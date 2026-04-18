"""
Health Vitals Tracking Module
Handles CRUD operations for patient health vitals (blood pressure, heart rate, glucose, SpO2, etc.)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from bson import ObjectId
import statistics


router = APIRouter(prefix="/api/vitals", tags=["Health Vitals"])

# ─────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────

class VitalReading(BaseModel):
    """A single vital sign measurement"""
    type: str  # blood_pressure, heart_rate, glucose, spo2, temperature, weight, bmi
    value: float
    unit: str
    systolic: Optional[float] = None   # for blood pressure
    diastolic: Optional[float] = None  # for blood pressure
    notes: str = ""
    recorded_at: Optional[str] = None  # ISO date string; server fills if absent

    @validator("type")
    def validate_type(cls, v):
        allowed = {"blood_pressure", "heart_rate", "glucose", "spo2", "temperature", "weight", "bmi", "respiratory_rate", "cholesterol", "hemoglobin"}
        if v not in allowed:
            raise ValueError(f"Vital type must be one of {allowed}")
        return v

    @validator("value")
    def validate_value(cls, v):
        if v < 0 or v > 10000:
            raise ValueError("Value out of realistic range")
        return v


class VitalUpdate(BaseModel):
    """Partial update model"""
    notes: Optional[str] = None
    value: Optional[float] = None
    systolic: Optional[float] = None
    diastolic: Optional[float] = None


class VitalAlert(BaseModel):
    """Threshold alert config"""
    vital_type: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    enabled: bool = True


# ─────────────────────────────────────────────────────
# Normal Ranges for Vitals (for alert generation)
# ─────────────────────────────────────────────────────

NORMAL_RANGES = {
    "heart_rate":        {"min": 60,    "max": 100,   "unit": "bpm",    "label": "Heart Rate"},
    "blood_pressure":    {"min": 60,    "max": 120,   "unit": "mmHg",   "label": "Blood Pressure (Systolic)"},
    "glucose":           {"min": 70,    "max": 140,   "unit": "mg/dL",  "label": "Blood Glucose"},
    "spo2":              {"min": 95,    "max": 100,   "unit": "%",      "label": "Oxygen Saturation"},
    "temperature":       {"min": 36.1,  "max": 37.2,  "unit": "°C",     "label": "Body Temperature"},
    "weight":            {"min": 30,    "max": 300,   "unit": "kg",     "label": "Weight"},
    "bmi":               {"min": 18.5,  "max": 24.9,  "unit": "",       "label": "BMI"},
    "respiratory_rate":  {"min": 12,    "max": 20,    "unit": "br/min", "label": "Respiratory Rate"},
    "cholesterol":       {"min": 0,     "max": 200,   "unit": "mg/dL",  "label": "Total Cholesterol"},
    "hemoglobin":        {"min": 12.0,  "max": 17.5,  "unit": "g/dL",   "label": "Hemoglobin"},
}


def check_vital_status(vital_type: str, value: float) -> dict:
    """Returns status: normal / warning / critical based on known ranges"""
    if vital_type not in NORMAL_RANGES:
        return {"status": "unknown", "message": "No reference range available"}
    r = NORMAL_RANGES[vital_type]
    if r["min"] <= value <= r["max"]:
        return {"status": "normal", "message": f"Within normal range ({r['min']}–{r['max']} {r['unit']})"}
    elif value < r["min"] * 0.85 or value > r["max"] * 1.20:
        return {"status": "critical", "message": f"Significantly out of range! Normal: {r['min']}–{r['max']} {r['unit']}"}
    else:
        return {"status": "warning", "message": f"Slightly out of range. Normal: {r['min']}–{r['max']} {r['unit']}"}


def compute_trend(readings: list, field: str = "value") -> dict:
    """Compute simple linear trend from a list of vital readings"""
    values = [r.get(field, 0) for r in readings if r.get(field) is not None]
    if len(values) < 2:
        return {"trend": "insufficient_data", "change": 0, "change_pct": 0}
    first, last = values[0], values[-1]
    change = round(last - first, 2)
    change_pct = round((change / first) * 100, 1) if first != 0 else 0
    if change > 0:
        trend = "increasing"
    elif change < 0:
        trend = "decreasing"
    else:
        trend = "stable"
    avg = round(statistics.mean(values), 2)
    std = round(statistics.stdev(values), 2) if len(values) > 1 else 0
    return {
        "trend": trend,
        "change": change,
        "change_pct": change_pct,
        "average": avg,
        "std_dev": std,
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "count": len(values),
    }


# ─────────────────────────────────────────────────────
# Route Factory - called from main.py
# ─────────────────────────────────────────────────────

def register_vitals_routes(app, db, get_current_user, log_action, serialize_doc):
    """Register all vitals-related routes onto the FastAPI app."""

    # ── POST /api/vitals ── Record a new vital reading
    @app.post("/api/vitals")
    async def record_vital(reading: VitalReading, current_user: dict = Depends(get_current_user)):
        """Record a new health vital reading for the current patient."""
        try:
            data = reading.dict()
            data["patient_id"] = current_user["uid"]
            data["patient_email"] = current_user.get("email", "")
            data["recorded_at"] = reading.recorded_at or datetime.utcnow().isoformat()
            data["created_at"] = datetime.utcnow()

            # Compute status
            check_val = reading.systolic if reading.type == "blood_pressure" and reading.systolic else reading.value
            data["status_info"] = check_vital_status(reading.type, check_val)

            result = await db.health_vitals.insert_one(data)
            await log_action(current_user, "record_vital", {"type": reading.type, "value": reading.value})
            return {"status": "success", "id": str(result.inserted_id), "status_info": data["status_info"]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/vitals ── Fetch the patient's own vitals
    @app.get("/api/vitals")
    async def get_vitals(
        vital_type: Optional[str] = Query(None, description="Filter by vital type"),
        days: int = Query(30, description="Days of history to return"),
        patient_id: Optional[str] = Query(None),
        current_user: dict = Depends(get_current_user),
    ):
        """Retrieve health vitals, optionally filtered by type and date range."""
        try:
            uid = current_user["uid"]
            role = current_user["role"]

            # Admins / doctors can query any patient
            if role in ["superuser", "admin", "superadmin", "doctor"] and patient_id:
                uid = patient_id
            elif role == "patient":
                uid = current_user["uid"]

            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            mongo_query = {"patient_id": uid, "recorded_at": {"$gte": cutoff}}

            if vital_type:
                mongo_query["type"] = vital_type

            cursor = db.health_vitals.find(mongo_query)
            vitals = []
            async for doc in cursor:
                vitals.append(serialize_doc(doc))

            vitals.sort(key=lambda x: x.get("recorded_at", ""), reverse=True)
            return {"vitals": vitals, "count": len(vitals)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/vitals/summary ── Statistical summary per vital type
    @app.get("/api/vitals/summary")
    async def get_vitals_summary(
        days: int = Query(30),
        patient_id: Optional[str] = Query(None),
        current_user: dict = Depends(get_current_user),
    ):
        """Get aggregated statistics summary for all vital types."""
        uid = current_user["uid"]
        role = current_user["role"]
        if role in ["superuser", "admin", "superadmin", "doctor"] and patient_id:
            uid = patient_id

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cursor = db.health_vitals.find({"patient_id": uid, "recorded_at": {"$gte": cutoff}})

        grouped: Dict[str, list] = {}
        async for doc in cursor:
            t = doc.get("type", "unknown")
            grouped.setdefault(t, []).append(doc)

        summary = {}
        for vtype, readings in grouped.items():
            readings.sort(key=lambda x: x.get("recorded_at", ""))
            trend_data = compute_trend(readings)
            latest = readings[-1] if readings else {}
            status_val = latest.get("systolic") if vtype == "blood_pressure" else latest.get("value")
            summary[vtype] = {
                "label": NORMAL_RANGES.get(vtype, {}).get("label", vtype),
                "unit": NORMAL_RANGES.get(vtype, {}).get("unit", ""),
                "latest_value": latest.get("value"),
                "latest_systolic": latest.get("systolic"),
                "latest_diastolic": latest.get("diastolic"),
                "latest_at": latest.get("recorded_at"),
                "trend": trend_data,
                "current_status": check_vital_status(vtype, status_val) if status_val else {"status": "unknown"},
                "normal_range": NORMAL_RANGES.get(vtype, {}),
            }
        return summary

    # ── GET /api/vitals/{vital_id} ── Single reading detail
    @app.get("/api/vitals/{vital_id}")
    async def get_single_vital(vital_id: str, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(vital_id)} if ObjectId.is_valid(vital_id) else {"vital_id": vital_id}
        doc = await db.health_vitals.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Vital reading not found")
        d = serialize_doc(doc)
        if current_user["role"] == "patient" and d.get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        return d

    # ── PATCH /api/vitals/{vital_id} ── Update notes/correction
    @app.patch("/api/vitals/{vital_id}")
    async def update_vital(
        vital_id: str,
        update: VitalUpdate,
        current_user: dict = Depends(get_current_user),
    ):
        query = {"_id": ObjectId(vital_id)} if ObjectId.is_valid(vital_id) else {"vital_id": vital_id}
        doc = await db.health_vitals.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Vital reading not found")
        if current_user["role"] == "patient" and doc.get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        patch = {k: v for k, v in update.dict().items() if v is not None}
        if patch:
            await db.health_vitals.update_one(query, {"$set": patch})
        await log_action(current_user, "update_vital", {"id": vital_id})
        return {"status": "success", "updated": list(patch.keys())}

    # ── DELETE /api/vitals/{vital_id} ── Remove a reading
    @app.delete("/api/vitals/{vital_id}")
    async def delete_vital(vital_id: str, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(vital_id)} if ObjectId.is_valid(vital_id) else {"vital_id": vital_id}
        doc = await db.health_vitals.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Vital reading not found")
        if current_user["role"] == "patient" and doc.get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        await db.health_vitals.delete_one(query)
        await log_action(current_user, "delete_vital", {"id": vital_id})
        return {"status": "success", "message": "Vital reading deleted"}

    # ── GET /api/vitals/alerts/active ── Fetch out-of-range alerts
    @app.get("/api/vitals/alerts/active")
    async def get_active_vital_alerts(
        patient_id: Optional[str] = Query(None),
        current_user: dict = Depends(get_current_user),
    ):
        """Return the most recent reading per vital type that is out of normal range."""
        uid = current_user["uid"]
        role = current_user["role"]
        if role in ["superuser", "admin", "superadmin", "doctor"] and patient_id:
            uid = patient_id

        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        cursor = db.health_vitals.find({"patient_id": uid, "recorded_at": {"$gte": cutoff}})

        latest_per_type: Dict[str, dict] = {}
        async for doc in cursor:
            t = doc.get("type", "")
            if t not in latest_per_type or doc.get("recorded_at", "") > latest_per_type[t].get("recorded_at", ""):
                latest_per_type[t] = doc

        alerts = []
        for vtype, reading in latest_per_type.items():
            check_val = reading.get("systolic") if vtype == "blood_pressure" and reading.get("systolic") else reading.get("value")
            if check_val is None:
                continue
            status = check_vital_status(vtype, check_val)
            if status["status"] in ("warning", "critical"):
                alerts.append({
                    "vital_type": vtype,
                    "value": reading.get("value"),
                    "systolic": reading.get("systolic"),
                    "diastolic": reading.get("diastolic"),
                    "recorded_at": reading.get("recorded_at"),
                    "status": status["status"],
                    "message": status["message"],
                    "reading_id": str(reading["_id"]),
                })
        alerts.sort(key=lambda x: x["status"] == "critical", reverse=True)
        return {"alerts": alerts, "count": len(alerts)}

    # ── GET /api/vitals/history/export ── CSV-like data export
    @app.get("/api/vitals/history/export")
    async def export_vitals_history(
        vital_type: Optional[str] = Query(None),
        days: int = Query(90),
        current_user: dict = Depends(get_current_user),
    ):
        """Export vitals history in a structured list format for charting."""
        uid = current_user["uid"]
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        mongo_query = {"patient_id": uid, "recorded_at": {"$gte": cutoff}}
        if vital_type:
            mongo_query["type"] = vital_type
            
        cursor = db.health_vitals.find(mongo_query)
        rows = []
        async for doc in cursor:
            d = serialize_doc(doc)
            rows.append({
                "date": d.get("recorded_at", ""),
                "type": d.get("type", ""),
                "value": d.get("value"),
                "systolic": d.get("systolic"),
                "diastolic": d.get("diastolic"),
                "unit": d.get("unit", ""),
                "status": d.get("status_info", {}).get("status", "unknown"),
            })
        rows.sort(key=lambda x: x["date"])
        return {"rows": rows, "count": len(rows), "days": days}

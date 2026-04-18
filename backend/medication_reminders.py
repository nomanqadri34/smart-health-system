"""
Medication Reminder System
Full CRUD for medication schedules, reminders, and adherence tracking.
"""
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, validator, Field
from typing import List, Optional, Dict
from datetime import datetime, timedelta, time
from bson import ObjectId


# ─────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────

class MedicationSchedule(BaseModel):
    medication_name: str
    dosage: str                   # e.g., "500mg", "10ml"
    form: str = "tablet"          # tablet, capsule, syrup, injection, inhaler, drops, patch
    frequency: str                # once_daily, twice_daily, thrice_daily, every_X_hours, as_needed, weekly
    times_of_day: List[str] = []  # ["08:00", "20:00"]
    start_date: str               # ISO date
    end_date: Optional[str] = None  # None = indefinite
    instructions: str = ""        # with food, before sleep, etc.
    side_effects_to_watch: List[str] = []
    prescribed_by: str = ""       # doctor name
    prescription_id: str = ""     # link to prescription doc
    refill_reminder_days: int = Field(default=7, ge=1, le=30)
    pill_count: Optional[int] = None
    condition: str = ""           # What condition this treats

    @validator("form")
    def validate_form(cls, v):
        allowed = {"tablet", "capsule", "syrup", "injection", "inhaler", "drops", "patch", "cream", "powder", "other"}
        if v not in allowed:
            raise ValueError(f"Form must be one of {allowed}")
        return v

    @validator("frequency")
    def validate_frequency(cls, v):
        allowed = {"once_daily", "twice_daily", "thrice_daily", "four_times_daily",
                   "every_4_hours", "every_6_hours", "every_8_hours", "every_12_hours",
                   "weekly", "biweekly", "monthly", "as_needed"}
        if v not in allowed:
            raise ValueError(f"Frequency must be one of {allowed}")
        return v


class AdherenceLog(BaseModel):
    schedule_id: str
    medication_name: str
    scheduled_time: str  # ISO datetime
    taken: bool
    taken_at: Optional[str] = None
    skipped_reason: str = ""
    side_effects_noted: Optional[str] = None


class MedicationUpdate(BaseModel):
    end_date: Optional[str] = None
    pill_count: Optional[int] = None
    instructions: Optional[str] = None
    refill_reminder_days: Optional[int] = None
    active: Optional[bool] = None


class RefillRequest(BaseModel):
    schedule_id: str
    medication_name: str
    quantity_requested: int
    pharmacy_name: str = ""
    notes: str = ""


# ─────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────

FREQUENCY_TIMES = {
    "once_daily":       ["08:00"],
    "twice_daily":      ["08:00", "20:00"],
    "thrice_daily":     ["07:00", "13:00", "19:00"],
    "four_times_daily": ["07:00", "11:00", "15:00", "21:00"],
    "every_4_hours":    ["06:00", "10:00", "14:00", "18:00", "22:00"],
    "every_6_hours":    ["06:00", "12:00", "18:00", "00:00"],
    "every_8_hours":    ["06:00", "14:00", "22:00"],
    "every_12_hours":   ["08:00", "20:00"],
    "weekly":           ["09:00"],
    "biweekly":         ["09:00"],
    "monthly":          ["09:00"],
    "as_needed":        [],
}


def compute_adherence_rate(logs: list) -> dict:
    """Calculate adherence % from a list of adherence logs."""
    total = len(logs)
    if total == 0:
        return {"rate": 0, "taken": 0, "skipped": 0, "total": 0, "level": "insufficient_data"}
    taken = sum(1 for l in logs if l.get("taken"))
    skipped = total - taken
    rate = round((taken / total) * 100, 1)
    if rate >= 90:
        level = "excellent"
    elif rate >= 75:
        level = "good"
    elif rate >= 50:
        level = "fair"
    else:
        level = "poor"
    return {"rate": rate, "taken": taken, "skipped": skipped, "total": total, "level": level}


def get_next_doses(schedule: dict, count: int = 3) -> list:
    """Compute the next N dose times for a given medication schedule."""
    freq = schedule.get("frequency", "once_daily")
    times = schedule.get("times_of_day") or FREQUENCY_TIMES.get(freq, ["08:00"])
    now = datetime.utcnow()
    upcoming = []
    for day_offset in range(7):
        date = now.date() + timedelta(days=day_offset)
        for t in times:
            try:
                hour, minute = map(int, t.split(":"))
                dose_dt = datetime(date.year, date.month, date.day, hour, minute)
                if dose_dt > now:
                    upcoming.append({
                        "datetime": dose_dt.isoformat(),
                        "time": t,
                        "date": date.isoformat(),
                    })
            except Exception:
                pass
        if len(upcoming) >= count:
            break
    return upcoming[:count]


def check_interactions(med_names: list) -> list:
    """
    Very simplified drug interaction check against a known list of pairs.
    In production, this would call a pharma API.
    """
    KNOWN_INTERACTIONS = {
        frozenset(["warfarin", "aspirin"]): "High bleeding risk — monitor INR closely.",
        frozenset(["metformin", "alcohol"]): "Risk of lactic acidosis — avoid alcohol.",
        frozenset(["ssri", "tramadol"]): "Risk of serotonin syndrome.",
        frozenset(["ace inhibitor", "potassium"]): "Risk of hyperkalemia.",
        frozenset(["statins", "grapefruit"]): "Grapefruit can increase statin levels.",
    }
    warnings = []
    med_lower = [m.lower() for m in med_names]
    for pair, warning in KNOWN_INTERACTIONS.items():
        pair_lower = {p.lower() for p in pair}
        if all(any(p in m for m in med_lower) for p in pair_lower):
            warnings.append({
                "medications": list(pair),
                "warning": warning,
                "severity": "high",
            })
    return warnings


# ─────────────────────────────────────────────────────
# Route Registration
# ─────────────────────────────────────────────────────

def register_medication_routes(app, db, get_current_user, log_action, serialize_doc):
    """Register all medication reminder routes onto the FastAPI app."""

    # ── POST /api/medications ── Create new medication schedule
    @app.post("/api/medications")
    async def create_medication_schedule(
        med: MedicationSchedule,
        current_user: dict = Depends(get_current_user),
    ):
        """Create a medication reminder schedule for the current patient."""
        try:
            data = med.dict()
            data["patient_id"] = current_user["uid"]
            data["patient_email"] = current_user.get("email", "")
            data["active"] = True
            data["created_at"] = datetime.utcnow()
            # Auto-fill times if not provided
            if not data.get("times_of_day"):
                data["times_of_day"] = FREQUENCY_TIMES.get(med.frequency, ["08:00"])
            data["next_doses"] = get_next_doses(data, count=5)
            result = await db.medication_schedules.insert_one(data)
            await log_action(current_user, "add_medication", {"med": med.medication_name})
            return {"status": "success", "id": str(result.inserted_id), "next_doses": data["next_doses"]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/medications ── Get all active medications
    @app.get("/api/medications")
    async def get_medications(
        patient_id: Optional[str] = Query(None),
        active_only: bool = Query(True),
        current_user: dict = Depends(get_current_user),
    ):
        """Get all medication schedules for the current user or a specified patient."""
        uid = current_user["uid"]
        role = current_user["role"]
        if role in ["superuser", "admin", "superadmin", "doctor"] and patient_id:
            uid = patient_id

        mongo_query = {"patient_id": uid}
        if active_only:
            mongo_query["active"] = True

        medications = []
        cursor = db.medication_schedules.find(mongo_query)
        async for doc in cursor:
            d = serialize_doc(doc)
            # Recompute next doses on fetch
            d["next_doses"] = get_next_doses(d, count=3)
            medications.append(d)

        # Check interactions
        active_names = [m.get("medication_name", "") for m in medications]
        interactions = check_interactions(active_names)

        return {
            "medications": medications,
            "count": len(medications),
            "interaction_warnings": interactions,
        }

    # ── GET /api/medications/{med_id} ── Single medication detail
    @app.get("/api/medications/{med_id}")
    async def get_single_medication(med_id: str, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(med_id)} if ObjectId.is_valid(med_id) else {"medication_id": med_id}
        doc = await db.medication_schedules.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Medication schedule not found")
        d = serialize_doc(doc)
        if current_user["role"] == "patient" and d.get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        d["next_doses"] = get_next_doses(d, count=5)
        return d

    # ── PATCH /api/medications/{med_id} ── Update schedule
    @app.patch("/api/medications/{med_id}")
    async def update_medication(
        med_id: str,
        update: MedicationUpdate,
        current_user: dict = Depends(get_current_user),
    ):
        query = {"_id": ObjectId(med_id)} if ObjectId.is_valid(med_id) else {"medication_id": med_id}
        doc = await db.medication_schedules.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Medication schedule not found")
        if current_user["role"] == "patient" and doc.get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        patch = {k: v for k, v in update.dict().items() if v is not None}
        patch["updated_at"] = datetime.utcnow()
        await db.medication_schedules.update_one(query, {"$set": patch})
        await log_action(current_user, "update_medication", {"id": med_id})
        return {"status": "success", "updated_fields": list(patch.keys())}

    # ── DELETE /api/medications/{med_id} ── Stop/delete a medication
    @app.delete("/api/medications/{med_id}")
    async def delete_medication(med_id: str, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(med_id)} if ObjectId.is_valid(med_id) else {"medication_id": med_id}
        doc = await db.medication_schedules.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Medication schedule not found")
        if current_user["role"] == "patient" and doc.get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        # Soft delete: mark as inactive
        await db.medication_schedules.update_one(query, {"$set": {"active": False, "stopped_at": datetime.utcnow()}})
        await log_action(current_user, "stop_medication", {"id": med_id})
        return {"status": "success", "message": "Medication schedule stopped"}

    # ── POST /api/medications/adherence ── Log a dose taken/skipped
    @app.post("/api/medications/adherence")
    async def log_adherence(
        log_data: AdherenceLog,
        current_user: dict = Depends(get_current_user),
    ):
        """Log whether a scheduled dose was taken or skipped."""
        try:
            data = log_data.dict()
            data["patient_id"] = current_user["uid"]
            data["logged_at"] = datetime.utcnow()
            result = await db.medication_adherence.insert_one(data)
            return {"status": "success", "log_id": str(result.inserted_id)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/medications/adherence/{med_id} ── Adherence stats for a medication
    @app.get("/api/medications/adherence/{med_id}")
    async def get_adherence_stats(
        med_id: str,
        days: int = Query(30),
        current_user: dict = Depends(get_current_user),
    ):
        """Get adherence statistics for a specific medication over N days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cursor = db.medication_adherence.find({
            "schedule_id": med_id,
            "patient_id": current_user["uid"]
        })

        logs = []
        async for doc in cursor:
            d = serialize_doc(doc)
            if d.get("scheduled_time", "") >= cutoff:
                logs.append(d)

        adherence = compute_adherence_rate(logs)
        return {
            "schedule_id": med_id,
            "days": days,
            "adherence": adherence,
            "logs": logs,
        }

    # ── POST /api/medications/refill-request ── Request a refill
    @app.post("/api/medications/refill-request")
    async def request_refill(
        refill: RefillRequest,
        current_user: dict = Depends(get_current_user),
    ):
        """Submit a medication refill request."""
        try:
            data = refill.dict()
            data["patient_id"] = current_user["uid"]
            data["patient_email"] = current_user.get("email", "")
            data["status"] = "pending"
            data["requested_at"] = datetime.utcnow()
            result = await db.refill_requests.insert_one(data)
            await log_action(current_user, "refill_request", {"med": refill.medication_name})
            return {"status": "success", "refill_id": str(result.inserted_id)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/medications/refills/pending ── Doctor views pending refills
    @app.get("/api/medications/refills/pending")
    async def get_pending_refills(current_user: dict = Depends(get_current_user)):
        """Doctors can view all pending refill requests."""
        if current_user["role"] not in ["doctor", "superuser", "admin", "superadmin"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        cursor = db.refill_requests.find({"status": "pending"})
        refills = []
        async for doc in cursor:
            refills.append(serialize_doc(doc))
        return {"refills": refills, "count": len(refills)}

    # ── GET /api/medications/adherence/overview ── Overall adherence for all active meds
    @app.get("/api/medications/adherence/overview")
    async def get_overall_adherence(
        days: int = Query(30),
        patient_id: Optional[str] = Query(None),
        current_user: dict = Depends(get_current_user),
    ):
        """Get an adherence overview across all active medications."""
        uid = current_user["uid"]
        role = current_user["role"]
        if role in ["superuser", "admin", "superadmin", "doctor"] and patient_id:
            uid = patient_id

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cursor = db.medication_adherence.find({"patient_id": uid})

        logs = []
        async for doc in cursor:
            d = serialize_doc(doc)
            if d.get("scheduled_time", "") >= cutoff:
                logs.append(d)

        by_medication: Dict[str, list] = {}
        for l in logs:
            name = l.get("medication_name", "Unknown")
            by_medication.setdefault(name, []).append(l)

        overview = []
        for name, med_logs in by_medication.items():
            adherence = compute_adherence_rate(med_logs)
            overview.append({"medication_name": name, "adherence": adherence})

        overall = compute_adherence_rate(logs)
        return {
            "overall": overall,
            "by_medication": overview,
            "days": days,
        }

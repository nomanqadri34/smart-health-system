"""
Lab Reports Management Module
Handles uploading metadata, viewing, and managing lab test reports for patients.
"""
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, validator
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from firebase_admin import firestore


# ─────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────

class LabReportCreate(BaseModel):
    patient_id: str
    patient_name: str
    patient_email: str
    test_name: str
    test_category: str   # e.g., Hematology, Biochemistry, Microbiology, Imaging, Pathology
    lab_name: str = ""
    performed_date: str  # ISO date
    results: Dict[str, str] = {}  # {parameter: value_string}
    reference_ranges: Dict[str, str] = {}  # {parameter: "min-max unit"}
    interpretation: str = ""   # Normal / Abnormal / Critical
    doctor_remarks: str = ""
    report_url: str = ""        # URL to the uploaded PDF/image

    @validator("test_category")
    def validate_category(cls, v):
        allowed = {
            "Hematology", "Biochemistry", "Microbiology", "Imaging",
            "Pathology", "Immunology", "Endocrinology", "Cardiology",
            "Neurology", "Genetics", "Urine Analysis", "Other"
        }
        if v not in allowed:
            raise ValueError(f"Category must be one of {allowed}")
        return v

    @validator("interpretation")
    def validate_interpretation(cls, v):
        if v and v not in ("", "Normal", "Abnormal", "Critical", "Borderline", "Pending"):
            raise ValueError("Interpretation must be Normal, Abnormal, Critical, Borderline, or Pending")
        return v


class LabReportUpdate(BaseModel):
    doctor_remarks: Optional[str] = None
    interpretation: Optional[str] = None
    results: Optional[Dict[str, str]] = None
    reference_ranges: Optional[Dict[str, str]] = None
    report_url: Optional[str] = None


class LabReportShare(BaseModel):
    share_with_doctor_id: str
    message: str = ""
    expires_in_days: int = 7


# ─────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────

# Common lab test normal ranges for quick reference
COMMON_LAB_RANGES = {
    "Hemoglobin":       {"male": "13.5-17.5 g/dL", "female": "12.0-15.5 g/dL"},
    "WBC":              {"all": "4,500-11,000 cells/mcL"},
    "Platelets":        {"all": "150,000-450,000/mcL"},
    "Glucose (Fasting)": {"all": "70-100 mg/dL"},
    "HbA1c":            {"all": "<5.7% (Normal), 5.7-6.4% (Prediabetes), ≥6.5% (Diabetes)"},
    "Total Cholesterol": {"all": "<200 mg/dL (Desirable)"},
    "LDL":              {"all": "<100 mg/dL (Optimal)"},
    "HDL":              {"male": ">40 mg/dL", "female": ">50 mg/dL"},
    "Triglycerides":    {"all": "<150 mg/dL"},
    "Creatinine":       {"male": "0.74-1.35 mg/dL", "female": "0.59-1.04 mg/dL"},
    "ALT":              {"all": "7-56 U/L"},
    "AST":              {"all": "10-40 U/L"},
    "TSH":              {"all": "0.4-4.0 mIU/L"},
    "Vitamin D":        {"all": "20-50 ng/mL (Sufficient)"},
    "Vitamin B12":      {"all": "200-900 pg/mL"},
    "Iron":             {"male": "60-170 mcg/dL", "female": "50-170 mcg/dL"},
}


def flag_abnormal_results(results: dict, reference_ranges: dict) -> dict:
    """Simple check: mark result parameters that are flagged as abnormal."""
    flags = {}
    for param, value in results.items():
        value_str = str(value).lower()
        if any(kw in value_str for kw in ["high", "low", "critical", "abnormal", "h ", "l "]):
            flags[param] = "abnormal"
        else:
            flags[param] = "normal"
    return flags


def categorize_urgency(interpretation: str) -> str:
    mapping = {
        "Critical": "urgent",
        "Abnormal": "review_needed",
        "Borderline": "monitor",
        "Normal": "routine",
        "Pending": "pending",
        "": "pending",
    }
    return mapping.get(interpretation, "review_needed")


# ─────────────────────────────────────────────────────
# Route Registration
# ─────────────────────────────────────────────────────

def register_lab_report_routes(app, db, get_current_user, log_action, serialize_doc):
    """Register all lab report routes onto the FastAPI app."""

    # ── POST /api/lab-reports ── Upload/create a lab report record
    @app.post("/api/lab-reports")
    def create_lab_report(report: LabReportCreate, current_user: dict = Depends(get_current_user)):
        """Create a new lab report record."""
        if current_user["role"] not in ["doctor", "superuser", "admin", "superadmin"]:
            raise HTTPException(status_code=403, detail="Only doctors or admins can upload lab reports")
        try:
            data = report.dict()
            data["doctor_id"] = current_user["uid"]
            data["doctor_email"] = current_user.get("email", "")
            data["uploaded_at"] = firestore.SERVER_TIMESTAMP
            data["urgency"] = categorize_urgency(report.interpretation)
            data["abnormal_flags"] = flag_abnormal_results(report.results, report.reference_ranges)
            data["common_ranges"] = {
                k: v for k, v in COMMON_LAB_RANGES.items()
                if any(k.lower() in param.lower() for param in report.results.keys())
            }
            ref = db.collection("lab_reports").add(data)
            log_action(current_user, "upload_lab_report", {
                "patient": report.patient_name,
                "test": report.test_name,
                "id": ref[1].id,
            })
            return {"status": "success", "report_id": ref[1].id, "urgency": data["urgency"]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/lab-reports ── Fetch reports (role-aware)
    @app.get("/api/lab-reports")
    def get_lab_reports(
        patient_id: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
        interpretation: Optional[str] = Query(None),
        days: int = Query(365),
        current_user: dict = Depends(get_current_user),
    ):
        """Retrieve lab reports; filtered by role."""
        role = current_user["role"]
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        if role in ["superuser", "admin", "superadmin"]:
            query = db.collection("lab_reports")
            if patient_id:
                query = query.where("patient_id", "==", patient_id)
        elif role == "doctor":
            if patient_id:
                query = db.collection("lab_reports").where("patient_id", "==", patient_id)
            else:
                query = db.collection("lab_reports").where("doctor_id", "==", current_user["uid"])
        else:
            query = db.collection("lab_reports").where("patient_email", "==", current_user.get("email", ""))

        if category:
            query = query.where("test_category", "==", category)
        if interpretation:
            query = query.where("interpretation", "==", interpretation)

        reports = []
        for doc in query.stream():
            d = doc.to_dict()
            d["id"] = doc.id
            d = serialize_doc(d)
            reports.append(d)

        reports.sort(key=lambda x: x.get("performed_date", ""), reverse=True)
        return {"reports": reports, "count": len(reports)}

    # ── GET /api/lab-reports/{report_id} ── Single report detail
    @app.get("/api/lab-reports/{report_id}")
    def get_single_lab_report(report_id: str, current_user: dict = Depends(get_current_user)):
        doc = db.collection("lab_reports").document(report_id).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Lab report not found")
        d = doc.to_dict()
        d["id"] = doc.id
        d = serialize_doc(d)
        role = current_user["role"]
        if role == "patient" and d.get("patient_email") != current_user.get("email"):
            raise HTTPException(status_code=403, detail="Not authorized")
        if role == "doctor" and d.get("doctor_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        return d

    # ── PATCH /api/lab-reports/{report_id} ── Doctor updates remarks/interpretation
    @app.patch("/api/lab-reports/{report_id}")
    def update_lab_report(
        report_id: str,
        update: LabReportUpdate,
        current_user: dict = Depends(get_current_user),
    ):
        if current_user["role"] not in ["doctor", "superuser", "admin", "superadmin"]:
            raise HTTPException(status_code=403, detail="Only doctors can update lab reports")
        doc_ref = db.collection("lab_reports").document(report_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Lab report not found")
        patch = {k: v for k, v in update.dict().items() if v is not None}
        if "interpretation" in patch:
            patch["urgency"] = categorize_urgency(patch["interpretation"])
        patch["last_updated"] = firestore.SERVER_TIMESTAMP
        doc_ref.update(patch)
        log_action(current_user, "update_lab_report", {"id": report_id})
        return {"status": "success", "updated": list(patch.keys())}

    # ── DELETE /api/lab-reports/{report_id} ── Remove a report
    @app.delete("/api/lab-reports/{report_id}")
    def delete_lab_report(report_id: str, current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in ["doctor", "superuser", "admin", "superadmin"]:
            raise HTTPException(status_code=403, detail="Only doctors or admins can delete reports")
        doc_ref = db.collection("lab_reports").document(report_id)
        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail="Lab report not found")
        doc_ref.delete()
        log_action(current_user, "delete_lab_report", {"id": report_id})
        return {"status": "success"}

    # ── POST /api/lab-reports/{report_id}/share ── Share with doctor
    @app.post("/api/lab-reports/{report_id}/share")
    def share_lab_report(
        report_id: str,
        share_data: LabReportShare,
        current_user: dict = Depends(get_current_user),
    ):
        """Allow a patient to share their lab report with a doctor."""
        doc_ref = db.collection("lab_reports").document(report_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Lab report not found")
        d = doc.to_dict()
        if d.get("patient_email") != current_user.get("email") and current_user["role"] not in ["superuser", "admin", "superadmin"]:
            raise HTTPException(status_code=403, detail="Can only share your own reports")

        share_record = {
            "report_id": report_id,
            "shared_by": current_user["uid"],
            "shared_with_doctor_id": share_data.share_with_doctor_id,
            "message": share_data.message,
            "expires_at": (datetime.utcnow() + timedelta(days=share_data.expires_in_days)).isoformat(),
            "shared_at": firestore.SERVER_TIMESTAMP,
            "active": True,
        }
        ref = db.collection("lab_report_shares").add(share_record)
        log_action(current_user, "share_lab_report", {"report_id": report_id, "to": share_data.share_with_doctor_id})
        return {"status": "success", "share_id": ref[1].id}

    # ── GET /api/lab-reports/stats/summary ── Aggregated lab stats for patient
    @app.get("/api/lab-reports/stats/summary")
    def get_lab_stats_summary(
        patient_id: Optional[str] = Query(None),
        current_user: dict = Depends(get_current_user),
    ):
        """Return a count breakdown of lab reports by category and interpretation."""
        role = current_user["role"]
        if role in ["superuser", "admin", "superadmin", "doctor"] and patient_id:
            query = db.collection("lab_reports").where("patient_id", "==", patient_id)
        else:
            query = db.collection("lab_reports").where("patient_email", "==", current_user.get("email", ""))

        categories = {}
        interpretations = {}
        critical_count = 0

        for doc in query.stream():
            d = doc.to_dict()
            cat = d.get("test_category", "Other")
            interp = d.get("interpretation", "Pending")
            categories[cat] = categories.get(cat, 0) + 1
            interpretations[interp] = interpretations.get(interp, 0) + 1
            if interp == "Critical":
                critical_count += 1

        return {
            "by_category": categories,
            "by_interpretation": interpretations,
            "critical_reports": critical_count,
            "total": sum(categories.values()),
            "common_reference_ranges": COMMON_LAB_RANGES,
        }

    # ── GET /api/lab-reports/reference-ranges ── Reference ranges
    @app.get("/api/lab-reports/reference-ranges")
    def get_reference_ranges():
        """Return common lab test reference ranges for patient education."""
        return {
            "reference_ranges": COMMON_LAB_RANGES,
            "test_categories": [
                "Hematology", "Biochemistry", "Microbiology", "Imaging",
                "Pathology", "Immunology", "Endocrinology", "Cardiology",
                "Neurology", "Genetics", "Urine Analysis", "Other"
            ]
        }

"""
Waitlist Management
Manages patient waitlists for fully booked doctors.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from firebase_admin import firestore

class WaitlistEntryCreate(BaseModel):
    doctor_id: str
    department: str
    preferred_date: str
    preferred_time_range: str = "Any"
    urgency: str = "Routine" # Routine, Urgent
    notes: str = ""

def register_waitlist_routes(app, db, get_current_user, log_action, serialize_doc):

    # ── POST /api/waitlist ── Join Waitlist
    @app.post("/api/waitlist")
    def join_waitlist(entry: WaitlistEntryCreate, current_user: dict = Depends(get_current_user)):
        data = entry.dict()
        data["patient_id"] = current_user["uid"]
        data["patient_email"] = current_user.get("email", "")
        data["status"] = "waiting" # waiting, notified, booked, cancelled
        data["joined_at"] = firestore.SERVER_TIMESTAMP
        
        ref = db.collection("waitlists").add(data)
        log_action(current_user, "join_waitlist", {"doctor": entry.doctor_id})
        return {"status": "success", "waitlist_id": ref[1].id}

    # ── GET /api/waitlist ── Get Waitlist entries for Doctor
    @app.get("/api/waitlist")
    def get_waitlist(doctor_id: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
        if current_user["role"] == "doctor":
             query = db.collection("waitlists").where("doctor_id", "==", current_user["uid"]).where("status", "==", "waiting")
        elif current_user["role"] in ["superuser", "admin", "superadmin"] and doctor_id:
             query = db.collection("waitlists").where("doctor_id", "==", doctor_id).where("status", "==", "waiting")
        elif current_user["role"] == "patient":
             query = db.collection("waitlists").where("patient_id", "==", current_user["uid"])
        else:
             raise HTTPException(status_code=403, detail="Not authorized")
             
        docs = query.stream()
        entries = []
        for doc in docs:
             d = doc.to_dict()
             d["id"] = doc.id
             entries.append(serialize_doc(d))
             
        # Sort by urgency and date joined
        def sort_key(e):
             u_score = 0 if e.get("urgency") == "Urgent" else 1
             return (u_score, e.get("joined_at", ""))
             
        entries.sort(key=sort_key)
        return entries

    # ── PATCH /api/waitlist/{waitlist_id}/notify ── Notify Patient (Doctor triggers)
    @app.patch("/api/waitlist/{waitlist_id}/notify")
    def notify_waitlisted_patient(waitlist_id: str, current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in ["doctor", "admin", "superadmin"]:
             raise HTTPException(status_code=403, detail="Only doctors/admins can notify patients")
             
        doc_ref = db.collection("waitlists").document(waitlist_id)
        if not doc_ref.get().exists:
             raise HTTPException(status_code=404, detail="Waitlist entry not found")
             
        doc_ref.update({
             "status": "notified",
             "notified_at": firestore.SERVER_TIMESTAMP
        })
        
        # Here we would integrate with NotificationsService (email/sms)
        return {"status": "success", "message": "Patient notified of available slot"}

    # ── DELETE /api/waitlist/{waitlist_id} ── Leave waitlist
    @app.delete("/api/waitlist/{waitlist_id}")
    def leave_waitlist(waitlist_id: str, current_user: dict = Depends(get_current_user)):
        doc_ref = db.collection("waitlists").document(waitlist_id)
        doc = doc_ref.get()
        if not doc.exists:
             raise HTTPException(status_code=404, detail="Entry not found")
             
        if doc.to_dict().get("patient_id") != current_user["uid"] and current_user["role"] not in ["doctor", "admin", "superuser", "superadmin"]:
             raise HTTPException(status_code=403, detail="Not authorized")
             
        doc_ref.update({"status": "cancelled", "cancelled_at": firestore.SERVER_TIMESTAMP})
        return {"status": "success"}

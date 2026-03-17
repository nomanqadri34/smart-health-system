"""
Telemedicine System
Manages video call sessions, meeting links, and session notes for remote consultations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
from firebase_admin import firestore

# ─────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────

class TelemedicineSessionCreate(BaseModel):
    appointment_id: str
    host_doctor_id: str
    patient_id: str
    scheduled_time: str # ISO datetime
    duration_minutes: int = 30
    notes: str = ""

class TelemedicineNotes(BaseModel):
    session_notes: str
    prescription_summary: str = ""
    follow_up_required: bool = False
    follow_up_interval_days: int = 0

# ─────────────────────────────────────────────────────
# Route Registration
# ─────────────────────────────────────────────────────

def register_telemedicine_routes(app, db, get_current_user, log_action, serialize_doc):

    # ── POST /api/telemedicine/session ── Create a video session (Doctor/Admin)
    @app.post("/api/telemedicine/session")
    def create_telemedicine_session(session: TelemedicineSessionCreate, current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in ["doctor", "admin", "superadmin", "superuser"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        meeting_id = str(uuid.uuid4())
        join_url = f"https://meet.smarthealth.local/{meeting_id}"
        
        data = session.dict()
        data["meeting_id"] = meeting_id
        data["join_url"] = join_url
        data["status"] = "scheduled" # scheduled, active, completed, cancelled
        data["created_at"] = firestore.SERVER_TIMESTAMP
        
        ref = db.collection("telemedicine_sessions").add(data)
        
        # Optionally link this session to the appointment document
        db.collection("appointments").document(session.appointment_id).update({
            "is_telemedicine": True,
            "telemedicine_session_id": ref[1].id,
            "meeting_url": join_url
        })
        
        log_action(current_user, "create_telemed_session", {"appointment": session.appointment_id})
        return {"status": "success", "session_id": ref[1].id, "join_url": join_url, "meeting_id": meeting_id}

    # ── GET /api/telemedicine/sessions ── Get user's sessions
    @app.get("/api/telemedicine/sessions")
    def get_telemedicine_sessions(current_user: dict = Depends(get_current_user)):
        if current_user["role"] == "doctor":
            query = db.collection("telemedicine_sessions").where("host_doctor_id", "==", current_user["uid"])
        else:
            query = db.collection("telemedicine_sessions").where("patient_id", "==", current_user["uid"])
            
        docs = query.stream()
        sessions = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            sessions.append(serialize_doc(d))
            
        return sessions

    # ── GET /api/telemedicine/session/{session_id}/join ── Get join details
    @app.get("/api/telemedicine/session/{session_id}/join")
    def join_session(session_id: str, current_user: dict = Depends(get_current_user)):
        doc_ref = db.collection("telemedicine_sessions").document(session_id)
        doc = doc_ref.get()
        if not doc.exists:
             raise HTTPException(status_code=404, detail="Session not found")
        
        data = doc.to_dict()
        if data.get("patient_id") != current_user["uid"] and data.get("host_doctor_id") != current_user["uid"] and current_user["role"] not in ["admin", "superadmin", "superuser"]:
            raise HTTPException(status_code=403, detail="Not authorized to join this session")
            
        if data.get("status") == "scheduled":
             # Mark as active if doctor is joining
             if current_user["uid"] == data.get("host_doctor_id"):
                  doc_ref.update({"status": "active", "started_at": firestore.SERVER_TIMESTAMP})
                  
        return {
            "join_url": data.get("join_url"),
            "meeting_id": data.get("meeting_id"),
            "status": data.get("status")
        }

    # ── POST /api/telemedicine/session/{session_id}/end ── End session and add notes
    @app.post("/api/telemedicine/session/{session_id}/end")
    def end_session(session_id: str, notes: TelemedicineNotes, current_user: dict = Depends(get_current_user)):
        doc_ref = db.collection("telemedicine_sessions").document(session_id)
        doc = doc_ref.get()
        if not doc.exists:
             raise HTTPException(status_code=404, detail="Session not found")
             
        data = doc.to_dict()
        if current_user["uid"] != data.get("host_doctor_id") and current_user["role"] not in ["admin", "superadmin", "superuser"]:
            raise HTTPException(status_code=403, detail="Only the host doctor can end the session")
            
        doc_ref.update({
             "status": "completed",
             "ended_at": firestore.SERVER_TIMESTAMP,
             "clinical_notes": notes.dict()
        })
        
        # Update Appointment status
        if data.get("appointment_id"):
             try:
                  db.collection("appointments").document(data.get("appointment_id")).update({"status": "completed"})
             except Exception:
                  pass
                  
        log_action(current_user, "end_telemed_session", {"session_id": session_id})
        return {"status": "success"}

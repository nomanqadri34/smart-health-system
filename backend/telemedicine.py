"""
Telemedicine System
Manages video call sessions, meeting links, and session notes for remote consultations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
from bson import ObjectId

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
    async def create_telemedicine_session(session: TelemedicineSessionCreate, current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in ["doctor", "admin", "superadmin", "superuser"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        meeting_id = str(uuid.uuid4())
        join_url = f"https://meet.smarthealth.local/{meeting_id}"
        
        data = session.dict()
        data["meeting_id"] = meeting_id
        data["join_url"] = join_url
        data["status"] = "scheduled" # scheduled, active, completed, cancelled
        data["created_at"] = datetime.utcnow()
        
        result = await db.telemedicine_sessions.insert_one(data)
        session_doc_id = str(result.inserted_id)
        
        # Link this session to the appointment document
        apt_query = {"_id": ObjectId(session.appointment_id)} if ObjectId.is_valid(session.appointment_id) else {"appointment_id": session.appointment_id}
        await db.appointments.update_one(apt_query, {
            "$set": {
                "is_telemedicine": True,
                "telemedicine_session_id": session_doc_id,
                "meeting_url": join_url
            }
        })
        
        await log_action(current_user, "create_telemed_session", {"appointment": session.appointment_id})
        return {"status": "success", "session_id": session_doc_id, "join_url": join_url, "meeting_id": meeting_id}

    # ── GET /api/telemedicine/sessions ── Get user's sessions
    @app.get("/api/telemedicine/sessions")
    async def get_telemedicine_sessions(current_user: dict = Depends(get_current_user)):
        mongo_query = {}
        if current_user["role"] == "doctor":
            mongo_query = {"host_doctor_id": current_user["uid"]}
        else:
            mongo_query = {"patient_id": current_user["uid"]}
            
        cursor = db.telemedicine_sessions.find(mongo_query)
        sessions = []
        async for doc in cursor:
            sessions.append(serialize_doc(doc))
            
        return sessions

    # ── GET /api/telemedicine/session/{session_id}/join ── Get join details
    @app.get("/api/telemedicine/session/{session_id}/join")
    async def join_session(session_id: str, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(session_id)} if ObjectId.is_valid(session_id) else {"session_id": session_id}
        doc = await db.telemedicine_sessions.find_one(query)
        if not doc:
             raise HTTPException(status_code=404, detail="Session not found")
        
        if doc.get("patient_id") != current_user["uid"] and doc.get("host_doctor_id") != current_user["uid"] and current_user["role"] not in ["admin", "superadmin", "superuser"]:
            raise HTTPException(status_code=403, detail="Not authorized to join this session")
            
        if doc.get("status") == "scheduled":
             # Mark as active if doctor is joining
             if current_user["uid"] == doc.get("host_doctor_id"):
                  await db.telemedicine_sessions.update_one(query, {"$set": {"status": "active", "started_at": datetime.utcnow()}})
                  
        return {
            "join_url": doc.get("join_url"),
            "meeting_id": doc.get("meeting_id"),
            "status": doc.get("status")
        }

    # ── POST /api/telemedicine/session/{session_id}/end ── End session and add notes
    @app.post("/api/telemedicine/session/{session_id}/end")
    async def end_session(session_id: str, notes: TelemedicineNotes, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(session_id)} if ObjectId.is_valid(session_id) else {"session_id": session_id}
        doc = await db.telemedicine_sessions.find_one(query)
        if not doc:
             raise HTTPException(status_code=404, detail="Session not found")
             
        if current_user["uid"] != doc.get("host_doctor_id") and current_user["role"] not in ["admin", "superadmin", "superuser"]:
            raise HTTPException(status_code=403, detail="Only the host doctor can end the session")
            
        await db.telemedicine_sessions.update_one(query, {
            "$set": {
                 "status": "completed",
                 "ended_at": datetime.utcnow(),
                 "clinical_notes": notes.dict()
            }
        })
        
        # Update Appointment status
        apt_id = doc.get("appointment_id")
        if apt_id:
             try:
                  apt_query = {"_id": ObjectId(apt_id)} if ObjectId.is_valid(apt_id) else {"appointment_id": apt_id}
                  await db.appointments.update_one(apt_query, {"$set": {"status": "completed"}})
             except Exception:
                  pass
                  
        await log_action(current_user, "end_telemed_session", {"session_id": session_id})
        return {"status": "success"}

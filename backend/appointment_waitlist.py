"""
Waitlist Management
Manages patient waitlists for fully booked doctors.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

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
    async def join_waitlist(entry: WaitlistEntryCreate, current_user: dict = Depends(get_current_user)):
        data = entry.dict()
        data["patient_id"] = current_user["uid"]
        data["patient_email"] = current_user.get("email", "")
        data["status"] = "waiting" # waiting, notified, booked, cancelled
        data["joined_at"] = datetime.utcnow()
        
        result = await db.waitlists.insert_one(data)
        await log_action(current_user, "join_waitlist", {"doctor": entry.doctor_id})
        return {"status": "success", "waitlist_id": str(result.inserted_id)}

    # ── GET /api/waitlist ── Get Waitlist entries for Doctor
    @app.get("/api/waitlist")
    async def get_waitlist(doctor_id: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
        mongo_query = {}
        if current_user["role"] == "doctor":
             mongo_query = {"doctor_id": current_user["uid"], "status": "waiting"}
        elif current_user["role"] in ["superuser", "admin", "superadmin"] and doctor_id:
             mongo_query = {"doctor_id": doctor_id, "status": "waiting"}
        elif current_user["role"] == "patient":
             mongo_query = {"patient_id": current_user["uid"]}
        else:
             raise HTTPException(status_code=403, detail="Not authorized")
             
        cursor = db.waitlists.find(mongo_query)
        entries = []
        async for doc in cursor:
             entries.append(serialize_doc(doc))
             
        # Sort by urgency and date joined
        def sort_key(e):
             u_score = 0 if e.get("urgency") == "Urgent" else 1
             return (u_score, e.get("joined_at", ""))
             
        entries.sort(key=sort_key)
        return entries

    # ── PATCH /api/waitlist/{waitlist_id}/notify ── Notify Patient (Doctor triggers)
    @app.patch("/api/waitlist/{waitlist_id}/notify")
    async def notify_waitlisted_patient(waitlist_id: str, current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in ["doctor", "admin", "superadmin"]:
             raise HTTPException(status_code=403, detail="Only doctors/admins can notify patients")
             
        query = {"_id": ObjectId(waitlist_id)} if ObjectId.is_valid(waitlist_id) else {"waitlist_id": waitlist_id}
        doc = await db.waitlists.find_one(query)
        if not doc:
             raise HTTPException(status_code=404, detail="Waitlist entry not found")
             
        await db.waitlists.update_one(query, {
             "$set": {
                  "status": "notified",
                  "notified_at": datetime.utcnow()
             }
        })
        
        # Here we would integrate with NotificationsService (email/sms)
        return {"status": "success", "message": "Patient notified of available slot"}

    # ── DELETE /api/waitlist/{waitlist_id} ── Leave waitlist
    @app.delete("/api/waitlist/{waitlist_id}")
    async def leave_waitlist(waitlist_id: str, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(waitlist_id)} if ObjectId.is_valid(waitlist_id) else {"waitlist_id": waitlist_id}
        doc = await db.waitlists.find_one(query)
        if not doc:
             raise HTTPException(status_code=404, detail="Entry not found")
             
        if doc.get("patient_id") != current_user["uid"] and current_user["role"] not in ["doctor", "admin", "superuser", "superadmin"]:
             raise HTTPException(status_code=403, detail="Not authorized")
             
        await db.waitlists.update_one(query, {"$set": {"status": "cancelled", "cancelled_at": datetime.utcnow()}})
        return {"status": "success"}

"""
Emergency Alert System
Handles SOS triggers, emergency contacts, ambulance tracking, and urgent notifications.
"""
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

# ─────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────

class LocationInfo(BaseModel):
    latitude: float
    longitude: float
    address: str = ""

class EmergencyContact(BaseModel):
    name: str
    relation: str
    phone: str
    email: Optional[str] = None
    is_primary: bool = False

class SOSRequest(BaseModel):
    location: LocationInfo
    nature_of_emergency: str = "Medical Emergency"
    requires_ambulance: bool = True
    additional_notes: str = ""

class AlertUpdate(BaseModel):
    status: str
    resolution_notes: Optional[str] = None
    responder_id: Optional[str] = None

# ─────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────

def dispatch_ambulance(location: dict, patient_id: str) -> dict:
    """Mock function to simulate dispatching an ambulance."""
    return {
        "dispatched": True,
        "ambulance_id": "AMB-1042",
        "eta_minutes": 12,
        "contact": "+1-800-AMBULANCE",
        "live_tracking_url": f"https://tracker.smarthealth.local/ambulance/AMB-1042?patient={patient_id}"
    }

def notify_emergency_contacts(contacts: list, patient_name: str, location: dict):
    """Mock function to simulate sending SMS/Emails to emergency contacts."""
    notifications_sent = 0
    for contact in contacts:
        if contact.get("phone"):
            # Mock sending SMS
            notifications_sent += 1
    return notifications_sent

# ─────────────────────────────────────────────────────
# Route Registration
# ─────────────────────────────────────────────────────

def register_emergency_routes(app, db, get_current_user, log_action, serialize_doc):
    """Register all emergency alert routes onto the FastAPI app."""

    # ── POST /api/emergency/contacts ── Add emergency contact
    @app.post("/api/emergency/contacts")
    async def add_emergency_contact(contact: EmergencyContact, current_user: dict = Depends(get_current_user)):
        try:
            data = contact.dict()
            data["patient_id"] = current_user["uid"]
            data["created_at"] = datetime.utcnow()
            result = await db.emergency_contacts.insert_one(data)
            return {"status": "success", "id": str(result.inserted_id)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/emergency/contacts ── Get emergency contacts
    @app.get("/api/emergency/contacts")
    async def get_emergency_contacts(current_user: dict = Depends(get_current_user)):
        cursor = db.emergency_contacts.find({"patient_id": current_user["uid"]})
        contacts = []
        async for doc in cursor:
            contacts.append(serialize_doc(doc))
        return contacts

    # ── DELETE /api/emergency/contacts/{contact_id} ── Delete emergency contact
    @app.delete("/api/emergency/contacts/{contact_id}")
    async def delete_emergency_contact(contact_id: str, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(contact_id)} if ObjectId.is_valid(contact_id) else {"contact_id": contact_id}
        doc = await db.emergency_contacts.find_one(query)
        if not doc or doc.get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        await db.emergency_contacts.delete_one(query)
        return {"status": "success"}

    # ── POST /api/emergency/sos ── Trigger SOS Alert
    @app.post("/api/emergency/sos")
    async def trigger_sos(sos: SOSRequest, current_user: dict = Depends(get_current_user)):
        try:
            data = sos.dict()
            data["patient_id"] = current_user["uid"]
            data["patient_email"] = current_user.get("email", "")
            data["patient_name"] = current_user.get("full_name", "")
            data["status"] = "active"
            data["triggered_at"] = datetime.utcnow()

            # Fetch emergency contacts
            contacts = []
            cursor = db.emergency_contacts.find({"patient_id": current_user["uid"]})
            async for doc in cursor:
                contacts.append(doc)

            # Notifications & Dispatch
            notifs = notify_emergency_contacts(contacts, data["patient_name"], data["location"])
            data["contacts_notified"] = notifs

            if sos.requires_ambulance:
                data["ambulance_info"] = dispatch_ambulance(data["location"], data["patient_id"])

            result = await db.sos_alerts.insert_one(data)
            await log_action(current_user, "triggered_sos", {"location": data["location"]})
            
            return {
                "status": "success",
                "alert_id": str(result.inserted_id),
                "ambulance_info": data.get("ambulance_info")
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/emergency/active ── Admin/Doctor view active emergencies
    @app.get("/api/emergency/active")
    async def get_active_emergencies(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in ["superuser", "admin", "superadmin", "doctor"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        cursor = db.sos_alerts.find({"status": "active"})
        alerts = []
        async for doc in cursor:
            alerts.append(serialize_doc(doc))
        
        # Sort by most recent
        alerts.sort(key=lambda x: x.get("triggered_at", ""), reverse=True)
        return alerts

    # ── PATCH /api/emergency/{alert_id} ── Update SOS Alert Status
    @app.patch("/api/emergency/{alert_id}")
    async def update_emergency_status(alert_id: str, update: AlertUpdate, current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in ["superuser", "admin", "superadmin", "doctor"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        query = {"_id": ObjectId(alert_id)} if ObjectId.is_valid(alert_id) else {"alert_id": alert_id}
        doc = await db.sos_alerts.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        patch = update.dict(exclude_unset=True)
        patch["updated_at"] = datetime.utcnow()
        if patch.get("status") == "resolved":
            patch["resolved_at"] = datetime.utcnow()
            
        await db.sos_alerts.update_one(query, {"$set": patch})
        await log_action(current_user, "update_sos", {"alert_id": alert_id, "status": update.status})
        return {"status": "success"}

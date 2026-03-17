"""
Emergency Alert System
Handles SOS triggers, emergency contacts, ambulance tracking, and urgent notifications.
"""
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from firebase_admin import firestore

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
    def add_emergency_contact(contact: EmergencyContact, current_user: dict = Depends(get_current_user)):
        try:
            data = contact.dict()
            data["patient_id"] = current_user["uid"]
            data["created_at"] = firestore.SERVER_TIMESTAMP
            ref = db.collection("emergency_contacts").add(data)
            return {"status": "success", "id": ref[1].id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/emergency/contacts ── Get emergency contacts
    @app.get("/api/emergency/contacts")
    def get_emergency_contacts(current_user: dict = Depends(get_current_user)):
        docs = db.collection("emergency_contacts").where("patient_id", "==", current_user["uid"]).stream()
        contacts = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            d = serialize_doc(d)
            contacts.append(d)
        return contacts

    # ── DELETE /api/emergency/contacts/{contact_id} ── Delete emergency contact
    @app.delete("/api/emergency/contacts/{contact_id}")
    def delete_emergency_contact(contact_id: str, current_user: dict = Depends(get_current_user)):
        doc_ref = db.collection("emergency_contacts").document(contact_id)
        doc = doc_ref.get()
        if not doc.exists or doc.to_dict().get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        doc_ref.delete()
        return {"status": "success"}

    # ── POST /api/emergency/sos ── Trigger SOS Alert
    @app.post("/api/emergency/sos")
    def trigger_sos(sos: SOSRequest, current_user: dict = Depends(get_current_user)):
        try:
            data = sos.dict()
            data["patient_id"] = current_user["uid"]
            data["patient_email"] = current_user.get("email", "")
            data["patient_name"] = current_user.get("full_name", "")
            data["status"] = "active"
            data["triggered_at"] = firestore.SERVER_TIMESTAMP

            # Fetch emergency contacts
            contacts = []
            contact_docs = db.collection("emergency_contacts").where("patient_id", "==", current_user["uid"]).stream()
            for doc in contact_docs:
                contacts.append(doc.to_dict())

            # Notifications & Dispatch
            notifs = notify_emergency_contacts(contacts, data["patient_name"], data["location"])
            data["contacts_notified"] = notifs

            if sos.requires_ambulance:
                data["ambulance_info"] = dispatch_ambulance(data["location"], data["patient_id"])

            ref = db.collection("sos_alerts").add(data)
            log_action(current_user, "triggered_sos", {"location": data["location"]})
            
            return {
                "status": "success",
                "alert_id": ref[1].id,
                "ambulance_info": data.get("ambulance_info")
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── GET /api/emergency/active ── Admin/Doctor view active emergencies
    @app.get("/api/emergency/active")
    def get_active_emergencies(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in ["superuser", "admin", "superadmin", "doctor"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        docs = db.collection("sos_alerts").where("status", "==", "active").stream()
        alerts = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            d = serialize_doc(d)
            alerts.append(d)
        
        # Sort by most recent
        alerts.sort(key=lambda x: x.get("triggered_at", ""), reverse=True)
        return alerts

    # ── PATCH /api/emergency/{alert_id} ── Update SOS Alert Status
    @app.patch("/api/emergency/{alert_id}")
    def update_emergency_status(alert_id: str, update: AlertUpdate, current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in ["superuser", "admin", "superadmin", "doctor"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        doc_ref = db.collection("sos_alerts").document(alert_id)
        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        patch = update.dict(exclude_unset=True)
        patch["updated_at"] = firestore.SERVER_TIMESTAMP
        if patch.get("status") == "resolved":
            patch["resolved_at"] = firestore.SERVER_TIMESTAMP
            
        doc_ref.update(patch)
        log_action(current_user, "update_sos", {"alert_id": alert_id, "status": update.status})
        return {"status": "success"}

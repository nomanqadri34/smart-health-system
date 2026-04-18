"""
Patient Medical History Compiler
Aggregates data across vitals, labs, medications, and past appointments to generate full medical history timelines.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, List
from datetime import datetime
from bson import ObjectId

def register_patient_history_routes(app, db, get_current_user, log_action, serialize_doc):

    # ── GET /api/patient/history/{patient_id} ── Complete Medical Record
    @app.get("/api/patient/history/{patient_id}")
    async def get_full_patient_history(patient_id: str, current_user: dict = Depends(get_current_user)):
        # Security Check
        if current_user["role"] not in ["doctor", "superuser", "admin", "superadmin"]:
             if current_user["uid"] != patient_id:
                 raise HTTPException(status_code=403, detail="Can only view your own medical history")
                 
        history = {
            "patient_info": {},
            "allergies": [],
            "chronic_conditions": [],
            "past_surgeries": [],
            "family_history": [],
            "timeline": []
        }

        # 1. User Profile data
        user_query = {"_id": ObjectId(patient_id)} if ObjectId.is_valid(patient_id) else {"uid": patient_id}
        user_doc = await db.users.find_one(user_query)
        if user_doc:
             history["patient_info"] = {
                 "name": user_doc.get("full_name", ""),
                 "email": user_doc.get("email", ""),
                 "date_of_birth": user_doc.get("dob", ""),
                 "blood_group": user_doc.get("blood_group", "Unknown")
             }
             history["allergies"] = user_doc.get("medical_profile", {}).get("allergies", [])
             history["chronic_conditions"] = user_doc.get("medical_profile", {}).get("chronic_conditions", [])
             history["past_surgeries"] = user_doc.get("medical_profile", {}).get("past_surgeries", [])
             history["family_history"] = user_doc.get("medical_profile", {}).get("family_history", [])

        # 2. Collect Appointments
        appt_cursor = db.appointments.find({"patient_id": patient_id})
        async for doc in appt_cursor:
             dt_str = doc.get("date", "") + "T" + doc.get("time", "00:00")
             history["timeline"].append({
                 "type": "appointment",
                 "date": doc.get("date", ""),
                 "timestamp": dt_str,
                 "title": f"Consultation with {doc.get('doctor_name', 'Doctor')}",
                 "details": doc.get("symptoms", ""),
                 "department": doc.get("department", ""),
                 "status": doc.get("status", ""),
                 "id": str(doc["_id"])
             })

        # 3. Collect Lab Reports
        lab_cursor = db.lab_reports.find({"patient_id": patient_id})
        async for doc in lab_cursor:
             history["timeline"].append({
                 "type": "lab_report",
                 "date": doc.get("performed_date", ""),
                 "timestamp": doc.get("performed_date", "") + "T00:00",
                 "title": f"Lab Test: {doc.get('test_name', '')}",
                 "details": doc.get("interpretation", ""),
                 "category": doc.get("test_category", ""),
                 "id": str(doc["_id"])
             })

        # 4. Collect Prescriptions
        rx_cursor = db.prescriptions.find({"patient_id": patient_id})
        async for doc in rx_cursor:
             serialized = serialize_doc(doc)
             issued_at = serialized.get("issued_at", "")
             date_str = issued_at.split(" ")[0] if issued_at else ""
             history["timeline"].append({
                 "type": "prescription",
                 "date": date_str,
                 "timestamp": issued_at,
                 "title": f"Prescription by {doc.get('doctor_name', '')}",
                 "details": f"{len(doc.get('medications', []))} medications prescribed",
                 "diagnosis": doc.get("diagnosis", ""),
                 "id": str(doc["_id"])
             })
             
        # 5. Collect Significant Vitals (Warnings/Critical only to reduce noise)
        vitals_cursor = db.health_vitals.find({"patient_id": patient_id})
        async for doc in vitals_cursor:
             status = doc.get("status_info", {}).get("status", "normal")
             if status in ["warning", "critical"]:
                  recorded_at = doc.get("recorded_at", "")
                  date_str = recorded_at.split("T")[0] if "T" in recorded_at else recorded_at
                  val = doc.get('systolic', '') if doc.get('type')=='blood_pressure' else doc.get('value', '')
                  history["timeline"].append({
                      "type": "vital_alert",
                      "date": date_str,
                      "timestamp": recorded_at,
                      "title": f"Abnormal Vital: {doc.get('type', '')}",
                      "details": f"Value: {val} ({status})",
                      "id": str(doc["_id"])
                  })

        # Sort timeline by timestamp descending
        history["timeline"].sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Log view
        await log_action(current_user, "view_patient_history", {"patient_id": patient_id})
        
        return history

    # ── PATCH /api/patient/profile/{patient_id}/medical ── Update Base Medical Profile
    @app.patch("/api/patient/profile/{patient_id}/medical")
    async def update_medical_profile(patient_id: str, medical_profile: dict, current_user: dict = Depends(get_current_user)):
        if current_user["uid"] != patient_id and current_user["role"] not in ["doctor", "admin", "superadmin", "superuser"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        user_query = {"_id": ObjectId(patient_id)} if ObjectId.is_valid(patient_id) else {"uid": patient_id}
        doc = await db.users.find_one(user_query)
        if not doc:
            raise HTTPException(status_code=404, detail="User not found")
            
        await db.users.update_one(user_query, {
            "$set": {
                "medical_profile": medical_profile,
                "updated_at": datetime.utcnow()
            }
        })
        
        await log_action(current_user, "update_medical_profile", {"patient_id": patient_id})
        return {"status": "success"}

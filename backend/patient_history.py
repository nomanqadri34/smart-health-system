"""
Patient Medical History Compiler
Aggregates data across vitals, labs, medications, and past appointments to generate full medical history timelines.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, List
from datetime import datetime
from firebase_admin import firestore

def register_patient_history_routes(app, db, get_current_user, log_action, serialize_doc):

    # ── GET /api/patient/history/{patient_id} ── Complete Medical Record
    @app.get("/api/patient/history/{patient_id}")
    def get_full_patient_history(patient_id: str, current_user: dict = Depends(get_current_user)):
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
        user_doc = db.collection("users").document(patient_id).get()
        if user_doc.exists:
             user_data = user_doc.to_dict()
             history["patient_info"] = {
                 "name": user_data.get("full_name", ""),
                 "email": user_data.get("email", ""),
                 "date_of_birth": user_data.get("dob", ""),
                 "blood_group": user_data.get("blood_group", "Unknown")
             }
             history["allergies"] = user_data.get("medical_profile", {}).get("allergies", [])
             history["chronic_conditions"] = user_data.get("medical_profile", {}).get("chronic_conditions", [])
             history["past_surgeries"] = user_data.get("medical_profile", {}).get("past_surgeries", [])
             history["family_history"] = user_data.get("medical_profile", {}).get("family_history", [])

        # 2. Collect Appointments
        appts = db.collection("appointments").where("patient_id", "==", patient_id).stream()
        for doc in appts:
             d = doc.to_dict()
             dt_str = d.get("date", "") + "T" + d.get("time", "00:00")
             history["timeline"].append({
                 "type": "appointment",
                 "date": d.get("date", ""),
                 "timestamp": dt_str,
                 "title": f"Consultation with {d.get('doctor_name', 'Doctor')}",
                 "details": d.get("symptoms", ""),
                 "department": d.get("department", ""),
                 "status": d.get("status", ""),
                 "id": doc.id
             })

        # 3. Collect Lab Reports
        labs = db.collection("lab_reports").where("patient_id", "==", patient_id).stream()
        for doc in labs:
             d = doc.to_dict()
             history["timeline"].append({
                 "type": "lab_report",
                 "date": d.get("performed_date", ""),
                 "timestamp": d.get("performed_date", "") + "T00:00",
                 "title": f"Lab Test: {d.get('test_name', '')}",
                 "details": d.get("interpretation", ""),
                 "category": d.get("test_category", ""),
                 "id": doc.id
             })

        # 4. Collect Prescriptions
        rx = db.collection("prescriptions").where("patient_id", "==", patient_id).stream()
        for doc in rx:
             d = doc.to_dict()
             issued_at = serialize_doc(d).get("issued_at", "")
             date_str = issued_at.split(" ")[0] if issued_at else ""
             history["timeline"].append({
                 "type": "prescription",
                 "date": date_str,
                 "timestamp": issued_at,
                 "title": f"Prescription by {d.get('doctor_name', '')}",
                 "details": f"{len(d.get('medications', []))} medications prescribed",
                 "diagnosis": d.get("diagnosis", ""),
                 "id": doc.id
             })
             
        # 5. Collect Significant Vitals (Warnings/Critical only to reduce noise)
        vitals = db.collection("health_vitals").where("patient_id", "==", patient_id).stream()
        for doc in vitals:
             d = doc.to_dict()
             status = d.get("status_info", {}).get("status", "normal")
             if status in ["warning", "critical"]:
                 recorded_at = d.get("recorded_at", "")
                 date_str = recorded_at.split("T")[0] if "T" in recorded_at else recorded_at
                 val = d.get('systolic', '') if d.get('type')=='blood_pressure' else d.get('value', '')
                 history["timeline"].append({
                     "type": "vital_alert",
                     "date": date_str,
                     "timestamp": recorded_at,
                     "title": f"Abnormal Vital: {d.get('type', '')}",
                     "details": f"Value: {val} ({status})",
                     "id": doc.id
                 })

        # Sort timeline by timestamp descending
        history["timeline"].sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Log view
        log_action(current_user, "view_patient_history", {"patient_id": patient_id})
        
        return history

    # ── PATCH /api/patient/profile/{patient_id}/medical ── Update Base Medical Profile
    @app.patch("/api/patient/profile/{patient_id}/medical")
    def update_medical_profile(patient_id: str, medical_profile: dict, current_user: dict = Depends(get_current_user)):
        if current_user["uid"] != patient_id and current_user["role"] not in ["doctor", "admin", "superadmin", "superuser"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        doc_ref = db.collection("users").document(patient_id)
        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail="User not found")
            
        doc_ref.update({
            "medical_profile": medical_profile,
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        
        log_action(current_user, "update_medical_profile", {"patient_id": patient_id})
        return {"status": "success"}

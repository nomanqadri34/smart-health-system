from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import random
from typing import List, Optional
from datetime import datetime, timedelta
import os
import io
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, firestore, auth

from ml_logic import predict_appointment, predict_noshow, recommend_doctors, summarize_notes_with_gemini

app = FastAPI(title="Smart Health API", description="AI-powered Appointment Scheduling")

# CORS Setup
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Firebase Admin Initialization ---
try:
    cred = credentials.Certificate('smart-health-51e3f-firebase-adminsdk-fbsvc-8a5938ff60.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin initialized successfully.")
except Exception as e:
    print(f"Error initializing Firebase Admin: {e}")

# --- Auth Dependency ---
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get('uid')
        
        user_doc = db.collection('users').document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=401, detail="User not found in database")
            
        user_data = user_doc.to_dict()
        return {
            "uid": uid, 
            "role": user_data.get('role', 'patient'), 
            "email": user_data.get('email') or decoded_token.get('email', ''),
            "full_name": user_data.get('full_name', '')
        }
    except Exception as e:
        print(f"Auth error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Auth error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- Audit Log Helper ---
def log_action(user: dict, action: str, details: dict = {}):
    try:
        db.collection('audit_logs').add({
            "uid": user.get('uid'),
            "email": user.get('email'),
            "role": user.get('role'),
            "action": action,
            "details": details,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        print(f"Audit log error: {e}")

def serialize_doc(data: dict) -> dict:
    for key, val in data.items():
        if hasattr(val, 'timestamp'):
            data[key] = str(val)
    return data

@app.get("/")
def read_root():
    return {"message": "Smart Health API is running"}

# --- Pydantic Models ---

class ScheduleRequest(BaseModel):
    appointment_id: str
    doctor_name: str
    doctor_email: EmailStr
    patient_name: str
    patient_email: EmailStr
    date: str
    time: str
    department: str
    triage_priority: str = None
    estimated_duration_minutes: int = 30
    symptoms: str = None
    consultation_fee: float = 0.0
    payment_status: str = "pending"

class SymptomInput(BaseModel):
    symptoms: str
    patient_severity_score: int = 5

class AnalysisResult(BaseModel):
    department: str
    confidence: float
    recommended_doctor: str
    summary: str
    immediate_actions: List[str] = []

class RoleUpdate(BaseModel):
    role: str

class ScheduleSettings(BaseModel):
    days: List[str]
    start_time: str
    end_time: str

class AppointmentUpdate(BaseModel):
    status: str

class BulkStatusUpdate(BaseModel):
    appointment_ids: List[str]
    status: str

class PrescriptionCreate(BaseModel):
    appointment_id: str
    patient_id: str
    patient_name: str
    patient_email: str
    doctor_name: str
    medications: List[dict]  # [{name, dosage, frequency, duration}]
    diagnosis: str
    notes: str = ""
    template_used: str = ""

class ConsultationNote(BaseModel):
    appointment_id: str
    patient_id: str
    patient_name: str
    note: str

class RescheduleRequest(BaseModel):
    appointment_id: str
    new_date: str
    new_time: str
    reason: str = ""

class ReferralCreate(BaseModel):
    appointment_id: str
    patient_id: str
    patient_name: str
    patient_email: str
    referred_to_department: str
    referred_to_doctor: str = ""
    reason: str
    notes: str = ""

class PaymentUpdate(BaseModel):
    payment_status: str
    consultation_fee: float = None

class ChatCreateMessage(BaseModel):
    user_id: str
    doctor_id: str
    initial_message: str

class MessageContent(BaseModel):
    text: str
    sender_id: str

class NoteSummarizeRequest(BaseModel):
    raw_notes: str

class ReviewCreate(BaseModel):
    rating: int  # 1 to 5
    comment: str = ""

# Mock Doctors for ML
DOCTOR_NAMES = {
    "Neurology": ["Dr. Strange", "Dr. Shephard"],
    "General Medicine": ["Dr. House", "Dr. Watson"],
    "Cardiology": ["Dr. Cristina Yang", "Dr. Burke"],
    "Dermatology": ["Dr. Gray", "Dr. Sloan"],
    "Dentistry": ["Dr. Wonka"],
    "Ophthalmology": ["Dr. Cyclops"],
    "Gastroenterology": ["Dr. Hannibal"],
    "Orthopedics": ["Dr. Bone"],
    "ENT": ["Dr. Hear"],
    "Psychiatry": ["Dr. Lecter"]
}

# ===========================================================================
# USER MANAGEMENT
# ===========================================================================

@app.get("/api/users")
def get_users(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    users = []
    docs = db.collection('users').stream()
    for doc in docs:
        user_data = doc.to_dict()
        user_data['id'] = doc.id
        users.append(user_data)
        
    return users

@app.get("/api/doctors")
def get_doctors():
    doctors = []
    docs = db.collection('users').where('role', '==', 'doctor').stream()
    for doc in docs:
        user_data = doc.to_dict()
        user_data['id'] = doc.id
        if 'password' in user_data:
            del user_data['password']
        doctors.append(user_data)
        
    return doctors

@app.patch("/api/users/{user_id}/role")
def update_user_role(user_id: str, role_update: RoleUpdate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        db.collection('users').document(user_id).update({"role": role_update.role})
        log_action(current_user, "update_role", {"target_user": user_id, "new_role": role_update.role})
        return {"status": "success", "message": f"User {user_id} role updated to {role_update.role}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/users/{user_id}/schedule")
def update_user_schedule(user_id: str, settings: ScheduleSettings, current_user: dict = Depends(get_current_user)):
    if current_user['uid'] != user_id and current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        db.collection('users').document(user_id).update({"schedule_settings": settings.dict()})
        log_action(current_user, "update_schedule", {"target_user": user_id})
        return {"status": "success", "message": "Schedule updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        try:
            auth.delete_user(user_id)
        except Exception as auth_error:
            print(f"Auth deletion skipped: {auth_error}")
            
        db.collection('users').document(user_id).delete()
        log_action(current_user, "delete_user", {"deleted_user": user_id})
        return {"status": "success", "message": f"User {user_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===========================================================================
# APPOINTMENTS
# ===========================================================================

@app.get("/api/appointments")
def get_appointments(current_user: dict = Depends(get_current_user)):
    appointments = []
    
    if current_user['role'] in ['superuser', 'admin', 'superadmin']:
        docs = db.collection('appointments').stream()
    elif current_user['role'] == 'doctor':
        docs = db.collection('appointments').where('doctor_email', '==', current_user['email']).stream()
    else:
        docs = db.collection('appointments').where('patient_email', '==', current_user['email']).stream()
        
    for doc in docs:
        appt_data = doc.to_dict()
        appt_data['id'] = doc.id
        appt_data = serialize_doc(appt_data)
        appointments.append(appt_data)
        
    return appointments

@app.patch("/api/appointments/{appointment_id}/status")
def update_appointment_status(appointment_id: str, payload: AppointmentUpdate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        db.collection('appointments').document(appointment_id).update({"status": payload.status})
        log_action(current_user, "update_appointment_status", {"appointment_id": appointment_id, "new_status": payload.status})
        return {"status": "success", "message": f"Appointment {appointment_id} marked as {payload.status}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/appointments/bulk-status")
def bulk_update_appointment_status(payload: BulkStatusUpdate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    updated = 0
    errors = []
    for appt_id in payload.appointment_ids:
        try:
            db.collection('appointments').document(appt_id).update({"status": payload.status})
            updated += 1
        except Exception as e:
            errors.append(str(e))
    
    log_action(current_user, "bulk_update_status", {"count": updated, "status": payload.status})
    return {"status": "success", "updated": updated, "errors": errors}

@app.post("/api/appointments/{appointment_id}/reschedule")
def reschedule_appointment(appointment_id: str, req: RescheduleRequest, current_user: dict = Depends(get_current_user)):
    try:
        appt_ref = db.collection('appointments').document(appointment_id)
        appt_doc = appt_ref.get()
        if not appt_doc.exists:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        appt_ref.update({
            "reschedule_requested": True,
            "reschedule_new_date": req.new_date,
            "reschedule_new_time": req.new_time,
            "reschedule_reason": req.reason,
            "reschedule_status": "pending",
            "reschedule_requested_at": firestore.SERVER_TIMESTAMP,
        })
        log_action(current_user, "reschedule_request", {"appointment_id": appointment_id, "new_date": req.new_date})
        return {"status": "success", "message": "Reschedule request submitted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/appointments/{appointment_id}/reschedule/approve")
def approve_reschedule(appointment_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        appt_ref = db.collection('appointments').document(appointment_id)
        appt_doc = appt_ref.get()
        if not appt_doc.exists:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        data = appt_doc.to_dict()
        new_date = data.get('reschedule_new_date')
        new_time = data.get('reschedule_new_time')
        
        appt_ref.update({
            "date": new_date,
            "time": new_time,
            "reschedule_requested": False,
            "reschedule_status": "approved",
        })
        log_action(current_user, "approve_reschedule", {"appointment_id": appointment_id})
        return {"status": "success", "message": "Reschedule approved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/appointments/{appointment_id}/payment")
def update_appointment_payment(appointment_id: str, payload: PaymentUpdate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        update_data = {"payment_status": payload.payment_status}
        if payload.consultation_fee is not None:
            update_data["consultation_fee"] = payload.consultation_fee
        db.collection('appointments').document(appointment_id).update(update_data)
        log_action(current_user, "update_payment", {"appointment_id": appointment_id, "status": payload.payment_status})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===========================================================================
# PRESCRIPTIONS
# ===========================================================================

@app.post("/api/prescriptions")
def create_prescription(prescription: PrescriptionCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['doctor', 'superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Only doctors can issue prescriptions")
    
    try:
        data = prescription.dict()
        data['doctor_id'] = current_user['uid']
        data['issued_at'] = firestore.SERVER_TIMESTAMP
        data['status'] = 'active'
        
        ref = db.collection('prescriptions').add(data)
        log_action(current_user, "issue_prescription", {"patient": prescription.patient_name})
        return {"status": "success", "prescription_id": ref[1].id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/prescriptions")
def get_prescriptions(current_user: dict = Depends(get_current_user)):
    prescriptions = []
    
    if current_user['role'] in ['superuser', 'admin', 'superadmin']:
        docs = db.collection('prescriptions').stream()
    elif current_user['role'] == 'doctor':
        docs = db.collection('prescriptions').where('doctor_id', '==', current_user['uid']).stream()
    else:
        docs = db.collection('prescriptions').where('patient_email', '==', current_user['email']).stream()
    
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        d = serialize_doc(d)
        prescriptions.append(d)
    
    return prescriptions

@app.get("/api/prescriptions/{prescription_id}")
def get_prescription(prescription_id: str, current_user: dict = Depends(get_current_user)):
    doc = db.collection('prescriptions').document(prescription_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Prescription not found")
    
    d = doc.to_dict()
    d['id'] = doc.id
    d = serialize_doc(d)
    
    # Access control
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        if current_user['role'] == 'doctor' and d.get('doctor_id') != current_user['uid']:
            raise HTTPException(status_code=403, detail="Not authorized")
        if current_user['role'] == 'patient' and d.get('patient_email') != current_user['email']:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    return d

# ===========================================================================
# CONSULTATION NOTES
# ===========================================================================

@app.post("/api/appointments/{appointment_id}/note")
def save_consultation_note(appointment_id: str, note_data: ConsultationNote, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['doctor', 'superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Only doctors can save notes")
    
    try:
        ref = db.collection('appointments').document(appointment_id)
        ref.update({
            "consultation_note": note_data.note,
            "note_updated_at": firestore.SERVER_TIMESTAMP
        })
        log_action(current_user, "add_note", {"appointment": appointment_id})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/appointments/{appointment_id}/review")
def add_appointment_review(appointment_id: str, review_data: ReviewCreate, current_user: dict = Depends(get_current_user)):
    try:
        ref = db.collection('appointments').document(appointment_id)
        apt_doc = ref.get()
        if not apt_doc.exists:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        apt = apt_doc.to_dict()
        
        # Security: only the patient of the appointment can leave a review
        if apt.get('patient_email') != current_user['email'] and current_user['role'] not in ['superuser', 'admin', 'superadmin']:
            raise HTTPException(status_code=403, detail="Not authorized to review this appointment")
            
        if apt.get('status') != 'completed':
            raise HTTPException(status_code=400, detail="Can only review completed appointments")
            
        if apt.get('review'):
            raise HTTPException(status_code=400, detail="Appointment already reviewed")
            
        review_dict = {
            "rating": review_data.rating,
            "comment": review_data.comment,
            "created_at": firestore.SERVER_TIMESTAMP
        }
        
        # 1. Update the appointment with the review
        ref.update({"review": review_dict})
        
        # 2. Update the Doctor's aggregate rating
        doctor_id = apt.get('doctor_id')
        if not doctor_id:
            # Fallback: try to find doctor ID by email if missing
            doctor_email = apt.get('doctor_email')
            docs = db.collection('users').where('email', '==', doctor_email).limit(1).stream()
            for d in docs:
                doctor_id = d.id
                break
                
        if doctor_id:
            doc_ref = db.collection('users').document(doctor_id)
            doctor_doc = doc_ref.get()
            if doctor_doc.exists:
                doc_data = doctor_doc.to_dict()
                current_rating = doc_data.get('rating', 0.0)
                current_count = doc_data.get('total_reviews', 0)
                
                # Calculate new average
                new_count = current_count + 1
                new_rating = ((current_rating * current_count) + review_data.rating) / new_count
                
                doc_ref.update({
                    "rating": round(new_rating, 1),
                    "total_reviews": new_count
                })
        
        log_action(current_user, "add_review", {"appointment": appointment_id, "rating": review_data.rating})
        return {"status": "success", "message": "Review added successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notes")
def get_notes(patient_id: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
    notes = []
    
    if current_user['role'] in ['superuser', 'admin', 'superadmin']:
        docs = db.collection('consultation_notes').stream()
    elif current_user['role'] == 'doctor':
        if patient_id:
            docs = db.collection('consultation_notes').where('doctor_id', '==', current_user['uid']).where('patient_id', '==', patient_id).stream()
        else:
            docs = db.collection('consultation_notes').where('doctor_id', '==', current_user['uid']).stream()
    else:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        d = serialize_doc(d)
        notes.append(d)
    
    return notes

# ===========================================================================
# REFERRALS
# ===========================================================================

@app.post("/api/referrals")
def create_referral(referral: ReferralCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['doctor', 'superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Only doctors can create referrals")
    
    try:
        data = referral.dict()
        data['referring_doctor_id'] = current_user['uid']
        data['referring_doctor_name'] = current_user.get('full_name', current_user['email'])
        data['status'] = 'pending'
        data['created_at'] = firestore.SERVER_TIMESTAMP
        
        ref = db.collection('referrals').add(data)
        log_action(current_user, "create_referral", {"patient": referral.patient_name, "to": referral.referred_to_department})
        return {"status": "success", "referral_id": ref[1].id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/referrals")
def get_referrals(current_user: dict = Depends(get_current_user)):
    referrals = []
    
    if current_user['role'] in ['superuser', 'admin', 'superadmin']:
        docs = db.collection('referrals').stream()
    elif current_user['role'] == 'doctor':
        docs = db.collection('referrals').where('referring_doctor_id', '==', current_user['uid']).stream()
    else:
        docs = db.collection('referrals').where('patient_email', '==', current_user['email']).stream()
    
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        d = serialize_doc(d)
        referrals.append(d)
    
    return referrals

# ===========================================================================
# AUDIT LOGS
# ===========================================================================

@app.get("/api/audit-logs")
def get_audit_logs(
    limit: int = Query(100, le=500),
    current_user: dict = Depends(get_current_user)
):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    logs = []
    docs = db.collection('audit_logs').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit).stream()
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        d = serialize_doc(d)
        logs.append(d)
    
    return logs

# ===========================================================================
# ANALYTICS
# ===========================================================================

@app.get("/api/analytics/overview")
def get_analytics_overview(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Fetch all appointments
    docs = list(db.collection('appointments').stream())
    appointments = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        d = serialize_doc(d)
        appointments.append(d)
    
    # Department utilization
    dept_counts = {}
    for a in appointments:
        dept = a.get('department', 'Unknown')
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
    
    # Status breakdown
    status_counts = {}
    for a in appointments:
        s = a.get('status', 'unknown')
        status_counts[s] = status_counts.get(s, 0) + 1
    
    # Peak hours
    hour_counts = {}
    for a in appointments:
        try:
            hour = int(a.get('time', '00:00').split(':')[0])
            label = f"{hour:02d}:00"
            hour_counts[label] = hour_counts.get(label, 0) + 1
        except:
            pass
    
    # Daily trend (last 14 days based on date field)
    from collections import defaultdict
    daily = defaultdict(int)
    for a in appointments:
        date = a.get('date', '')
        if date:
            daily[date] += 1
    
    # Sort daily
    daily_trend = [{"date": k, "count": v} for k, v in sorted(daily.items())[-14:]]
    
    dept_utilization = [{"department": k, "count": v} for k, v in sorted(dept_counts.items(), key=lambda x: -x[1])]
    peak_hours = [{"hour": k, "count": v} for k, v in sorted(hour_counts.items())]
    
    return {
        "total_appointments": len(appointments),
        "status_breakdown": status_counts,
        "department_utilization": dept_utilization,
        "peak_hours": peak_hours,
        "daily_trend": daily_trend,
    }

@app.get("/api/analytics/revenue")
def get_revenue_analytics(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    docs = list(db.collection('appointments').stream())
    appointments = []
    total_revenue = 0.0
    pending_revenue = 0.0
    
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        d = serialize_doc(d)
        fee = float(d.get('consultation_fee', 0) or 0)
        payment_status = d.get('payment_status', 'pending')
        
        if payment_status == 'paid':
            total_revenue += fee
        else:
            pending_revenue += fee
        
        appointments.append(d)
    
    return {
        "appointments": appointments,
        "total_revenue": round(total_revenue, 2),
        "pending_revenue": round(pending_revenue, 2),
        "total_appointments": len(appointments),
    }

@app.get("/api/analytics/doctor-performance")
def get_doctor_performance(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if current_user['role'] == 'doctor':
        docs = list(db.collection('appointments').where('doctor_email', '==', current_user['email']).stream())
    else:
        docs = list(db.collection('appointments').stream())
    
    # Per-doctor stats
    doctor_stats = {}
    for doc in docs:
        d = doc.to_dict()
        email = d.get('doctor_email', 'unknown')
        name = d.get('doctor_name', email)
        if email not in doctor_stats:
            doctor_stats[email] = {
                "doctor_name": name,
                "doctor_email": email,
                "total_appointments": 0,
                "completed": 0,
                "cancelled": 0,
                "total_duration_minutes": 0,
            }
        doctor_stats[email]['total_appointments'] += 1
        status = d.get('status', '')
        if status == 'completed':
            doctor_stats[email]['completed'] += 1
            doctor_stats[email]['total_duration_minutes'] += int(d.get('estimated_duration_minutes', 30) or 30)
        elif status == 'cancelled':
            doctor_stats[email]['cancelled'] += 1
    
    result = []
    for stats in doctor_stats.values():
        comp = stats['completed']
        stats['avg_duration_minutes'] = round(stats['total_duration_minutes'] / comp, 1) if comp > 0 else 0
        stats['completion_rate'] = round(comp / stats['total_appointments'] * 100, 1) if stats['total_appointments'] > 0 else 0
        result.append(stats)
    
    result.sort(key=lambda x: -x['total_appointments'])
    return result

# ===========================================================================
# ML ENDPOINTS
# ===========================================================================

@app.get("/api/ml/noshow-risk/{appointment_id}")
def get_noshow_risk(appointment_id: str, current_user: dict = Depends(get_current_user)):
    doc = db.collection('appointments').document(appointment_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appt = doc.to_dict()
    appt = serialize_doc(appt)
    risk = predict_noshow(appt)
    return risk

@app.get("/api/ml/noshow-risks")
def get_all_noshow_risks(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if current_user['role'] == 'doctor':
        docs = db.collection('appointments').where('doctor_email', '==', current_user['email']).where('status', '==', 'scheduled').stream()
    else:
        docs = db.collection('appointments').where('status', '==', 'scheduled').stream()
    
    results = []
    for doc in docs:
        appt = doc.to_dict()
        appt['id'] = doc.id
        appt = serialize_doc(appt)
        risk = predict_noshow(appt)
        results.append({**appt, **risk})
    
    results.sort(key=lambda x: -x.get('noshow_risk_score', 0))
    return results

@app.post("/api/ml/recommend-doctors")
async def ml_recommend_doctors(body: SymptomInput, current_user: dict = Depends(get_current_user)):
    prediction = await predict_appointment(body.symptoms)
    dept = prediction['department']
    
    doctors = []
    docs = db.collection('users').where('role', '==', 'doctor').stream()
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        doctors.append(d)
    
    ranked = recommend_doctors(body.symptoms, dept, doctors)
    return {"department": dept, "recommended_doctors": ranked, "prediction": prediction}

# ===========================================================================
# CHATS
# ===========================================================================

@app.get("/api/chats")
def get_chats(current_user: dict = Depends(get_current_user)):
    chats = []
    
    user_docs = db.collection('chats').where('user_id', '==', current_user['uid']).stream()
    for doc in user_docs:
        chat_data = doc.to_dict()
        chat_data['id'] = doc.id
        if 'updated_at' in chat_data and chat_data['updated_at']:
            chat_data['updated_at'] = str(chat_data['updated_at'])
        chats.append(chat_data)
        
    doc_docs = db.collection('chats').where('doctor_id', '==', current_user['uid']).stream()
    for doc in doc_docs:
        chat_data = doc.to_dict()
        chat_data['id'] = doc.id
        if 'updated_at' in chat_data and chat_data['updated_at']:
            chat_data['updated_at'] = str(chat_data['updated_at'])
        if not any(c['id'] == doc.id for c in chats):
            chats.append(chat_data)
            
    chats.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
    return chats

@app.post("/api/chats/{chat_id}/messages")
def send_message(chat_id: str, msg: MessageContent, current_user: dict = Depends(get_current_user)):
    chat_doc = db.collection('chats').document(chat_id).get()
    if not chat_doc.exists:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    chat_data = chat_doc.to_dict()
    if chat_data.get('user_id') != current_user['uid'] and chat_data.get('doctor_id') != current_user['uid'] and current_user['role'] not in ['admin', 'superadmin', 'superuser']:
        raise HTTPException(status_code=403, detail="Not authorized to send messages in this chat")

    new_message = {
        "text": msg.text,
        "sender_id": current_user['uid'],
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    
    try:
        db.collection('chats').document(chat_id).collection('messages').add(new_message)
        db.collection('chats').document(chat_id).update({
            "last_message": msg.text,
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===========================================================================
# ML SYMPTOM ANALYSIS
# ===========================================================================

@app.post("/analyze-symptoms", response_model=AnalysisResult)
async def analyze_symptoms(input_data: SymptomInput):
    prediction = await predict_appointment(input_data.symptoms, input_data.patient_severity_score)
    dept = prediction["department"]
    doctors = DOCTOR_NAMES.get(dept, ["Dr. General"])
    prediction["recommended_doctor"] = random.choice(doctors)
    return prediction

# ===========================================================================
# GEMINI AI ENDPOINTS
# ===========================================================================

@app.post("/api/gemini/summarize-notes")
async def ai_summarize_notes(req: NoteSummarizeRequest, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['doctor', 'superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    summary = await summarize_notes_with_gemini(req.raw_notes)
    return {"summary": summary}

# ===========================================================================
# APPOINTMENT SCHEDULING
# ===========================================================================

@app.post("/api/schedule-appointment")
async def schedule_appointment(
    req: ScheduleRequest, 
    current_user: dict = Depends(get_current_user)
):
    appointment_data = {
        "appointment_id": req.appointment_id,
        "doctor_name": req.doctor_name,
        "doctor_email": req.doctor_email,
        "patient_name": req.patient_name,
        "patient_email": req.patient_email,
        "date": req.date,
        "time": req.time,
        "department": req.department,
        "status": "scheduled",
        "triage_priority": req.triage_priority,
        "estimated_duration_minutes": req.estimated_duration_minutes,
        "symptoms": req.symptoms,
        "consultation_fee": req.consultation_fee,
        "payment_status": req.payment_status,
        "created_at": firestore.SERVER_TIMESTAMP
    }
    
    try:
        doc_ref = db.collection('appointments').document(req.appointment_id)
        doc_ref.set(appointment_data)
        log_action(current_user, "schedule_appointment", {
            "appointment_id": req.appointment_id,
            "patient": req.patient_name,
            "doctor": req.doctor_name
        })
        return {"status": "Scheduled successfully", "appointment_id": req.appointment_id}
    except Exception as e:
        print(f"Firestore Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save appointment to database")

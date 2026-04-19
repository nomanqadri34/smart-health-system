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
from bson import ObjectId
from mongodb_engine import get_db
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
import razorpay

from ml_logic import predict_appointment, predict_noshow, recommend_doctors, summarize_notes_with_gemini

app = FastAPI(title="Smart Health API", description="AI-powered Appointment Scheduling")

# CORS Setup
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MongoDB Initialization ---
db = get_db()
print("MongoDB initialized successfully.")

# --- Auth Setup ---
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Config (loaded from .env)
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-123")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

# SMTP Config
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME", "Smart Health"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

# Razorpay Config
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    
    try:
        # 1. First try to verify as Google ID Token
        if client_id and len(token) > 200: 
            try:
                idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
                email = idinfo['email']
                user_data = await db.users.find_one({"email": email})
            except Exception:
                user_data = None
        else:
            user_data = None

        # 2. If not Google, try as our custom JWT
        if not user_data:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                email = payload.get("sub")
                if email:
                    user_data = await db.users.find_one({"email": email})
            except JWTError:
                user_data = None

        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid token or user not found")
            
        return {
            "uid": str(user_data.get('uid', user_data.get('_id'))), 
            "role": user_data.get('role', 'patient'), 
            "email": user_data.get('email', ''),
            "full_name": user_data.get('full_name', '')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth error: {str(e)}")

# --- Audit Log Helper ---
async def log_action(user: dict, action: str, details: dict = {}):
    try:
        await db.audit_logs.insert_one({
            "uid": user.get('uid'),
            "email": user.get('email'),
            "role": user.get('role'),
            "action": action,
            "details": details,
            "timestamp": datetime.utcnow(),
        })
    except Exception as e:
        print(f"Audit log error: {e}")

def serialize_doc(data: dict) -> dict:
    if not data:
        return data
    if "_id" in data:
        data["id"] = str(data["_id"])
        del data["_id"]
    for key, val in data.items():
        if isinstance(val, datetime):
            data[key] = val.isoformat()
        elif isinstance(val, ObjectId):
            data[key] = str(val)
    return data

# --- Pydantic Models ---

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = 'patient'

class VerifySignupOtpRequest(BaseModel):
    email: EmailStr
    otp: str

class SigninRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str # This is the 6-digit OTP
    new_password: str

class ScheduleRequest(BaseModel):
    appointment_id: str
    doctor_id: str = ""
    patient_id: str = ""
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
    severity_score: int = 0
    notes: Optional[str] = None

class SymptomInput(BaseModel):
    symptoms: str
    patient_severity_score: int = 5

class AnalysisResult(BaseModel):
    department: str
    confidence: float
    recommended_doctor: str
    summary: str
    immediate_actions: List[str] = []
    triage_priority: str = "Medium"
    severity_score: float = 5.0
    estimated_duration_minutes: int = 30
    key_concerns: List[str] = []

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
    doctor_id: str = ""
    patient_id: str = ""
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
    doctor_id: str = ""
    patient_id: str = ""
    patient_id: str
    patient_name: str
    note: str

class RescheduleRequest(BaseModel):
    appointment_id: str
    doctor_id: str = ""
    patient_id: str = ""
    new_date: str
    new_time: str
    reason: str = ""

class ReferralCreate(BaseModel):
    appointment_id: str
    doctor_id: str = ""
    patient_id: str = ""
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
    sender_id: Optional[str] = None

class NoteSummarizeRequest(BaseModel):
    raw_notes: str

class ReviewCreate(BaseModel):
    rating: int  # 1 to 5
    comment: str = ""

class RazorpayOrderRequest(BaseModel):
    amount: float # in INR
    currency: str = "INR"

class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

@app.get("/")
def read_root():
    return {"message": "Smart Health API is running"}

class GoogleAuthRequest(BaseModel):
    credential: str
    role: Optional[str] = 'patient'

@app.post("/api/auth/google")
async def google_auth(auth_req: GoogleAuthRequest):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured on server")
    
    try:
        idinfo = id_token.verify_oauth2_token(auth_req.credential, google_requests.Request(), client_id)
        google_uid = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', '')
        picture = idinfo.get('picture', '')
        
        # Check if user exists
        user = await db.users.find_one({"$or": [{"google_uid": google_uid}, {"email": email}, {"uid": google_uid}]})
        
        if not user:
            # Create new user
            user_obj = {
                "uid": google_uid,
                "google_uid": google_uid,
                "email": email,
                "full_name": name,
                "picture": picture,
                "role": auth_req.role,
                "created_at": datetime.utcnow()
            }
            await db.users.insert_one(user_obj)
            user = user_obj
        else:
            # Update existing user if needed
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login": datetime.utcnow()}})
            
        return serialize_doc(user)
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/signup")
async def signup(req: SignupRequest):
    # 1. Check if user already exists
    existing_user = await db.users.find_one({"email": req.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists with this email")
    
    # 2. Generate OTP and Expiry
    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
    expiry = datetime.utcnow() + timedelta(minutes=10)
    
    # 3. Store in pending_registrations
    hashed_password = pwd_context.hash(req.password)
    pending_reg = {
        "email": req.email,
        "full_name": req.full_name,
        "hashed_password": hashed_password,
        "role": req.role,
        "otp": otp,
        "expires_at": expiry,
        "created_at": datetime.utcnow()
    }
    
    await db.pending_registrations.update_one(
        {"email": req.email},
        {"$set": pending_reg},
        upsert=True
    )
    
    # 4. Send Email
    message = MessageSchema(
        subject="Smart Health - Verify Your Account",
        recipients=[req.email],
        body=f"Welcome! Your verification code for Smart Health is: {otp}. It will expire in 10 minutes.",
        subtype=MessageType.plain
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)
    
    return {"message": "OTP sent to your email. Please verify to complete registration."}

@app.post("/api/auth/verify-signup-otp")
async def verify_signup_otp(req: VerifySignupOtpRequest):
    # 1. Find the pending registration
    pending = await db.pending_registrations.find_one({
        "email": req.email,
        "otp": req.otp,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not pending:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # 2. Create the user
    user_obj = {
        "email": pending["email"],
        "full_name": pending["full_name"],
        "hashed_password": pending["hashed_password"],
        "role": pending["role"],
        "verified": True,
        "created_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_obj)
    user_obj["_id"] = result.inserted_id
    
    # 3. Delete the pending registration
    await db.pending_registrations.delete_one({"_id": pending["_id"]})
    
    # 4. Generate Access Token
    token = create_access_token(data={"sub": pending["email"]})
    return {"user": serialize_doc(user_obj), "access_token": token}

@app.post("/api/auth/signin")
async def signin(req: SigninRequest):
    user = await db.users.find_one({"email": req.email})
    if not user or not pwd_context.verify(req.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token(data={"sub": req.email})
    return {"user": serialize_doc(user), "access_token": token}

@app.post("/api/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    user = await db.users.find_one({"email": req.email})
    if not user:
        # We return success to avoid user enumeration, but don't send email
        return {"message": "If this email is registered, you will receive a reset code."}
    
    # Generate 6-digit code
    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
    expiry = datetime.utcnow() + timedelta(minutes=15)
    
    # Store OTP in user record
    await db.users.update_one({"email": req.email}, {"$set": {"reset_otp": otp, "reset_otp_expiry": expiry}})
    
    # Send Email
    message = MessageSchema(
        subject="Smart Health Password Reset",
        recipients=[req.email],
        body=f"Your password reset code is: {otp}. It will expire in 15 minutes.",
        subtype=MessageType.plain
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)
    
    return {"message": "Reset code sent to your email."}

@app.post("/api/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    user = await db.users.find_one({
        "email": req.email,
        "reset_otp": req.token,
        "reset_otp_expiry": {"$gt": datetime.utcnow()}
    })
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    
    hashed_password = pwd_context.hash(req.new_password)
    await db.users.update_one(
        {"email": req.email}, 
        {
            "$set": {"hashed_password": hashed_password},
            "$unset": {"reset_otp": "", "reset_otp_expiry": ""}
        }
    )
    
    return {"message": "Password updated successfully"}

@app.get("/api/users/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    email = current_user['email']
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(user)

@app.patch("/api/users/profile")
async def update_user_profile(profile_data: dict, current_user: dict = Depends(get_current_user)):
    uid = current_user['uid']
    user_query = {"$or": [{"uid": uid}, {"_id": ObjectId(uid)} if ObjectId.is_valid(uid) else {"_id": uid}]}
    
    result = await db.users.update_one(user_query, {"$set": profile_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    await log_action(current_user, "update_profile", {"fields": list(profile_data.keys())})
    return {"status": "success"}

# --- Pydantic Models ---

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = 'patient'

class SigninRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str # This is the 6-digit OTP
    new_password: str

class ScheduleRequest(BaseModel):
    appointment_id: str
    doctor_id: str = ""
    patient_id: str = ""
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
    severity_score: int = 0
    notes: Optional[str] = None

class SymptomInput(BaseModel):
    symptoms: str
    patient_severity_score: int = 5

class AnalysisResult(BaseModel):
    department: str
    confidence: float
    recommended_doctor: str
    summary: str
    immediate_actions: List[str] = []
    triage_priority: str = "Medium"
    severity_score: float = 5.0
    estimated_duration_minutes: int = 30
    key_concerns: List[str] = []

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
async def get_users(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    users = []
    cursor = db.users.find()
    async for doc in cursor:
        users.append(serialize_doc(doc))
        
    return users

@app.get("/api/doctors")
async def get_doctors():
    doctors = []
    cursor = db.users.find({'role': 'doctor'})
    async for doc in cursor:
        user_data = serialize_doc(doc)
        if 'password' in user_data:
            del user_data['password']
        doctors.append(user_data)
        
    return doctors

@app.patch("/api/users/{user_id}/role")
async def update_user_role(user_id: str, role_update: RoleUpdate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        # Check if user_id is an ObjectId or custom UID string
        query = {"uid": user_id} if not user_id.isalnum() else {"$or": [{"uid": user_id}, {"_id": ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id}]}
        
        await db.users.update_one(query, {"$set": {"role": role_update.role}})
        await log_action(current_user, "update_role", {"target_user": user_id, "new_role": role_update.role})
        return {"status": "success", "message": f"User {user_id} role updated to {role_update.role}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/users/{user_id}/schedule")
async def update_user_schedule(user_id: str, settings: ScheduleSettings, current_user: dict = Depends(get_current_user)):
    if current_user['uid'] != user_id and current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        query = {"uid": user_id}
        await db.users.update_one(query, {"$set": {"schedule_settings": settings.dict()}})
        await log_action(current_user, "update_schedule", {"target_user": user_id})
        return {"status": "success", "message": "Schedule updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        # Note: Firebase auth deletion commented out or moved to a service if still used
        # For now, focus on DB
        await db.users.delete_one({"uid": user_id})
        await log_action(current_user, "delete_user", {"deleted_user": user_id})
        return {"status": "success", "message": f"User {user_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===========================================================================
# APPOINTMENTS
# ===========================================================================

@app.get("/api/appointments")
async def get_appointments(current_user: dict = Depends(get_current_user)):
    appointments = []
    
    query = {}
    if current_user['role'] in ['superuser', 'admin', 'superadmin']:
        query = {}
    elif current_user['role'] == 'doctor':
        query = {'doctor_email': current_user['email']}
    else:
        query = {'patient_email': current_user['email']}
        
    cursor = db.appointments.find(query)
    async for doc in cursor:
        appointments.append(serialize_doc(doc))
        
    return appointments

@app.patch("/api/appointments/{appointment_id}/status")
async def update_appointment_status(appointment_id: str, payload: AppointmentUpdate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        query = {"_id": ObjectId(appointment_id)} if ObjectId.is_valid(appointment_id) else {"appointment_id": appointment_id}
        await db.appointments.update_one(query, {"$set": {"status": payload.status}})
        await log_action(current_user, "update_appointment_status", {"appointment_id": appointment_id, "new_status": payload.status})
        return {"status": "success", "message": f"Appointment {appointment_id} marked as {payload.status}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/appointments/bulk-status")
async def bulk_update_appointment_status(payload: BulkStatusUpdate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    updated = 0
    errors = []
    for appt_id in payload.appointment_ids:
        try:
            query = {"_id": ObjectId(appt_id)} if ObjectId.is_valid(appt_id) else {"appointment_id": appt_id}
            await db.appointments.update_one(query, {"$set": {"status": payload.status}})
            updated += 1
        except Exception as e:
            errors.append(str(e))
    
    await log_action(current_user, "bulk_update_status", {"count": updated, "status": payload.status})
    return {"status": "success", "updated": updated, "errors": errors}

@app.post("/api/appointments/{appointment_id}/reschedule")
async def reschedule_appointment(appointment_id: str, req: RescheduleRequest, current_user: dict = Depends(get_current_user)):
    try:
        query = {"_id": ObjectId(appointment_id)} if ObjectId.is_valid(appointment_id) else {"appointment_id": appointment_id}
        appt_doc = await db.appointments.find_one(query)
        if not appt_doc:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        await db.appointments.update_one(query, {"$set": {
            "reschedule_requested": True,
            "reschedule_new_date": req.new_date,
            "reschedule_new_time": req.new_time,
            "reschedule_reason": req.reason,
            "reschedule_status": "pending",
            "reschedule_requested_at": datetime.utcnow(),
        }})
        await log_action(current_user, "reschedule_request", {"appointment_id": appointment_id, "new_date": req.new_date})
        return {"status": "success", "message": "Reschedule request submitted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/appointments/{appointment_id}/reschedule/approve")
async def approve_reschedule(appointment_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        query = {"_id": ObjectId(appointment_id)} if ObjectId.is_valid(appointment_id) else {"appointment_id": appointment_id}
        appt_doc = await db.appointments.find_one(query)
        if not appt_doc:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        new_date = appt_doc.get('reschedule_new_date')
        new_time = appt_doc.get('reschedule_new_time')
        
        await db.appointments.update_one(query, {"$set": {
            "date": new_date,
            "time": new_time,
            "reschedule_requested": False,
            "reschedule_status": "approved",
        }})
        await log_action(current_user, "approve_reschedule", {"appointment_id": appointment_id})
        return {"status": "success", "message": "Reschedule approved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/appointments/{appointment_id}/payment")
async def update_appointment_payment(appointment_id: str, payload: PaymentUpdate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        update_data = {"payment_status": payload.payment_status}
        if payload.consultation_fee is not None:
            update_data["consultation_fee"] = payload.consultation_fee
            
        query = {"_id": ObjectId(appointment_id)} if ObjectId.is_valid(appointment_id) else {"appointment_id": appointment_id}
        await db.appointments.update_one(query, {"$set": update_data})
        await log_action(current_user, "update_payment", {"appointment_id": appointment_id, "status": payload.payment_status})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===========================================================================
# PRESCRIPTIONS
# ===========================================================================

@app.post("/api/prescriptions")
async def create_prescription(prescription: PrescriptionCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['doctor', 'superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Only doctors can issue prescriptions")
    
    try:
        data = prescription.dict()
        data['doctor_id'] = current_user['uid']
        data['issued_at'] = datetime.utcnow()
        data['status'] = 'active'
        
        result = await db.prescriptions.insert_one(data)
        await log_action(current_user, "issue_prescription", {"patient": prescription.patient_name})
        return {"status": "success", "prescription_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/prescriptions")
async def get_prescriptions(current_user: dict = Depends(get_current_user)):
    prescriptions = []
    
    query = {}
    if current_user['role'] in ['superuser', 'admin', 'superadmin']:
        query = {}
    elif current_user['role'] == 'doctor':
        query = {'doctor_id': current_user['uid']}
    else:
        query = {'patient_email': current_user['email']}
    
    cursor = db.prescriptions.find(query)
    async for doc in cursor:
        prescriptions.append(serialize_doc(doc))
    
    return prescriptions

@app.get("/api/prescriptions/{prescription_id}")
async def get_prescription(prescription_id: str, current_user: dict = Depends(get_current_user)):
    query = {"_id": ObjectId(prescription_id)} if ObjectId.is_valid(prescription_id) else {"prescription_id": prescription_id}
    doc = await db.prescriptions.find_one(query)
    if not doc:
        raise HTTPException(status_code=404, detail="Prescription not found")
    
    d = serialize_doc(doc)
    
    # Access control
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        if current_user['role'] == 'doctor' and d.get('doctor_id') != current_user['uid']:
            raise HTTPException(status_code=403, detail="Not authorized")
        if current_user['role'] == 'patient' and d.get('patient_email') != current_user['email']:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    return d
    
    return d

# ===========================================================================
# CONSULTATION NOTES
# ===========================================================================

@app.post("/api/appointments/{appointment_id}/note")
async def save_consultation_note(appointment_id: str, note_data: ConsultationNote, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['doctor', 'superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Only doctors can save notes")
    
    try:
        query = {"_id": ObjectId(appointment_id)} if ObjectId.is_valid(appointment_id) else {"appointment_id": appointment_id}
        await db.appointments.update_one(query, {
            "$set": {
                "consultation_note": note_data.note,
                "note_updated_at": datetime.utcnow()
            }
        })
        await log_action(current_user, "add_note", {"appointment": appointment_id})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/appointments/{appointment_id}/review")
async def add_appointment_review(appointment_id: str, review_data: ReviewCreate, current_user: dict = Depends(get_current_user)):
    try:
        query = {"_id": ObjectId(appointment_id)} if ObjectId.is_valid(appointment_id) else {"appointment_id": appointment_id}
        apt = await db.appointments.find_one(query)
        if not apt:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
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
            "created_at": datetime.utcnow()
        }
        
        # 1. Update the appointment with the review
        await db.appointments.update_one(query, {"$set": {"review": review_dict}})
        
        # 2. Update the Doctor's aggregate rating
        doctor_id = apt.get('doctor_id')
        if not doctor_id:
            # Fallback: try to find doctor ID by email if missing
            doctor_email = apt.get('doctor_email')
            doc = await db.users.find_one({'email': doctor_email, 'role': 'doctor'})
            if doc:
                doctor_id = str(doc.get('uid', doc.get('_id')))
                
        if doctor_id:
            doctor_doc = await db.users.find_one({"$or": [{"uid": doctor_id}, {"_id": ObjectId(doctor_id) if ObjectId.is_valid(doctor_id) else doctor_id}]})
            if doctor_doc:
                current_rating = doctor_doc.get('rating', 0.0)
                current_count = doctor_doc.get('total_reviews', 0)
                
                # Calculate new average
                new_count = current_count + 1
                new_rating = ((float(current_rating) * current_count) + review_data.rating) / new_count
                
                await db.users.update_one({"_id": doctor_doc["_id"]}, {
                    "$set": {
                        "rating": round(new_rating, 1),
                        "total_reviews": new_count
                    }
                })
        
        await log_action(current_user, "add_review", {"appointment": appointment_id, "rating": review_data.rating})
        return {"status": "success", "message": "Review added successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notes")
async def get_notes(patient_id: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
    notes = []
    
    query = {}
    if current_user['role'] in ['superuser', 'admin', 'superadmin']:
        query = {}
    elif current_user['role'] == 'doctor':
        query = {'doctor_id': current_user['uid']}
        if patient_id:
            query['patient_id'] = patient_id
    else:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    cursor = db.consultation_notes.find(query)
    async for doc in cursor:
        notes.append(serialize_doc(doc))
    
    return notes

# ===========================================================================
# REFERRALS
# ===========================================================================

@app.post("/api/referrals")
async def create_referral(referral: ReferralCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['doctor', 'superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Only doctors can create referrals")
    
    try:
        data = referral.dict()
        data['referring_doctor_id'] = current_user['uid']
        data['referring_doctor_name'] = current_user.get('full_name', current_user['email'])
        data['status'] = 'pending'
        data['created_at'] = datetime.utcnow()
        
        result = await db.referrals.insert_one(data)
        await log_action(current_user, "create_referral", {"patient": referral.patient_name, "to": referral.referred_to_department})
        return {"status": "success", "referral_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/referrals")
async def get_referrals(current_user: dict = Depends(get_current_user)):
    referrals = []
    
    query = {}
    if current_user['role'] in ['superuser', 'admin', 'superadmin']:
        query = {}
    elif current_user['role'] == 'doctor':
        query = {'referring_doctor_id': current_user['uid']}
    else:
        query = {'patient_email': current_user['email']}
    
    cursor = db.referrals.find(query)
    async for doc in cursor:
        referrals.append(serialize_doc(doc))
    
    return referrals

# ===========================================================================
# AUDIT LOGS
# ===========================================================================

@app.get("/api/audit-logs")
async def get_audit_logs(
    limit: int = Query(100, le=500),
    current_user: dict = Depends(get_current_user)
):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    logs = []
    cursor = db.audit_logs.find().sort('timestamp', -1).limit(limit)
    async for doc in cursor:
        logs.append(serialize_doc(doc))
    
    return logs

# ===========================================================================
# ANALYTICS
# ===========================================================================

@app.get("/api/analytics/overview")
async def get_analytics_overview(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Fetch all appointments
    cursor = db.appointments.find()
    appointments = []
    async for doc in cursor:
        appointments.append(serialize_doc(doc))
    
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
async def get_revenue_analytics(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    cursor = db.appointments.find()
    appointments = []
    total_revenue = 0.0
    pending_revenue = 0.0
    
    async for doc in cursor:
        d = serialize_doc(doc)
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
async def get_doctor_performance(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    query = {}
    if current_user['role'] == 'doctor':
        query = {'doctor_email': current_user['email']}
    
    cursor = db.appointments.find(query)
    
    # Per-doctor stats
    doctor_stats = {}
    async for doc in cursor:
        d = serialize_doc(doc)
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
async def get_noshow_risk(appointment_id: str, current_user: dict = Depends(get_current_user)):
    query = {"_id": ObjectId(appointment_id)} if ObjectId.is_valid(appointment_id) else {"appointment_id": appointment_id}
    appt = await db.appointments.find_one(query)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    risk = predict_noshow(serialize_doc(appt))
    return risk

@app.get("/api/ml/noshow-risks")
async def get_all_noshow_risks(current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    query = {'status': 'scheduled'}
    if current_user['role'] == 'doctor':
        query['doctor_email'] = current_user['email']
    
    cursor = db.appointments.find(query)
    
    results = []
    async for doc in cursor:
        appt = serialize_doc(doc)
        risk = predict_noshow(appt)
        results.append({**appt, **risk})
    
    results.sort(key=lambda x: -x.get('noshow_risk_score', 0))
    return results

@app.post("/api/ml/recommend-doctors")
async def ml_recommend_doctors(body: SymptomInput, current_user: dict = Depends(get_current_user)):
    prediction = await predict_appointment(body.symptoms)
    dept = prediction['department']
    
    doctors = []
    cursor = db.users.find({"role": "doctor"})
    async for doc in cursor:
        doctors.append(serialize_doc(doc))
    
    ranked = recommend_doctors(body.symptoms, dept, doctors)
    return {"department": dept, "recommended_doctors": ranked, "prediction": prediction}

# ===========================================================================
# CHATS
# ===========================================================================

@app.get("/api/chats")
async def get_chats(current_user: dict = Depends(get_current_user)):
    chats = []
    uid = str(current_user['uid'])
    # Query for chats where the user is either the patient or the doctor
    # We check both patient_id and doctor_id fields
    cursor = db.chats.find({"$or": [{"patient_id": uid}, {"doctor_id": uid}, {"user_id": uid}]})
    async for doc in cursor:
        chat_data = serialize_doc(doc)
        
        # Check if unlocked for patient
        if current_user['role'] == 'patient':
            paid_appt = await db.appointments.find_one({
                "patient_id": uid,
                "doctor_id": chat_data.get("doctor_id"),
                "payment_status": "paid"
            })
            chat_data['is_unlocked'] = paid_appt is not None
        else:
            # Doctors/Admins always see unlocked
            chat_data['is_unlocked'] = True
            
        chats.append(chat_data)
            
    chats.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
    return chats

class ChatCreateRequest(BaseModel):
    target_id: str  # The ID of the person to chat with
    target_name: str
    target_role: str = 'doctor' # 'doctor' or 'patient'

@app.post("/api/chats")
async def create_chat(req: ChatCreateRequest, current_user: dict = Depends(get_current_user)):
    uid = str(current_user['uid'])
    
    # Determine roles
    if req.target_role == 'doctor':
        doctor_id = req.target_id
        patient_id = uid
        doctor_name = req.target_name
        patient_name = current_user.get('full_name', 'Patient')
    else:
        doctor_id = uid
        patient_id = req.target_id
        doctor_name = current_user.get('full_name', 'Doctor')
        patient_name = req.target_name

    # Check if exists
    existing = await db.chats.find_one({
        "doctor_id": doctor_id,
        "patient_id": patient_id
    })
    
    if existing:
        return serialize_doc(existing)
        
    new_chat = {
        "doctor_id": doctor_id,
        "patient_id": patient_id,
        "doctor_name": doctor_name,
        "patient_name": patient_name,
        "last_message": "",
        "updated_at": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "unread_count": 0,
        "is_encrypted": True # UI flag for requested "professional" feel
    }
    
    result = await db.chats.insert_one(new_chat)
    new_chat["_id"] = result.inserted_id
    return serialize_doc(new_chat)

@app.post("/api/chats/{chat_id}/messages")
async def send_message(chat_id: str, msg: MessageContent, current_user: dict = Depends(get_current_user)):
    query = {"_id": ObjectId(chat_id)} if ObjectId.is_valid(chat_id) else {"chat_id": chat_id}
    chat_data = await db.chats.find_one(query)
    if not chat_data:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    uid = str(current_user['uid'])
    chat_patient_id = str(chat_data.get('patient_id', chat_data.get('user_id', '')))
    chat_doctor_id = str(chat_data.get('doctor_id', ''))
    
    if uid not in [chat_patient_id, chat_doctor_id] and current_user['role'] not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized for this secure channel")

    # Payment Restriction: Patients must have at least one PAID appointment with the doctor
    if current_user['role'] == 'patient':
        # Admin/Superuser can bypass for support
        paid_appt = await db.appointments.find_one({
            "patient_id": uid,
            "doctor_id": chat_doctor_id,
            "payment_status": "paid"
        })
        if not paid_appt:
            raise HTTPException(
                status_code=402, 
                detail="Consultation fee payment required to unlock messaging with this doctor."
            )

    now = datetime.utcnow()
    new_message = {
        "chat_id": chat_id,
        "content": msg.text,
        "sender_id": uid,
        "created_at": now
    }
    
    try:
        await db.messages.insert_one(new_message)
        await db.chats.update_one(query, {
            "$set": {
                "last_message": msg.text,
                "updated_at": now
            }
        })
        return {"status": "success"}
    except Exception as e:
        print(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: str, current_user: dict = Depends(get_current_user)):
    query = {"_id": ObjectId(chat_id)} if ObjectId.is_valid(chat_id) else {"chat_id": chat_id}
    chat_data = await db.chats.find_one(query)
    if not chat_data:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    uid = str(current_user['uid'])
    chat_patient_id = str(chat_data.get('patient_id', chat_data.get('user_id', '')))
    chat_doctor_id = str(chat_data.get('doctor_id', ''))
    
    if uid not in [chat_patient_id, chat_doctor_id] and current_user['role'] not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized to view this secure channel")
        
    messages = []
    cursor = db.messages.find({"chat_id": chat_id}).sort("created_at", 1)
    async for doc in cursor:
        messages.append(serialize_doc(doc))
        
    return messages

# ===========================================================================
# ML SYMPTOM ANALYSIS
# ===========================================================================

@app.post("/analyze-symptoms", response_model=AnalysisResult)
async def analyze_symptoms(input_data: SymptomInput):
    try:
        prediction = await predict_appointment(input_data.symptoms, input_data.patient_severity_score)
        dept = prediction["department"]
        doctors = DOCTOR_NAMES.get(dept, ["Dr. General"])
        prediction["recommended_doctor"] = random.choice(doctors)
        return prediction
    except Exception as e:
        print(f"Error in /analyze-symptoms: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Symptom analysis failed: {str(e)}")

# ===========================================================================
# GEMINI AI ENDPOINTS
# ===========================================================================

@app.post("/api/gemini/summarize-notes")
async def ai_summarize_notes(req: NoteSummarizeRequest, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['doctor', 'superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    summary = await summarize_notes_with_gemini(req.raw_notes)
    return {"summary": summary}

class DeepAnalysisRequest(BaseModel):
    symptoms: str = ""
    department: str = "General Medicine"
    triage_priority: str = "Medium"
    severity_score: Optional[float] = 5.0

@app.post("/api/gemini/deep-analysis")
async def gemini_deep_analysis(req: DeepAnalysisRequest):
    """
    Generates a rich, patient-friendly narrative analysis using Gemini AI.
    Returns detailed health insights, lifestyle advice, and consultation tips.
    """
    from ml_logic import model as gemini_model
    
    severity = int(req.severity_score or 5)
    prompt = f"""
    You are a compassionate and expert medical AI assistant. A patient has reported the following:
    - Symptoms: {req.symptoms}
    - Recommended Department: {req.department}
    - Triage Priority: {req.triage_priority}
    - Self-Reported Severity: {severity}/10

    Provide a comprehensive, patient-friendly health analysis report in strict JSON format with EXACTLY these keys:
    - "narrative": A warm, 3-4 sentence paragraph explaining what these symptoms might suggest in plain language. Do not use medical jargon excessively.
    - "lifestyle_advice": A list of 3-4 specific lifestyle changes or home care tips directly related to the symptoms.
    - "warning_signs": A list of 3 specific red-flag symptoms that should prompt the patient to seek emergency care immediately.
    - "questions_for_doctor": A list of 3-4 smart questions the patient should ask their doctor during the consultation.
    - "diet_tips": A list of 2-3 dietary recommendations that may help alleviate or not worsen the symptoms.
    - "mental_health_note": A single encouraging sentence acknowledging the patient's concern and reassuring them.

    Return ONLY the valid JSON object. Be helpful, warm, and clear.
    """
    
    try:
        if gemini_model is None:
            raise ValueError("Gemini model not initialized")
        
        response = gemini_model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean markdown fences if present
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()
        
        import json
        data = json.loads(text)
        return {
            "narrative": data.get("narrative", "Our AI has analyzed your symptoms and routed you to the best specialist."),
            "lifestyle_advice": data.get("lifestyle_advice", ["Rest well", "Stay hydrated", "Monitor symptoms"]),
            "warning_signs": data.get("warning_signs", ["Severe worsening of symptoms", "High fever", "Difficulty breathing"]),
            "questions_for_doctor": data.get("questions_for_doctor", ["What is the most likely diagnosis?", "What tests do I need?"]),
            "diet_tips": data.get("diet_tips", ["Stay hydrated", "Avoid processed foods"]),
            "mental_health_note": data.get("mental_health_note", "It is great that you are taking care of your health. You are in good hands.")
        }
    except Exception as e:
        print(f"Gemini Deep Analysis Error: {e}")
        raise HTTPException(status_code=500, detail=f"Gemini analysis failed: {str(e)}")


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
        "doctor_id": req.doctor_id,
        "patient_name": req.patient_name,
        "patient_email": req.patient_email,
        "patient_id": req.patient_id,
        "date": req.date,
        "time": req.time,
        "department": req.department,
        "status": "scheduled",
        "triage_priority": req.triage_priority,
        "estimated_duration_minutes": req.estimated_duration_minutes,
        "symptoms": req.symptoms,
        "consultation_fee": req.consultation_fee,
        "payment_status": req.payment_status,
        "severity_score": req.severity_score,
        "notes": req.notes,
        "created_at": datetime.utcnow()
    }
    
    try:
        # Use appointment_id as _id or as a field
        await db.appointments.update_one(
            {"appointment_id": req.appointment_id}, 
            {"$set": appointment_data}, 
            upsert=True
        )
        await log_action(current_user, "schedule_appointment", {
            "appointment_id": req.appointment_id,
            "patient": req.patient_name,
            "doctor": req.doctor_name
        })
        return {"status": "Scheduled successfully", "appointment_id": req.appointment_id}
    except Exception as e:
        print(f"MongoDB Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save appointment to database")

# ===========================================================================
# RAZORPAY PAYMENT GATEWAY
# ===========================================================================

@app.post("/api/razorpay/create-order")
async def create_razorpay_order(req: RazorpayOrderRequest, current_user: dict = Depends(get_current_user)):
    try:
        # Amount must be in paise (ps)
        amount_paise = int(req.amount * 100)
        
        data = {
            "amount": amount_paise,
            "currency": req.currency,
            "receipt": f"receipt_{random.randint(1000, 9999)}",
            "payment_capture": 1 # Auto capture
        }
        
        order = razorpay_client.order.create(data=data)
        return order
    except Exception as e:
        print(f"Razorpay Order Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/razorpay/verify-payment")
async def verify_razorpay_payment(req: RazorpayVerifyRequest, current_user: dict = Depends(get_current_user)):
    try:
        # Verify signature
        params_dict = {
            'razorpay_order_id': req.razorpay_order_id,
            'razorpay_payment_id': req.razorpay_payment_id,
            'razorpay_signature': req.razorpay_signature
        }
        
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Payment is authentic
        await log_action(current_user, "payment_verified", {"payment_id": req.razorpay_payment_id})
        return {"status": "success", "message": "Payment verified successfully"}
    except Exception as e:
        print(f"Razorpay Verification Error: {e}")
        raise HTTPException(status_code=400, detail="Payment verification failed")

# Import notification and cache services
from notification_service import NotificationService
from cache_service import CacheService

# Initialize services
notification_service = NotificationService()
cache_service = CacheService()

# Import content classifier and rate limiter
from content_classifier import ContentClassifier
from rate_limiter import RateLimiter

# Initialize services
content_classifier = ContentClassifier()
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

# Import Data Validation System
from data_validator import *
from data_sanitizer import *

# Session Management
from session_manager import *
from session_store import *

# API Authentication
from auth_handler import *
from token_manager import *

# File Upload System
from file_uploader import *
from file_validator import *

# Search Engine
from search_indexer import *
from search_query import *

# Backup System
from backup_manager import *
from backup_scheduler import *

# ============================================
# API Auth v2 System Integration
# ============================================
from auth_handler_v2 import AuthHandler
from token_manager_v2 import TokenManager

# Initialize API Auth v2 services
auth_handler_v2_service = AuthHandler(config={"enabled": True})
token_manager_v2_service = TokenManager(config={"enabled": True})


# ============================================
# File Upload v2 System Integration
# ============================================
from file_uploader_v2 import FileUploader
from file_validator_v2 import FileValidator

# Initialize File Upload v2 services
file_uploader_v2_service = FileUploader(config={"enabled": True})
file_validator_v2_service = FileValidator(config={"enabled": True})


# ============================================
# Search v2 System Integration
# ============================================
from search_indexer_v2 import SearchIndexer
from search_query_v2 import SearchQuery

# Initialize Search v2 services
search_indexer_v2_service = SearchIndexer(config={"enabled": True})
search_query_v2_service = SearchQuery(config={"enabled": True})

# ===========================================================================
# NEW MODULE ROUTE REGISTRATIONS
# ===========================================================================

from health_vitals import register_vitals_routes
from lab_reports import register_lab_report_routes
from medication_reminders import register_medication_routes
from emergency_alerts import register_emergency_routes
from doctor_availability import register_availability_routes
from health_goals import register_health_goals_routes
from telemedicine import register_telemedicine_routes
from patient_history import register_patient_history_routes
from appointment_waitlist import register_waitlist_routes
from health_analytics_ml import register_health_analytics_routes

# Register all routes onto the FastAPI app
register_vitals_routes(app, db, get_current_user, log_action, serialize_doc)
register_lab_report_routes(app, db, get_current_user, log_action, serialize_doc)
register_medication_routes(app, db, get_current_user, log_action, serialize_doc)
register_emergency_routes(app, db, get_current_user, log_action, serialize_doc)
register_availability_routes(app, db, get_current_user, log_action, serialize_doc)
register_health_goals_routes(app, db, get_current_user, log_action, serialize_doc)
register_telemedicine_routes(app, db, get_current_user, log_action, serialize_doc)
register_patient_history_routes(app, db, get_current_user, log_action, serialize_doc)
register_waitlist_routes(app, db, get_current_user, log_action, serialize_doc)
register_health_analytics_routes(app, db, get_current_user, log_action, serialize_doc)


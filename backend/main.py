from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import random
from typing import List
from datetime import datetime, timedelta

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from icalendar import Calendar, Event, vText
from apscheduler.schedulers.background import BackgroundScheduler
import os
import io
from starlette.datastructures import UploadFile
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, firestore, auth

from ml_logic import predict_appointment

app = FastAPI(title="Smart Health API", description="AI-powered Appointment Scheduling (ML Only)")

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
        
        # Fetch user role from Firestore
        user_doc = db.collection('users').document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=401, detail="User not found in database")
            
        user_data = user_doc.to_dict()
        return {
            "uid": uid, 
            "role": user_data.get('role', 'patient'), 
            "email": user_data.get('email') or decoded_token.get('email', '')
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

@app.get("/")
def read_root():
    return {"message": "Smart Health API is running (ML + Scheduling)"}

# --- Email & Scheduling Configuration ---

# Use a free Gmail account or App Password for testing. 
# For production, these should be loaded from .env
MAIL_CONF = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", "dummy@gmail.com"), 
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", "dummy_password"),
    MAIL_FROM=os.getenv("MAIL_FROM", "donotreply@smarthealth.com"),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

fm = FastMail(MAIL_CONF)

# Initialize Scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Stop scheduler when shutting down app
@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

class ScheduleRequest(BaseModel):
    appointment_id: str
    doctor_name: str
    doctor_email: EmailStr
    patient_name: str
    patient_email: EmailStr
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    department: str
    triage_priority: str = None
    estimated_duration_minutes: int = 30
    symptoms: str = None

class SymptomInput(BaseModel):
    symptoms: str

class AnalysisResult(BaseModel):
    department: str
    confidence: float
    recommended_doctor: str
    summary: str

# Mock Doctors for ML recommendation (names only, no DB)
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

# --- User Management (Super Admin) ---

class RoleUpdate(BaseModel):
    role: str

class ScheduleSettings(BaseModel):
    days: List[str]
    start_time: str
    end_time: str

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
        # Avoid sending sensitive data
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
        return {"status": "success", "message": f"User {user_id} role updated to {role_update.role}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/users/{user_id}/schedule")
def update_user_schedule(user_id: str, settings: ScheduleSettings, current_user: dict = Depends(get_current_user)):
    # Only allow the user themselves or an admin to update their schedule
    if current_user['uid'] != user_id and current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        db.collection('users').document(user_id).update({"schedule_settings": settings.dict()})
        return {"status": "success", "message": "Schedule updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        try:
            # Delete from auth if they exist
            auth.delete_user(user_id)
        except Exception as auth_error:
            print(f"Auth deletion skipped (might solely be in DB): {auth_error}")
            
        # Delete from firestore regardless
        db.collection('users').document(user_id).delete()
        return {"status": "success", "message": f"User {user_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Appointments API ---

@app.get("/api/appointments")
def get_appointments(current_user: dict = Depends(get_current_user)):
    appointments = []
    
    print(f"DEBUG: get_appointments called by {current_user['email']} (Role: {current_user['role']})")
    
    # Super admins see all
    if current_user['role'] in ['superuser', 'admin', 'superadmin']:
        print("DEBUG: Fetching all appointments for superadmin")
        docs = db.collection('appointments').stream()
    # Doctors see appointments where their email matches
    elif current_user['role'] == 'doctor':
        print(f"DEBUG: Fetching appointments for doctor {current_user['email']}")
        docs = db.collection('appointments').where('doctor_email', '==', current_user['email']).stream()
    # Patients see appointments where their email matches
    else:
        print(f"DEBUG: Fetching appointments for patient {current_user['email']}")
        docs = db.collection('appointments').where('patient_email', '==', current_user['email']).stream()
        
    for doc in docs:
        appt_data = doc.to_dict()
        appt_data['id'] = doc.id
        
        # FastAPI cannot serialize DatetimeWithNanoseconds automatically
        for key, val in appt_data.items():
            if hasattr(val, 'timestamp'):  # catches DatetimeWithNanoseconds and datetimes
                appt_data[key] = str(val)
                
        appointments.append(appt_data)
        
    print(f"DEBUG: Returning {len(appointments)} appointments")
    return appointments

class AppointmentUpdate(BaseModel):
    status: str

@app.patch("/api/appointments/{appointment_id}/status")
def update_appointment_status(appointment_id: str, payload: AppointmentUpdate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] not in ['superuser', 'admin', 'superadmin', 'doctor']:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        db.collection('appointments').document(appointment_id).update({"status": payload.status})
        return {"status": "success", "message": f"Appointment {appointment_id} marked as {payload.status}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Chats API ---

class ChatCreateMessage(BaseModel):
    user_id: str
    doctor_id: str
    initial_message: str

@app.get("/api/chats")
def get_chats(current_user: dict = Depends(get_current_user)):
    """Fetch all chats involving the current user (either as patient or doctor)"""
    chats = []
    
    # Check if they are listed as user_id
    user_docs = db.collection('chats').where('user_id', '==', current_user['uid']).stream()
    for doc in user_docs:
        chat_data = doc.to_dict()
        chat_data['id'] = doc.id
        if 'updated_at' in chat_data and chat_data['updated_at']:
            chat_data['updated_at'] = str(chat_data['updated_at'])
        chats.append(chat_data)
        
    # Check if they are listed as doctor_id
    doc_docs = db.collection('chats').where('doctor_id', '==', current_user['uid']).stream()
    for doc in doc_docs:
        chat_data = doc.to_dict()
        chat_data['id'] = doc.id
        if 'updated_at' in chat_data and chat_data['updated_at']:
            chat_data['updated_at'] = str(chat_data['updated_at'])
        # Avoid duplicates if they somehow matched both (rare)
        if not any(c['id'] == doc.id for c in chats):
            chats.append(chat_data)
            
    # Sort by updated_at descending
    chats.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
    return chats

class MessageContent(BaseModel):
    text: str
    sender_id: str

@app.post("/api/chats/{chat_id}/messages")
def send_message(chat_id: str, msg: MessageContent, current_user: dict = Depends(get_current_user)):
    """Add a message to a specific chat document"""
    # Verify they have access to this chat
    chat_doc = db.collection('chats').document(chat_id).get()
    if not chat_doc.exists:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    chat_data = chat_doc.to_dict()
    if chat_data.get('user_id') != current_user['uid'] and chat_data.get('doctor_id') != current_user['uid'] and current_user['role'] not in ['admin', 'superadmin', 'superuser']:
        raise HTTPException(status_code=403, detail="Not authorized to send messages in this chat")

    new_message = {
        "text": msg.text,
        "sender_id": current_user['uid'],  # Force the sender to be the authenticated user
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    
    try:
        # Add to subcollection
        db.collection('chats').document(chat_id).collection('messages').add(new_message)
        # Update parent document timestamp
        db.collection('chats').document(chat_id).update({
            "last_message": msg.text,
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-symptoms", response_model=AnalysisResult)
def analyze_symptoms(input_data: SymptomInput):
    """Uses ML to analyze symptoms and recommend a department."""
    prediction = predict_appointment(input_data.symptoms)
    dept = prediction["department"]
    doctors = DOCTOR_NAMES.get(dept, ["Dr. General"])
    prediction["recommended_doctor"] = random.choice(doctors)
    return prediction

# --- Email & Calendar Logic ---

def create_ics(req: ScheduleRequest) -> bytes:
    """Generates an .ics file content for the appointment."""
    cal = Calendar()
    cal.add('prodid', '-//Smart Health Appointments//EN')
    cal.add('version', '2.0')

    event = Event()
    
    # Parse date and time
    start_dt = datetime.strptime(f"{req.date} {req.time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=30) # Assume 30 min duration
    
    event.add('summary', f"Medical Appointment: {req.patient_name} with {req.doctor_name}")
    event.add('dtstart', start_dt)
    event.add('dtend', end_dt)
    event.add('description', f"Department: {req.department}\nPatient: {req.patient_name}\nDoctor: {req.doctor_name}")
    event.add('location', 'Smart Health Clinic (Telemedicine or In-Person)')
    event['organizer'] = vText(f"MAILTO:{MAIL_CONF.MAIL_FROM}")
    
    # Add attendees to force calendar sync for most clients
    event.add('attendee', f"MAILTO:{req.patient_email}", parameters={'ROLE': 'REQ-PARTICIPANT'})
    event.add('attendee', f"MAILTO:{req.doctor_email}", parameters={'ROLE': 'REQ-PARTICIPANT'})

    cal.add_component(event)
    return cal.to_ical()

async def send_reminder_email(req: ScheduleRequest, reminder_type: str):
    """Helper to send the 24h or 1h reminder."""
    # In a real app, you'd check DB if appointment was cancelled first
    
    subject = f"Reminder: Appointment in {reminder_type} with {req.doctor_name}"
    body = f"""
    Hello {req.patient_name},
    
    This is an automated reminder that your {req.department} appointment with {req.doctor_name} 
    is coming up in {reminder_type} on {req.date} at {req.time}.
    
    Location: Smart Health Clinic / Telemedicine Portal
    
    Thank you,
    Smart Health Team
    """
    
    message = MessageSchema(
        subject=subject,
        recipients=[req.patient_email, req.doctor_email],
        body=body,
        subtype=MessageType.plain
    )
    
    try:
        await fm.send_message(message)
        print(f"[{datetime.now()}] Sent {reminder_type} reminder for {req.appointment_id}")
    except Exception as e:
        print(f"Failed to send {reminder_type} reminder: {e}")


async def send_initial_email(message: MessageSchema):
    """Wrapper to catch SMTP errors when using dummy credentials for local dev."""
    try:
        await fm.send_message(message)
    except Exception as e:
        print(f"Warning: Could not send email (check SMTP credentials): {e}")

@app.post("/api/schedule-appointment")
async def schedule_appointment(
    req: ScheduleRequest, 
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    1. Saves appointment to Firestore
    2. Sends immediate confirmation with .ics 
    3. Schedules 24h and 1h reminders
    """
    
    # 0. Save to Firestore via Admin SDK
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
        "created_at": firestore.SERVER_TIMESTAMP
    }
    
    try:
        # Use add() to auto-generate document ID and store it
        doc_ref = db.collection('appointments').document(req.appointment_id)
        doc_ref.set(appointment_data)
    except Exception as e:
        print(f"Firestore Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save appointment to database")

    # 1. Immediate confirmation with ICS
    ics_file_bytes = create_ics(req)
    
    # Wrap bytes in an UploadFile so fastapi-mail treats it as a file
    ics_io = io.BytesIO(ics_file_bytes)
    ics_io.seek(0)
    upload_file = UploadFile(filename="appointment.ics", file=ics_io)
    
    body = f"""
    Hello,
    
    Your appointment has been successfully scheduled!
    Please find the attached Google Calendar (.ics) invitation.
    
    Details:
    Patient: {req.patient_name}
    Doctor: {req.doctor_name} ({req.department})
    When: {req.date} at {req.time}
    
    Thank you for choosing Smart Health!
    """
    
    message = MessageSchema(
        subject=f"Appointment Confirmed: {req.patient_name} & {req.doctor_name}",
        recipients=[req.patient_email, req.doctor_email],
        body=body,
        subtype=MessageType.plain,
        attachments=[upload_file]
    )
    
    try:
        # We send the initial email immediately (or via background task)
        background_tasks.add_task(send_initial_email, message)
        
        # 2. Schedule Reminders
        appt_time = datetime.strptime(f"{req.date} {req.time}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        
        time_24h = appt_time - timedelta(hours=24)
        time_1h = appt_time - timedelta(hours=1)
        
        # Since send_message expects an event loop, we have a wrapper or use the background scheduler properly.
        # APScheduler integrates with asyncio, but passing async functions needs Care. 
        # For simplicity in this demo, we wrap it in an async-to-sync or just schedule an async runner.
        
        import asyncio
        def run_async(coro):
            asyncio.run(coro)

        if time_24h > now:
            scheduler.add_job(
                run_async, 
                'date', 
                run_date=time_24h, 
                args=[send_reminder_email(req, "24 Hours")],
                id=f"{req.appointment_id}_24h",
                replace_existing=True
            )
            
        if time_1h > now:
            scheduler.add_job(
                run_async, 
                'date', 
                run_date=time_1h, 
                args=[send_reminder_email(req, "1 Hour")],
                id=f"{req.appointment_id}_1h",
                replace_existing=True
            )
            
        return {"status": "Scheduled successfully", "appointment_id": req.appointment_id}

    except Exception as e:
        print(f"Scheduling Error: {e}")
        return {"error": str(e)}

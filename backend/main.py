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
async def schedule_appointment(req: ScheduleRequest, background_tasks: BackgroundTasks):
    """
    1. Sends immediate confirmation with .ics 
    2. Schedules 24h and 1h reminders
    """
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

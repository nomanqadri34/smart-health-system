from pydantic import BaseModel
from typing import Optional, List

# --- Existing Models ---
class SymptomInput(BaseModel):
    symptoms: str

class AnalysisResult(BaseModel):
    department: str
    estimated_duration_minutes: int
    triage_priority: str
    recommended_doctor: str

class Slot(BaseModel):
    id: str
    time: str
    doctor_name: str
    department: str
    is_available: bool

class BookingRequest(BaseModel):
    slot_id: str
    patient_name: str
    symptoms_summary: str
    department: str
    time: str

# --- Auth Models ---
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserData(BaseModel):
    id: int
    email: str
    full_name: str


# Analytics and reporting logic has been migrated to specialized modules
# (e.g., health_analytics_ml.py)

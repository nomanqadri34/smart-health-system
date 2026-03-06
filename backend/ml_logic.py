from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
import pandas as pd
import numpy as np
from datetime import datetime
import google.generativeai as genai
import json

import os
from dotenv import load_dotenv

# Configure Gemini API
load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError("GEMINI_API_KEY is not set in the environment.")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# Mock Dataset for Training
data = [
    {"symptoms": "headache, dizziness, nausea", "department": "Neurology", "duration": 30, "priority": "High", "severity": 7},
    {"symptoms": "fever, cough, cold, runny nose", "department": "General Medicine", "duration": 15, "priority": "Medium", "severity": 4},
    {"symptoms": "chest pain, shortness of breath", "department": "Cardiology", "duration": 45, "priority": "Critical", "severity": 9},
    {"symptoms": "skin rash, itching, redness", "department": "Dermatology", "duration": 20, "priority": "Low", "severity": 3},
    {"symptoms": "toothache, swollen gum", "department": "Dentistry", "duration": 30, "priority": "Medium", "severity": 4},
    {"symptoms": "blurred vision, eye pain", "department": "Ophthalmology", "duration": 20, "priority": "Medium", "severity": 5},
    {"symptoms": "stomach ache, vomiting, diarrhea", "department": "Gastroenterology", "duration": 20, "priority": "Medium", "severity": 5},
    {"symptoms": "joint pain, swelling, knee pain", "department": "Orthopedics", "duration": 30, "priority": "Medium", "severity": 5},
    {"symptoms": "ear pain, hearing loss", "department": "ENT", "duration": 20, "priority": "Medium", "severity": 4},
    {"symptoms": "anxiety, depression, sleep issues", "department": "Psychiatry", "duration": 60, "priority": "Medium", "severity": 6},
]

df = pd.DataFrame(data)

# Train Department Model
dept_model = make_pipeline(CountVectorizer(), MultinomialNB())
dept_model.fit(df['symptoms'], df['department'])

# Department average duration lookup
dept_avg_duration = df.groupby('department')['duration'].mean().to_dict()

# Severity keyword rules
CRITICAL_KEYWORDS = ['chest', 'heart', 'breath', 'unconscious', 'bleeding', 'stroke', 'seizure', 'paralysis']
HIGH_KEYWORDS = ['severe', 'intense', 'unbearable', 'sudden', 'acute', 'trauma', 'fracture']
LOW_KEYWORDS = ['mild', 'slight', 'minor', 'occasional', 'light']

def compute_severity_score(symptoms: str, priority: str) -> int:
    """Return a severity score 0-10 based on keywords and triage priority."""
    s = symptoms.lower()
    base = {'Critical': 9, 'High': 7, 'Medium': 5, 'Low': 3}.get(priority, 5)
    
    if any(k in s for k in CRITICAL_KEYWORDS):
        base = max(base, 9)
    elif any(k in s for k in HIGH_KEYWORDS):
        base = max(base, 7)
    elif any(k in s for k in LOW_KEYWORDS):
        base = min(base, 3)
    
    return min(10, base)


async def predict_appointment(symptoms: str, patient_severity_score: int = 5):
    """
    Uses Gemini to analyze symptoms and return a structured JSON response.
    Fallback to simple mock if Gemini fails.
    """
    prompt = f"""
    You are an expert triage nurse. Analyze the following patient symptoms: "{symptoms}"
    The patient has self-reported a pain/severity score of {patient_severity_score} out of 10.
    Provide your assessment in strict JSON format with exactly these keys:
    - "department": The specific medical department the patient should visit (e.g., Cardiology, Neurology, General Medicine, Dermatology, Orthopedics, ENT, Psychiatry).
    - "triage_priority": One of "Low", "Medium", "High", or "Critical".
    - "estimated_duration_minutes": An integer estimating the typical consultation duration (15 to 60).
    - "severity_score": An integer from 1 to 10 (you can adjust the patient's self-reported score if needed based on the symptoms).
    - "summary": A brief, comforting 2-sentence summary of the recommendation.
    - "immediate_actions": A list of 2 to 4 short, actionable strings the patient should do right now (e.g., ["Drink plenty of water", "Rest in a dark room"]).
    Return ONLY valid JSON.
    """
    try:
        response = model.generate_content(prompt)
        # Strip code formatting if any
        text = response.text.strip()
        if text.startswith('```json'):
            text = text[7:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        return {
            "department": data.get("department", "General Medicine"),
            "estimated_duration_minutes": data.get("estimated_duration_minutes", 30),
            "triage_priority": data.get("triage_priority", "Medium"),
            "confidence": 0.95,
            "summary": data.get("summary", f"Based on your symptoms, we recommend visiting {data.get('department')}."),
            "severity_score": data.get("severity_score", patient_severity_score),
            "immediate_actions": data.get("immediate_actions", ["Please consult a doctor for further advice."]),
        }
    except Exception as e:
        print(f"Gemini API Error: {e}")
        # Fallback to old ML logic
        predicted_dept = dept_model.predict([symptoms])[0]
        confidence = float(max(dept_model.predict_proba([symptoms])[0]))
        duration = dept_avg_duration.get(predicted_dept, 30)
        critical_keywords = ['chest', 'heart', 'breath', 'unconscious', 'bleeding']
        priority = "Critical" if any(k in symptoms.lower() for k in critical_keywords) else "Medium"
        severity_score = compute_severity_score(symptoms, priority)
        return {
            "department": str(predicted_dept),
            "estimated_duration_minutes": int(duration),
            "triage_priority": priority,
            "confidence": confidence,
            "summary": f"Based on your symptoms, we recommend visiting the {predicted_dept} department.",
            "severity_score": severity_score,
            "immediate_actions": ["Rest and monitor your symptoms closely.", "Seek immediate care if symptoms worsen."]
        }

async def summarize_notes_with_gemini(raw_notes: str) -> str:
    """Uses Gemini to structure raw clinical notes."""
    prompt = f"""
    You are a professional medical scribe. Structure the following raw doctor's consultation notes into a clean, professional medical summary.
    Use headings like 'Primary Diagnosis', 'Action Items/Follow-up', and 'Recommendations'.
    Keep it concise and clinical.
    
    Raw Notes: {raw_notes}
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini Note Error: {e}")
        return raw_notes


def predict_noshow(appointment: dict) -> dict:
    """
    Heuristic-based no-show risk prediction.
    Returns a score 0.0–1.0 and risk label.
    """
    score = 0.0
    
    # Factor 1: Time of day (early morning or late evening = higher risk)
    try:
        hour = int(appointment.get('time', '09:00').split(':')[0])
        if hour < 8 or hour >= 17:
            score += 0.2
        elif 8 <= hour < 10 or 15 <= hour < 17:
            score += 0.1
    except:
        pass
    
    # Factor 2: Day of week computed from date
    try:
        appt_date = datetime.strptime(appointment.get('date', '2025-01-01'), '%Y-%m-%d')
        if appt_date.weekday() >= 5:  # Weekend
            score += 0.25
    except:
        pass
    
    # Factor 3: Low severity symptoms
    priority = appointment.get('triage_priority', 'Medium')
    if priority == 'Low':
        score += 0.2
    elif priority == 'Medium':
        score += 0.1
    
    # Factor 4: Very new booking (created_at close to appointment)
    score = min(1.0, score)
    
    if score >= 0.5:
        risk = "High"
    elif score >= 0.3:
        risk = "Medium"
    else:
        risk = "Low"
    
    return {"noshow_risk_score": round(score, 2), "noshow_risk_level": risk}


def recommend_doctors(symptoms: str, department: str, doctors: list) -> list:
    """
    Rank doctors by department match and (mock) workload score.
    Returns a sorted list of doctor dicts with match_score.
    """
    results = []
    dept_lower = department.lower()
    
    for doc in doctors:
        score = 0.0
        doc_dept = (doc.get('profile', {}).get('specialization', '') or '').lower()
        
        # Exact department match
        if dept_lower in doc_dept or doc_dept in dept_lower:
            score += 0.6
        
        # Experience bonus
        exp = doc.get('profile', {}).get('experience_years', 0) or 0
        score += min(0.3, exp * 0.02)
        
        # Random mock "availability" score
        score += np.random.uniform(0, 0.1)
        
        results.append({
            **doc,
            'match_score': round(min(1.0, score), 2)
        })
    
    results.sort(key=lambda x: x['match_score'], reverse=True)
    return results[:5]

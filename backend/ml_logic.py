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

try:
    genai.configure(api_key=api_key)
    # Using the stable gemini-2.5-flash model
    model = genai.GenerativeModel('models/gemini-2.5-flash')
    print("Gemini AI model 'gemini-2.5-flash' initialized.")
except Exception as e:
    print(f"CRITICAL: Failed to initialize Gemini model: {e}")
    model = None

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
    You are a highly advanced AI triage clinical assistant specializing in initial patient diagnosis and routing.
    Analyze the following patient symptoms provided in quotes: "{symptoms}"
    The patient has self-reported a severity of {patient_severity_score}/10.

    Analyze the symptoms with deep clinical logic and provide a structured JSON response.
    Your response must be based on medical expertise while maintaining a reassuring tone.
    Provide the response in strict JSON format with exactly these keys:
    - "department": The most appropriate medical specialty (e.g., Cardiology, Neurology, Orthopedics, Gastroenterology, Dermatology, Psychiatry, Pulmonology, General Medicine).
    - "triage_priority": "Low", "Medium", "High", or "Critical" based on the severity of symptoms described.
    - "estimated_duration_minutes": A realistic integer (15, 20, 30, 45, or 60) for a standard consultation in this department.
    - "severity_score": An adjusted severity score (1-10) based on clinical evaluation of the symptoms vs the patient's self-report.
    - "confidence_percentage": An integer (0-100) representing your confidence in this routing.
    - "summary": A professional but comforting 2-sentence summary explaining why this department was chosen.
    - "immediate_actions": A list of 3-4 specific, actionable, and safe next steps (e.g., "Monitor your temperature every 4 hours", "Apply a cold compress to the swollen area").
    - "key_concerns": A list of 2-3 specific medical conditions these symptoms could potentially indicate (be professional).

    Return ONLY the valid JSON object.
    """
    try:
        if model is None:
            raise ValueError("Gemini model is not initialized")

        response = model.generate_content(prompt)
        text = response.text.strip()
        # Robust JSON cleaning
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()
        
        data = json.loads(text)
        
        return {
            "department": data.get("department", "General Medicine"),
            "estimated_duration_minutes": int(data.get("estimated_duration_minutes", 30)),
            "triage_priority": data.get("triage_priority", "Medium"),
            "confidence": data.get("confidence_percentage", 90) / 100.0,
            "summary": data.get("summary", "Complete diagnostic checkup recommended based on symptoms."),
            "severity_score": int(data.get("severity_score", patient_severity_score)),
            "immediate_actions": data.get("immediate_actions", ["Rest and observe", "Stay hydrated"]),
            "key_concerns": data.get("key_concerns", ["General inflammatory response"])
        }
    except Exception as e:
        print(f"ML Prediction Error (Gemini): {e}")
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

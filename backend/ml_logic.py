from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
import pandas as pd
import numpy as np

# Mock Dataset for Training
data = [
    {"symptoms": "headache, dizziness, nausea", "department": "Neurology", "duration": 30, "priority": "High"},
    {"symptoms": "fever, cough, cold, runny nose", "department": "General Medicine", "duration": 15, "priority": "Medium"},
    {"symptoms": "chest pain, shortness of breath", "department": "Cardiology", "duration": 45, "priority": "Critical"},
    {"symptoms": "skin rash, itching, redness", "department": "Dermatology", "duration": 20, "priority": "Low"},
    {"symptoms": "toothache, swollen gum", "department": "Dentistry", "duration": 30, "priority": "Medium"},
    {"symptoms": "blurred vision, eye pain", "department": "Ophthalmology", "duration": 20, "priority": "Medium"},
    {"symptoms": "stomach ache, vomiting, diarrhea", "department": "Gastroenterology", "duration": 20, "priority": "Medium"},
    {"symptoms": "joint pain, swelling, knee pain", "department": "Orthopedics", "duration": 30, "priority": "Medium"},
    {"symptoms": "ear pain, hearing loss", "department": "ENT", "duration": 20, "priority": "Medium"},
    {"symptoms": "anxiety, depression, sleep issues", "department": "Psychiatry", "duration": 60, "priority": "Medium"},
]

df = pd.DataFrame(data)

# Train Models
dept_model = make_pipeline(CountVectorizer(), MultinomialNB())
dept_model.fit(df['symptoms'], df['department'])

# For duration, we'll just take the average of the predicted department for simplicity in this demo
# or train a regressor. Let's use a lookup for simplicity after dept prediction.
dept_avg_duration = df.groupby('department')['duration'].mean().to_dict()

def predict_appointment(symptoms: str):
    # Predict Department
    predicted_dept = dept_model.predict([symptoms])[0]
    
    # Get confidence from probability
    proba = dept_model.predict_proba([symptoms])[0]
    confidence = float(max(proba))
    
    # Get estimated duration
    duration = dept_avg_duration.get(predicted_dept, 30)
    
    # Determine priority (Simple rule based or could be another model)
    # We'll just infer from the department in this mock or use keywords
    critical_keywords = ['chest', 'heart', 'breath', 'unconscious', 'bleeding']
    if any(k in symptoms.lower() for k in critical_keywords):
        priority = "Critical"
    else:
        # Fallback to what our mock data usually has for this dept
        priority = df[df['department'] == predicted_dept]['priority'].iloc[0]
    
    # Generate summary
    summary = f"Based on your symptoms ({symptoms}), we recommend visiting the {predicted_dept} department. Priority: {priority}."

    return {
        "department": str(predicted_dept),
        "estimated_duration_minutes": int(duration),
        "triage_priority": priority,
        "confidence": confidence,
        "summary": summary
    }


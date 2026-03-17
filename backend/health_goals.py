"""
Patient Health Goals System
Tracking custom health goals like weight loss, daily steps, water intake, etc.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, validator
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from firebase_admin import firestore

# ─────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────

class HealthGoal(BaseModel):
    title: str               # e.g., "Lose 5kg", "Walk 10,000 steps"
    category: str            # weight, nutrition, activity, sleep, mind
    target_value: float      # e.g., 5.0, 10000.0
    current_value: float = 0.0
    unit: str                # kg, steps, hours, liters
    deadline: Optional[str] = None # ISO date
    frequency: str = "daily" # daily, weekly, monthly, overall
    notes: str = ""

    @validator("category")
    def validate_category(cls, v):
        allowed = {"weight", "nutrition", "activity", "sleep", "mind", "other"}
        if v not in allowed:
            raise ValueError(f"Category must be one of {allowed}")
        return v

class GoalProgressUpdate(BaseModel):
    increment: Optional[float] = None # Add to current_value
    set_value: Optional[float] = None # Override current_value
    notes: Optional[str] = None

# ─────────────────────────────────────────────────────
# Route Registration
# ─────────────────────────────────────────────────────

def register_health_goals_routes(app, db, get_current_user, log_action, serialize_doc):

    # ── POST /api/goals ── Create a goal
    @app.post("/api/goals")
    def create_goal(goal: HealthGoal, current_user: dict = Depends(get_current_user)):
        data = goal.dict()
        data["patient_id"] = current_user["uid"]
        data["status"] = "in_progress" # in_progress, achieved, failed
        data["created_at"] = firestore.SERVER_TIMESTAMP
        data["progress_logs"] = [] # Timeline of updates
        
        ref = db.collection("health_goals").add(data)
        log_action(current_user, "create_goal", {"title": goal.title})
        return {"status": "success", "id": ref[1].id}

    # ── GET /api/goals ── Fetch goals
    @app.get("/api/goals")
    def get_goals(status: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
        query = db.collection("health_goals").where("patient_id", "==", current_user["uid"])
        if status:
            query = query.where("status", "==", status)
            
        docs = query.stream()
        goals = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            goals.append(serialize_doc(d))
            
        return goals

    # ── POST /api/goals/{goal_id}/progress ── Update progress
    @app.post("/api/goals/{goal_id}/progress")
    def update_goal_progress(goal_id: str, update: GoalProgressUpdate, current_user: dict = Depends(get_current_user)):
        doc_ref = db.collection("health_goals").document(goal_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Goal not found")
        
        goal_data = doc.to_dict()
        if goal_data.get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        new_value = goal_data.get("current_value", 0.0)
        if update.set_value is not None:
            new_value = update.set_value
        elif update.increment is not None:
            new_value += update.increment
            
        new_status = goal_data.get("status")
        if new_value >= goal_data.get("target_value", 0):
             new_status = "achieved"
             
        log_entry = {
            "timestamp": firestore.SERVER_TIMESTAMP,
            "previous_value": goal_data.get("current_value"),
            "new_value": new_value,
            "notes": update.notes or ""
        }
        
        doc_ref.update({
            "current_value": new_value,
            "status": new_status,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "progress_logs": firestore.ArrayUnion([log_entry])
        })
        
        return {"status": "success", "new_value": new_value, "goal_status": new_status}

    # ── DELETE /api/goals/{goal_id} ── Delete goal
    @app.delete("/api/goals/{goal_id}")
    def delete_goal(goal_id: str, current_user: dict = Depends(get_current_user)):
        doc_ref = db.collection("health_goals").document(goal_id)
        doc = doc_ref.get()
        if not doc.exists or doc.to_dict().get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        doc_ref.delete()
        return {"status": "success"}

    # ── GET /api/goals/dashboard ── Dashboard stats
    @app.get("/api/goals/dashboard")
    def get_goals_dashboard(current_user: dict = Depends(get_current_user)):
        docs = db.collection("health_goals").where("patient_id", "==", current_user["uid"]).stream()
        total_goals = 0
        achieved = 0
        categories = {}
        
        for doc in docs:
            d = doc.to_dict()
            total_goals += 1
            if d.get("status") == "achieved":
                achieved += 1
            cat = d.get("category", "other")
            categories[cat] = categories.get(cat, 0) + 1
            
        return {
            "total_goals": total_goals,
            "achieved_goals": achieved,
            "active_goals": total_goals - achieved,
            "completion_rate": (achieved / total_goals * 100) if total_goals > 0 else 0,
            "by_category": categories
        }

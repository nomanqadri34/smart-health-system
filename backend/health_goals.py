"""
Patient Health Goals System
Tracking custom health goals like weight loss, daily steps, water intake, etc.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, validator
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from bson import ObjectId

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
    async def create_goal(goal: HealthGoal, current_user: dict = Depends(get_current_user)):
        data = goal.dict()
        data["patient_id"] = current_user["uid"]
        data["status"] = "in_progress" # in_progress, achieved, failed
        data["created_at"] = datetime.utcnow()
        data["progress_logs"] = [] # Timeline of updates
        
        result = await db.health_goals.insert_one(data)
        await log_action(current_user, "create_goal", {"title": goal.title})
        return {"status": "success", "id": str(result.inserted_id)}

    # ── GET /api/goals ── Fetch goals
    @app.get("/api/goals")
    async def get_goals(status: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
        mongo_query = {"patient_id": current_user["uid"]}
        if status:
            mongo_query["status"] = status
            
        cursor = db.health_goals.find(mongo_query)
        goals = []
        async for doc in cursor:
            goals.append(serialize_doc(doc))
            
        return goals

    # ── POST /api/goals/{goal_id}/progress ── Update progress
    @app.post("/api/goals/{goal_id}/progress")
    async def update_goal_progress(goal_id: str, update: GoalProgressUpdate, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(goal_id)} if ObjectId.is_valid(goal_id) else {"goal_id": goal_id}
        goal_data = await db.health_goals.find_one(query)
        if not goal_data:
            raise HTTPException(status_code=404, detail="Goal not found")
        
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
             
        now = datetime.utcnow()
        log_entry = {
            "timestamp": now,
            "previous_value": goal_data.get("current_value"),
            "new_value": new_value,
            "notes": update.notes or ""
        }
        
        await db.health_goals.update_one(query, {
            "$set": {
                "current_value": new_value,
                "status": new_status,
                "updated_at": now
            },
            "$push": {"progress_logs": log_entry}
        })
        
        return {"status": "success", "new_value": new_value, "goal_status": new_status}

    # ── DELETE /api/goals/{goal_id} ── Delete goal
    @app.delete("/api/goals/{goal_id}")
    async def delete_goal(goal_id: str, current_user: dict = Depends(get_current_user)):
        query = {"_id": ObjectId(goal_id)} if ObjectId.is_valid(goal_id) else {"goal_id": goal_id}
        doc = await db.health_goals.find_one(query)
        if not doc or doc.get("patient_id") != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        await db.health_goals.delete_one(query)
        return {"status": "success"}

    # ── GET /api/goals/dashboard ── Dashboard stats
    @app.get("/api/goals/dashboard")
    async def get_goals_dashboard(current_user: dict = Depends(get_current_user)):
        cursor = db.health_goals.find({"patient_id": current_user["uid"]})
        total_goals = 0
        achieved = 0
        categories = {}
        
        async for doc in cursor:
            total_goals += 1
            if doc.get("status") == "achieved":
                achieved += 1
            cat = doc.get("category", "other")
            categories[cat] = categories.get(cat, 0) + 1
            
        return {
            "total_goals": total_goals,
            "achieved_goals": achieved,
            "active_goals": total_goals - achieved,
            "completion_rate": (achieved / total_goals * 100) if total_goals > 0 else 0,
            "by_category": categories
        }

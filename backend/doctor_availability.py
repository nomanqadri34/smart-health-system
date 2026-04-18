"""
Doctor Availability Management
Handles predefined schedules, exceptions, time-off, and slot generation.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from bson import ObjectId

# ─────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────

class WorkingHours(BaseModel):
    start: str  # HH:MM format
    end: str    # HH:MM format

class DailySchedule(BaseModel):
    day_of_week: int  # 0=Monday, 6=Sunday
    is_working: bool
    working_hours: Optional[List[WorkingHours]] = None

class DoctorScheduleConfig(BaseModel):
    slot_duration_minutes: int = 30
    buffer_between_slots_minutes: int = 5
    regular_schedule: List[DailySchedule]

class TimeOffRequest(BaseModel):
    start_date: str # ISO date string
    end_date: str
    reason: str = ""

# ─────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────

def generate_slots_for_date(date: datetime, schedule_config: dict, time_offs: list, existing_appointments: list) -> list:
    """Generates available time slots for a specific date based on configuration."""
    # Check if date is in time-offs
    date_str = date.date().isoformat()
    for to in time_offs:
        if to.get("start_date", "") <= date_str <= to.get("end_date", ""):
            return [] # Doctor is off

    # Find the day of week configuration
    day_of_week = date.weekday()
    day_config = None
    for ds in schedule_config.get("regular_schedule", []):
        if ds.get("day_of_week") == day_of_week:
            day_config = ds
            break
            
    if not day_config or not day_config.get("is_working"):
        return []
        
    slot_duration = schedule_config.get("slot_duration_minutes", 30)
    buffer = schedule_config.get("buffer_between_slots_minutes", 0)
    
    slots = []
    # Collect all booked times for this date
    booked_times = [appt.get("time") for appt in existing_appointments if appt.get("date") == date_str and appt.get("status") not in ("cancelled", "rejected")]
    
    for block in day_config.get("working_hours", []):
        try:
            sh, sm = map(int, block["start"].split(":"))
            eh, em = map(int, block["end"].split(":"))
            start_dt = datetime(date.year, date.month, date.day, sh, sm)
            end_dt = datetime(date.year, date.month, date.day, eh, em)
            
            curr_dt = start_dt
            while curr_dt + timedelta(minutes=slot_duration) <= end_dt:
                time_str = curr_dt.strftime("%H:%M")
                
                # Check if this slot overlap with booked times (simplified exact match for now)
                is_available = time_str not in booked_times
                
                if curr_dt > datetime.utcnow() or date.date() > datetime.utcnow().date():
                    slots.append({
                        "time": time_str,
                        "datetime_iso": curr_dt.isoformat(),
                        "is_available": is_available
                    })
                
                curr_dt += timedelta(minutes=slot_duration + buffer)
        except Exception:
            pass
            
    return slots

# ─────────────────────────────────────────────────────
# Route Registration
# ─────────────────────────────────────────────────────

def register_availability_routes(app, db, get_current_user, log_action, serialize_doc):

    # ── POST /api/schedule/config ── Set Doctor Schedule Config
    @app.post("/api/schedule/config")
    async def set_schedule_config(config: DoctorScheduleConfig, current_user: dict = Depends(get_current_user)):
        if current_user["role"] != "doctor":
            raise HTTPException(status_code=403, detail="Only doctors can manage their schedules")
            
        data = config.dict()
        data["updated_at"] = datetime.utcnow()
        await db.doctor_schedules.update_one(
            {"_id": current_user["uid"]},
            {"$set": data},
            upsert=True
        )
        await log_action(current_user, "update_schedule_config")
        return {"status": "success"}

    # ── GET /api/schedule/config ── Get Doctor Schedule Config
    @app.get("/api/schedule/config")
    async def get_schedule_config(doctor_id: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
        target_id = current_user["uid"]
        if doctor_id and current_user["role"] in ["superuser", "admin", "superadmin", "patient"]:
             target_id = doctor_id
             
        doc = await db.doctor_schedules.find_one({"_id": target_id})
        if not doc:
            # Return default config
            return {
                "slot_duration_minutes": 30,
                "buffer_between_slots_minutes": 0,
                "regular_schedule": [
                    {"day_of_week": i, "is_working": i < 5, "working_hours": [{"start": "09:00", "end": "17:00"} if i < 5 else None]}
                    for i in range(7)
                ]
            }
        return serialize_doc(doc)

    # ── POST /api/schedule/time-off ── Add Time Off
    @app.post("/api/schedule/time-off")
    async def add_time_off(request: TimeOffRequest, current_user: dict = Depends(get_current_user)):
        if current_user["role"] != "doctor":
            raise HTTPException(status_code=403, detail="Only doctors can request time off")
            
        data = request.dict()
        data["doctor_id"] = current_user["uid"]
        data["created_at"] = datetime.utcnow()
        result = await db.time_offs.insert_one(data)
        await log_action(current_user, "add_time_off")
        return {"status": "success", "id": str(result.inserted_id)}

    # ── GET /api/schedule/time-off ── Get Time Offs
    @app.get("/api/schedule/time-off")
    async def get_time_offs(doctor_id: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
        target_id = current_user["uid"] if current_user["role"] == "doctor" else doctor_id
        if not target_id:
            raise HTTPException(status_code=400, detail="Doctor ID required")
            
        cursor = db.time_offs.find({"doctor_id": target_id})
        results = []
        async for doc in cursor:
            results.append(serialize_doc(doc))
        return results

    # ── DELETE /api/schedule/time-off/{time_off_id} ── Delete Time Off
    @app.delete("/api/schedule/time-off/{time_off_id}")
    async def delete_time_off(time_off_id: str, current_user: dict = Depends(get_current_user)):
        if current_user["role"] != "doctor":
             raise HTTPException(status_code=403, detail="Not authorized")
        query = {"_id": ObjectId(time_off_id)} if ObjectId.is_valid(time_off_id) else {"time_off_id": time_off_id}
        doc = await db.time_offs.find_one(query)
        if not doc or doc.get("doctor_id") != current_user["uid"]:
             raise HTTPException(status_code=403, detail="Not authorized")
        await db.time_offs.delete_one(query)
        return {"status": "success"}

    # ── GET /api/schedule/slots ── Get Available Slots for a Doctor
    @app.get("/api/schedule/slots")
    async def get_available_slots(doctor_id: str, date: str = Query(...), current_user: dict = Depends(get_current_user)):
        """Generate available slots for a specific doctor and date."""
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

        # 1. Get Schedule Config
        config_doc = await db.doctor_schedules.find_one({"_id": doctor_id})
        if config_doc:
            config = config_doc
        else:
            # Default Mon-Fri 9-5 config
            config = {
                "slot_duration_minutes": 30,
                "buffer_between_slots_minutes": 0,
                "regular_schedule": [
                    {"day_of_week": i, "is_working": i < 5, "working_hours": [{"start": "09:00", "end": "17:00"}]}
                    for i in range(7)
                ]
            }

        # 2. Get Time Offs
        to_cursor = db.time_offs.find({"doctor_id": doctor_id})
        time_offs = []
        async for doc in to_cursor:
            time_offs.append(doc)

        # 3. Get Existing Appointments (by finding doctor email first)
        user_query = {"_id": ObjectId(doctor_id)} if ObjectId.is_valid(doctor_id) else {"uid": doctor_id}
        user_doc = await db.users.find_one(user_query)
        doctor_email = user_doc.get("email", "") if user_doc else ""
        
        appt_cursor = db.appointments.find({"doctor_email": doctor_email, "date": date})
        existing_appointments = []
        async for doc in appt_cursor:
            existing_appointments.append(doc)

        # 4. Generate slots
        slots = generate_slots_for_date(target_date, config, time_offs, existing_appointments)
        return {"doctor_id": doctor_id, "date": date, "slots": slots}

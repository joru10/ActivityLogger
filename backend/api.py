# api.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models import SessionLocal, ActivityLog
from typing import List, Optional
from datetime import datetime, timedelta, date
from pydantic import BaseModel
import os
import json

router = APIRouter()

# --------------------------
# Activity Logs Endpoints
# --------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/activity-logs", response_model=List[dict])
def read_activity_logs(date: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(ActivityLog)
    if date:
        try:
            # Parse the date string in format YYYY-MM-DD.
            start_date = datetime.strptime(date, "%Y-%m-%d")
            # Define the end of that day.
            end_date = start_date + timedelta(days=1)
            # Filter logs between start_date (inclusive) and end_date (exclusive).
            query = query.filter(ActivityLog.timestamp >= start_date, ActivityLog.timestamp < end_date)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")
    logs = query.all()
    # Remove SQLAlchemy's internal state from the dict before returning.
    return [
        {k: v for k, v in log.__dict__.items() if k != "_sa_instance_state"}
        for log in logs
    ]

# --------------------------
# Settings Endpoints
# --------------------------

class Settings(BaseModel):
    notificationInterval: int
    audioDevice: str
    llmProvider: str
    openRouterApiKey: str = ""
    openRouterLLM: str = ""
    activityGroups: str

# For demonstration purposes, settings are stored in a global dictionary.
current_settings = {
    "notificationInterval": 15,
    "audioDevice": "default",
    "llmProvider": "LMStudio",
    "openRouterApiKey": "",
    "openRouterLLM": "",
    "activityGroups": "coding, meeting, research, others"
}

@router.get("/settings", response_model=Settings)
def get_settings():
    return current_settings

@router.put("/settings", response_model=Settings)
def update_settings(settings: Settings):
    global current_settings
    current_settings = settings.dict()
    return current_settings

# --------------------------
# Reports Endpoints
# --------------------------

@router.get("/daily-report")
def get_daily_report():
    today_str = date.today().isoformat()
    report_filename = os.path.join(os.getcwd(), "reports", "daily", f"{today_str}_report.json")
    if os.path.exists(report_filename):
        with open(report_filename, "r", encoding="utf-8") as f:
            report_data = json.load(f)
        return report_data
    else:
        return {"message": "No report found for today."}
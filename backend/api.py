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

# ------------------------------------------
# Dependency: Database session
# ------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ------------------------------------------
# Activity Logs Endpoints
# ------------------------------------------
@router.get("/activity-logs", response_model=List[dict])
def read_activity_logs(date: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(ActivityLog)
    if date:
        try:
            start_date = datetime.strptime(date, "%Y-%m-%d")
            end_date = start_date + timedelta(days=1)
            query = query.filter(ActivityLog.timestamp >= start_date,
                                 ActivityLog.timestamp < end_date)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")
    logs = query.all()
    return [
        {k: v for k, v in log.__dict__.items() if k != "_sa_instance_state"}
        for log in logs
    ]

# ------------------------------------------
# Settings Endpoints
# ------------------------------------------
class Category(BaseModel):
    name: str
    groups: List[str]

class Settings(BaseModel):
    notificationInterval: int
    audioDevice: str
    llmProvider: str
    openRouterApiKey: str = ""
    openRouterLLM: str = ""
    categories: List[Category]

# For demonstration, we store settings in a global variable
current_settings = {
    "notificationInterval": 60,
    "audioDevice": "default",
    "llmProvider": "LMStudio",
    "openRouterApiKey": "",
    "openRouterLLM": "",
    "categories": [
        {
            "name": "Coding",
            "groups": ["ActivityReports project", "ColabsReview", "MultiAgent"]
        },
        {
            "name": "Training",
            "groups": ["NLP Course", "Deep Learning Specialization"]
        },
        {
            "name": "Research",
            "groups": ["Paper Reading: Transformer-XX", "Video: New Architecture"]
        },
        {
            "name": "Business",
            "groups": ["Project Bids", "Client Meetings"]
        },
        {
            "name": "Work&Finance",
            "groups": ["Unemployment", "Work-search", "Pensions-related"]
        }
    ]
}

@router.get("/settings", response_model=Settings)
def get_settings():
    return current_settings

@router.put("/settings", response_model=Settings)
def update_settings(settings: Settings):
    global current_settings
    current_settings = settings.dict()
    return current_settings
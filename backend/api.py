# api.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models import SessionLocal, ActivityLog, Settings
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import json
import logging

# Setup logging
logger = logging.getLogger(__name__)
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
def read_activity_logs(date: Optional[datetime] = Query(None), db: Session = Depends(get_db)):
    query = db.query(ActivityLog)
    if date:
        start_date = datetime(date.year, date.month, date.day)
        end_date = start_date + timedelta(days=1)
        query = query.filter(ActivityLog.timestamp >= start_date,
                             ActivityLog.timestamp < end_date)
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

class SettingsUpdate(BaseModel):
    notificationInterval: int
    audioDevice: str
    llmProvider: str
    openRouterApiKey: str = ""
    openRouterLLM: str = ""
    categories: List[Category]

@router.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    settings = db.query(Settings).first()  # Use Settings instead of DBSettings
    if not settings:
        settings = Settings()
        db.add(settings)
        db.commit()
    return settings.dict()

@router.put("/settings")
def update_settings(updated_settings: SettingsUpdate, db: Session = Depends(get_db)):
    try:
        logger.info(f"Updating settings with: {json.dumps(updated_settings.dict(), indent=2)}")
        settings = db.query(Settings).first()
        if not settings:
            settings = Settings()
            db.add(settings)
            logger.info("Created new settings record")
        
        # Update fields from Pydantic model
        settings_dict = updated_settings.dict()
        logger.info(f"Current settings before update: {settings.dict()}")
        
        # Update scalar fields
        for field in ["notificationInterval", "audioDevice", "llmProvider", 
                     "openRouterApiKey", "openRouterLLM"]:
            if field in settings_dict:
                setattr(settings, field, settings_dict[field])
        
        # Update categories
        if "categories" in settings_dict:
            settings.set_categories(settings_dict["categories"])
        
        db.commit()
        logger.info("Settings committed to database")
        return settings.dict()
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
# api.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .models import SessionLocal, ActivityLog, Settings
from .daily_report_fix import generate_daily_report_html
from .weekly_report_fix import generate_weekly_report_html
from typing import List, Optional
from datetime import datetime, timedelta, time
from pydantic import BaseModel, Field, ConfigDict
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
def read_activity_logs(date: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(ActivityLog)
    if date:
        try:
            # Parse the date string from the frontend (YYYY-MM-DD)
            parsed_date = datetime.strptime(date, '%Y-%m-%d')
            start_date = datetime(parsed_date.year, parsed_date.month, parsed_date.day)
            end_date = start_date + timedelta(days=1)
            logger.info(f"Filtering logs between {start_date} and {end_date}")
            query = query.filter(ActivityLog.timestamp >= start_date,
                               ActivityLog.timestamp < end_date)
        except ValueError as e:
            logger.error(f"Error parsing date parameter: {date}, error: {e}")
    logs = query.all()
    return [
        {k: v for k, v in log.__dict__.items() if k != "_sa_instance_state"}
        for log in logs
    ]

# ------------------------------------------
# Activity Logs Endpoints
# ------------------------------------------

class ActivityLogCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    timestamp: datetime
    description: str
    category: str
    group: Optional[str] = None
    duration_minutes: int = Field(..., gt=0, description="Duration in minutes, must be positive")

class ActivityLogUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    description: Optional[str] = Field(None, min_length=1, description="Activity description")
    category: Optional[str] = Field(None, min_length=1, description="Activity category")
    group: Optional[str] = Field(None, min_length=1, description="Activity group")
    duration_minutes: Optional[int] = Field(None, gt=0, description="Duration in minutes, must be positive")

@router.post("/activities", response_model=dict)
def create_activity(activity: ActivityLogCreate, db: Session = Depends(get_db)):
    db_activity = ActivityLog(**activity.model_dump())
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return {k: v for k, v in db_activity.__dict__.items() if k != "_sa_instance_state"}

@router.get("/activities/{activity_id}", response_model=dict)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return {k: v for k, v in activity.__dict__.items() if k != "_sa_instance_state"}

@router.put("/activities/{activity_id}", response_model=dict)
def update_activity(activity_id: int, activity_update: ActivityLogUpdate, db: Session = Depends(get_db)):
    db_activity = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    if not db_activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    update_data = activity_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_activity, key, value)

    db.commit()
    db.refresh(db_activity)
    return {k: v for k, v in db_activity.__dict__.items() if k != "_sa_instance_state"}

@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    db_activity = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    if not db_activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(db_activity)
    db.commit()
    return {"message": "Activity deleted successfully"}

# ------------------------------------------
# Reports Endpoints
# ------------------------------------------

@router.post("/reports/generate-weekly")
def generate_weekly_report(db: Session = Depends(get_db)):
    """Generate a weekly report from the last 7 days of activity logs."""
    try:
        # Calculate date range for weekly report
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        # Fetch activity logs for the date range
        logs = db.query(ActivityLog).filter(
            ActivityLog.timestamp >= datetime.combine(start_date, time.min),
            ActivityLog.timestamp <= datetime.combine(end_date, time.max)
        ).all()
        
        # Convert logs to dictionary format for processing
        logs_data = [
            {k: v for k, v in log.__dict__.items() if k != "_sa_instance_state"}
            for log in logs
        ]
        
        # Generate the report using the existing logic
        html_report = generate_weekly_report_html(
            start_date=start_date,
            end_date=end_date,
            logs_data=logs_data
        )
        
        return {"html_report": html_report}
    except Exception as e:
        logger.error(f"Error generating weekly report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------
# LLM Service Endpoints
# ------------------------------------------

class LLMProcessTextRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    text: str = Field(..., min_length=1, description="Text to be processed by LLM")

@router.post("/llm/process-text")
def process_text_with_llm(request: LLMProcessTextRequest):
    # Placeholder for LLM processing logic
    return {"response": f"Processed text: {request.text} (placeholder LLM response)"}

# ------------------------------------------
# Daily Report Endpoint
# ------------------------------------------

class DailyReportRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    date: Optional[str] = Field(
        None, 
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Date in YYYY-MM-DD format"
    )

@router.post("/reports/generate-daily")
def generate_daily_report(request: DailyReportRequest = None, db: Session = Depends(get_db)):
    """Generate a daily report summarizing activities by category for the last 24 hours."""
    try:
        if request and request.date:
            # Parse the provided date
            try:
                parsed_date = datetime.fromisoformat(request.date)
                start_date = parsed_date
                end_date = parsed_date + timedelta(hours=24)
            except ValueError as e:
                logger.error(f"Error parsing date parameter: {request.date}, error: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
        else:
            # Use current time for daily report
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=24)
        
        logger.info(f"Generating daily report from {start_date} to {end_date}")
        
        # Fetch activity logs for the date range
        logs = db.query(ActivityLog).filter(
            ActivityLog.timestamp >= start_date,
            ActivityLog.timestamp <= end_date
        ).all()
        
        # Convert logs to dictionary format for processing
        logs_data = [
            {k: v for k, v in log.__dict__.items() if k != "_sa_instance_state"}
            for log in logs
        ]
        
        # Generate the report using existing logic
        html_report = generate_daily_report_html(
            start_date=start_date,
            end_date=end_date,
            logs_data=logs_data
        )
        
        return {"html_report": html_report}
    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------
# Scheduler Endpoints
# ------------------------------------------

@router.get("/scheduler/status")
def get_scheduler_status():
    # Placeholder for scheduler status
    return {"job_count": 0, "jobs": [], "running": False}

# ------------------------------------------
# Settings Endpoints
# ------------------------------------------

class Category(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(..., min_length=1, description="Category name")
    groups: List[str] = Field(default_factory=list, description="List of group names in this category")

class SettingsUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    notificationInterval: int = Field(..., gt=0, description="Notification interval in minutes")
    audioDevice: str = Field(..., description="Audio device identifier")
    llmProvider: str = Field(..., description="LLM provider name")
    openRouterApiKey: str = Field(
        default="", 
        description="API key for OpenRouter service"
    )
    openRouterLLM: str = Field(
        default="", 
        description="OpenRouter model identifier"
    )
    lmstudioEndpoint: str = Field(
        default="http://localhost:1234/v1", 
        description="LM Studio API endpoint"
    )
    lmstudioModel: str = Field(
        default="default_model",
        description="Default LM Studio model"
    )
    lmstudioLogsModel: Optional[str] = Field(
        default=None,
        description="LM Studio model for log processing"
    )
    lmstudioReportsModel: Optional[str] = Field(
        default=None,
        description="LM Studio model for report generation"
    )
    categories: List[Category] = Field(
        default_factory=list,
        description="List of activity categories and their groups"
    )

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
        logger.info(f"Updating settings with: {json.dumps(updated_settings.model_dump(), indent=2)}")
        settings = db.query(Settings).first()
        if not settings:
            settings = Settings()
            db.add(settings)
            logger.info("Created new settings record")

        # Update fields from Pydantic model
        settings_dict = updated_settings.model_dump()
        logger.info(f"Current settings before update: {settings.model_dump()}")

        # Update scalar fields
        for field in ["notificationInterval", "audioDevice", "llmProvider",
                     "openRouterApiKey", "openRouterLLM", "lmstudioEndpoint",
                     "lmstudioModel"]:
            if field in settings_dict:
                setattr(settings, field, settings_dict[field])

        # Handle the new fields with special logic
        if "lmstudioLogsModel" in settings_dict and settings_dict["lmstudioLogsModel"] is not None:
            settings.lmstudioLogsModel = settings_dict["lmstudioLogsModel"]
        elif not settings.lmstudioLogsModel:  # If it's not set yet
            settings.lmstudioLogsModel = settings.lmstudioModel or "phi-3-mini-4k"

        if "lmstudioReportsModel" in settings_dict and settings_dict["lmstudioReportsModel"] is not None:
            settings.lmstudioReportsModel = settings_dict["lmstudioReportsModel"]
        elif not settings.lmstudioReportsModel:  # If it's not set yet
            settings.lmstudioReportsModel = settings.lmstudioModel or "gemma-7b"

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
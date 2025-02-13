# reports_api.py
from fastapi import APIRouter, Query
import os
import json
from datetime import datetime, timedelta, date
from models import SessionLocal, ActivityLog
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()

def generate_daily_report_for_date(report_date, logs_data):
    """
    Stub implementation for generating a daily report.
    Aggregates logs and creates a simple report, then saves it as a JSON file.
    """
    total_time = sum(log.get("duration_minutes", 0) for log in logs_data)
    time_by_group = {}
    for log in logs_data:
        group = log.get("group", "others")
        time_by_group[group] = time_by_group.get(group, 0) + log.get("duration_minutes", 0)
    
    report = {
        "executive_summary": {
            "total_time": total_time,
            "time_by_group": time_by_group,
            "key_insights": "This is a generated daily report for testing purposes."
        },
        "details": logs_data,
        "raw_data": logs_data
    }
    
    # Compute the reports directory relative to this file's location.
    base_dir = os.path.dirname(os.path.abspath(__file__))
    report_dir = os.path.join(base_dir, "..", "reports", "daily")
    os.makedirs(report_dir, exist_ok=True)
    report_filename = os.path.join(report_dir, f"{report_date}_report.json")
    logger.info("Looking for filE: " + report_filename)
    with open(report_filename, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    
    return report

@router.get("/daily-report")
def get_daily_report(requested_date: str = Query(None, alias="date")):
    try:
        if requested_date:
            report_date = datetime.strptime(requested_date, "%Y-%m-%d").date()
        else:
            report_date = date.today()  # Using the imported date class
    except Exception as e:
        return {"error": "Invalid date format. Expected YYYY-MM-DD."}
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    report_dir = os.path.join(base_dir, "..", "reports", "daily")
    report_filename = os.path.join(report_dir, f"{report_date}_report.json")
    
    logger.info("GET /daily-report endpoint called")
    logger.info("Looking for file: " + report_filename)
    logger.info("Received query parameter requested_date: " + str(requested_date))
    
    if os.path.exists(report_filename):
        with open(report_filename, "r", encoding="utf-8") as f:
            report_data = json.load(f)
        return report_data
    else:
        return {"message": f"No report found for {report_date}."}

@router.post("/force-daily-report")
def force_daily_report(date_str: str = Query(..., alias="date")):
    """
    Forces the generation of a daily report for the specified date (YYYY-MM-DD).
    """
    try:
        report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return {"error": "Invalid date format. Expected YYYY-MM-DD."}
    
    start_date = datetime.combine(report_date, datetime.min.time())
    end_date = start_date + timedelta(days=1)
    
    db = SessionLocal()
    try:
        logs = db.query(ActivityLog).filter(
            ActivityLog.timestamp >= start_date,
            ActivityLog.timestamp < end_date
        ).all()
        logs_data = [
            {k: v for k, v in log.__dict__.items() if k != "_sa_instance_state"}
            for log in logs
        ]
    finally:
        db.close()
        
    
    report = generate_daily_report_for_date(report_date, logs_data)
    return {"message": f"Daily report for {report_date} generated successfully.", "report": report}
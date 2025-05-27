import json
import logging
import os
from datetime import datetime, date, time
from sqlalchemy import and_
from .models import SessionLocal, ActivityLog
from .report_templates import generate_html_report, ChartData, DailyTimeBreakdown

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the reports directory
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")
WEEKLY_REPORTS_DIR = os.path.join(REPORTS_DIR, "weekly")

def generate_weekly_report_html(start_date, end_date, logs_data):
    """
    Generate an HTML weekly report using the correct function signature.
    
    Args:
        start_date: Start date of the report period
        end_date: End date of the report period
        logs_data: List of activity log dictionaries
        
    Returns:
        HTML string containing the report
    """
    logger.info(f"Generating weekly report HTML for {start_date} to {end_date}")
    
    # Initialize variables
    total_time = 0
    time_by_group = {}
    time_by_category = {}
    daily_breakdown = {}
    
    # If no logs, create a default empty report
    if not logs_data:
        return generate_html_report(
            start_date=start_date,
            end_date=end_date,
            total_time=0,
            time_by_group={"No Data": 0},
            time_by_category={"No Data": 0},
            daily_breakdown={},
            visualizations={},
            logs_data=[]
        )
    
    # Process logs to create time breakdowns
    for log in logs_data:
        # Update total time
        total_time += log["duration_minutes"]
        
        # Update group time with safe access
        group = log.get("group", "Uncategorized")
        if group not in time_by_group:
            time_by_group[group] = 0
        time_by_group[group] += log["duration_minutes"]
        
        # Update category time with safe access
        category = log.get("category", "Uncategorized")
        if category not in time_by_category:
            time_by_category[category] = 0
        time_by_category[category] += log["duration_minutes"]
        
        # Update daily breakdown
        # Handle timestamp with safe parsing - handle both string and datetime objects
        timestamp = log.get("timestamp")
        if timestamp is None:
            timestamp = "2025-01-01 00:00:00.000"
        
        # If it's already a datetime object, get the date directly
        if isinstance(timestamp, datetime):
            log_date = timestamp.date().strftime("%Y-%m-%d")
        # If it's a string, parse it
        elif isinstance(timestamp, str):
            try:
                log_date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f").date().strftime("%Y-%m-%d")
            except ValueError:
                # Try a different format if the first one fails
                try:
                    log_date = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S").date().strftime("%Y-%m-%d")
                except ValueError:
                    # Default to today if parsing fails
                    log_date = datetime.now().date().strftime("%Y-%m-%d")
        if log_date not in daily_breakdown:
            daily_breakdown[log_date] = DailyTimeBreakdown(
                total_time=0,
                time_by_group={},
                time_by_category={}
            )
        
        # Update daily time
        daily_breakdown[log_date].total_time += log["duration_minutes"]
        
        # Update daily group time
        if group not in daily_breakdown[log_date].time_by_group:
            daily_breakdown[log_date].time_by_group[group] = 0
        daily_breakdown[log_date].time_by_group[group] += log["duration_minutes"]
        
        # Update daily category time
        if category not in daily_breakdown[log_date].time_by_category:
            daily_breakdown[log_date].time_by_category[category] = 0
        daily_breakdown[log_date].time_by_category[category] += log["duration_minutes"]
    
    # Create visualizations dictionary
    visualizations = {}
    
    # Generate HTML report with the correct parameters
    html_report = generate_html_report(
        start_date=start_date,
        end_date=end_date,
        total_time=total_time,
        time_by_group=time_by_group,
        time_by_category=time_by_category,
        daily_breakdown=daily_breakdown,
        visualizations=visualizations,
        logs_data=logs_data
    )
    
    logger.info(f"Generated HTML report with length: {len(html_report)}")
    return html_report

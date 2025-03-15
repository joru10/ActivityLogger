import os
import logging
import json
from datetime import datetime, timedelta, time, date
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from sqlalchemy import and_, func
from fastapi import APIRouter
from models import SessionLocal, ActivityLog
# Only import functions that actually exist
from reports import generate_daily_report_for_date, generate_weekly_report as gen_weekly_report, DailyTimeBreakdown

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Create report directories if they don't exist
base_dir = os.path.dirname(os.path.abspath(__file__))
REPORTS_BASE_DIR = os.path.join(base_dir, "..", "reports")
DAILY_REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "daily")
WEEKLY_REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "weekly")
MONTHLY_REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "monthly")
QUARTERLY_REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "quarterly")
ANNUAL_REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "annual")

# Create all report directories
for directory in [DAILY_REPORTS_DIR, WEEKLY_REPORTS_DIR, MONTHLY_REPORTS_DIR, 
                  QUARTERLY_REPORTS_DIR, ANNUAL_REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Created report directory: {directory}")

# Initialize the scheduler
scheduler = BackgroundScheduler(
    jobstores={
        'default': MemoryJobStore()
    },
    executors={
        'default': ThreadPoolExecutor(20)
    },
    job_defaults={
        'coalesce': True,
        'max_instances': 1
    }
)

async def generate_daily_report(target_date=None):
    """
    Generate a daily report for the specified date or the previous day if no date is provided.
    This function is called automatically at the end of each day and can also be called manually.
    
    Args:
        target_date (date, optional): The date to generate the report for. Defaults to yesterday.
    """
    from models import SessionLocal, ActivityLog
    from reports import generate_daily_report_for_date
    
    if target_date is None:
        current_date = date.today()
        target_date = current_date - timedelta(days=1)
    
    logger.info(f"Generating daily report for {target_date}")
    
    try:
        # Get activity logs for the target date
        db = SessionLocal()
        start_date = datetime.combine(target_date, time.min)
        end_date = datetime.combine(target_date, time.max)
        
        logs = db.query(ActivityLog).filter(
            and_(
                ActivityLog.timestamp >= start_date,
                ActivityLog.timestamp < end_date
            )
        ).all()
        
        # Convert logs to the format expected by the report generator
        logs_data = [{
            "group": log.group,
            "category": log.category,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "duration_minutes": log.duration_minutes,
            "description": log.description
        } for log in logs]
        
        # Generate the report
        if logs_data:
            report_data = await reports.generate_daily_report_for_date(target_date, logs_data)
            
            # Save the report
            report_filename = os.path.join(
                DAILY_REPORTS_DIR, 
                f"daily_report_{target_date.strftime('%Y-%m-%d')}.json"
            )
            
            with open(report_filename, "w") as f:
                f.write(json.dumps(report_data, indent=2))
                
            logger.info(f"Daily report saved to {report_filename}")
            return report_data
        else:
            logger.info(f"No activity logs found for {target_date}, skipping report generation")
            return None
    except Exception as e:
        logger.error(f"Error generating daily report: {str(e)}")
        return None
    finally:
        if 'db' in locals():
            db.close()

async def generate_weekly_report():
    """
    Generate a weekly report for the previous week.
    This function is called automatically at the end of each week (Sunday).
    """
    # Add detailed logging for debugging
    logger.info("Starting weekly report generation in scheduler.py")
    
    try:
        current_date = date.today()
        logger.info(f"Current date: {current_date}")
        # Calculate the start and end of the previous week (Monday to Sunday)
        days_since_monday = current_date.weekday()
        logger.info(f"Days since Monday: {days_since_monday}")
        end_date = current_date - timedelta(days=days_since_monday + 1)  # Last Sunday
        start_date = end_date - timedelta(days=6)  # Last Monday
        logger.info(f"Week range: {start_date} to {end_date}")
        
        # First, ensure we have daily reports for each day in the week
        current_day = start_date
        while current_day <= end_date:
            # Check if daily report exists for this day
            daily_report_filename = os.path.join(
                DAILY_REPORTS_DIR, 
                f"daily_report_{current_day.strftime('%Y-%m-%d')}.json"
            )
            
            if not os.path.exists(daily_report_filename):
                logger.info(f"Daily report for {current_day} not found, generating it now")
                # Generate the daily report for this day
                await generate_daily_report(current_day)
            
            # Move to the next day
            current_day += timedelta(days=1)
        
        logger.info(f"Generating weekly report for {start_date} to {end_date}")
        # Get activity logs for the week
        db = SessionLocal()
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)
        
        logs = db.query(ActivityLog).filter(
            and_(
                ActivityLog.timestamp >= start_datetime,
                ActivityLog.timestamp <= end_datetime
            )
        ).all()
        
        # Convert logs to the format expected by the report generator
        logs_data = [{
            "group": log.group,
            "category": log.category,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "duration_minutes": log.duration_minutes,
            "description": log.description
        } for log in logs]
        
        # Generate the weekly report
        if logs_data:
            # Use the weekly report profile
            report_data = await gen_weekly_report(start_date, end_date, logs_data)
            
            # Save the report
            report_filename = os.path.join(
                WEEKLY_REPORTS_DIR, 
                f"weekly_report_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.json"
            )
            
            with open(report_filename, "w") as f:
                f.write(json.dumps(report_data, indent=2))
                
            logger.info(f"Weekly report saved to {report_filename}")
        else:
            logger.info(f"No activity logs found for week {start_date} to {end_date}, skipping report generation")
    
    except Exception as e:
        import traceback
        error_stack = traceback.format_exc()
        logger.error(f"Error generating weekly report: {str(e)}\n{error_stack}")
    finally:
        if 'db' in locals():
            db.close()

async def generate_monthly_report():
    """
    Generate a monthly report for the previous month.
    This function is called automatically at the end of each month.
    """
    # Add logging for monthly report generation
    logger.info("Starting monthly report generation")
    
    current_date = date.today()
    # Calculate the first day of the current month
    first_day_current_month = date(current_date.year, current_date.month, 1)
    # Calculate the last day of the previous month
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    # Calculate the first day of the previous month
    first_day_previous_month = date(last_day_previous_month.year, last_day_previous_month.month, 1)
    
    logger.info(f"Generating monthly report for {first_day_previous_month} to {last_day_previous_month}")
    
    # First, ensure we have daily reports for each day in the month
    current_day = first_day_previous_month
    while current_day <= last_day_previous_month:
        # Check if daily report exists for this day
        daily_report_filename = os.path.join(
            DAILY_REPORTS_DIR, 
            f"daily_report_{current_day.strftime('%Y-%m-%d')}.json"
        )
        
        if not os.path.exists(daily_report_filename):
            logger.info(f"Daily report for {current_day} not found, generating it now")
            # Generate the daily report for this day
            await generate_daily_report(current_day)
        
        # Move to the next day
        current_day += timedelta(days=1)
    
    try:
        # Get activity logs for the month
        db = SessionLocal()
        start_datetime = datetime.combine(first_day_previous_month, time.min)
        end_datetime = datetime.combine(last_day_previous_month, time.max)
        
        logs = db.query(ActivityLog).filter(
            and_(
                ActivityLog.timestamp >= start_datetime,
                ActivityLog.timestamp <= end_datetime
            )
        ).all()
        
        # Convert logs to the format expected by the report generator
        logs_data = [{
            "group": log.group,
            "category": log.category,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "duration_minutes": log.duration_minutes,
            "description": log.description
        } for log in logs]
        
        # Generate the monthly report
        if logs_data:
            logger.info("Generating monthly report with HTML content")
            
            # Calculate total time
            total_time = sum(log["duration_minutes"] for log in logs_data)
            
            # Calculate time by group and category
            time_by_group = {}
            time_by_category = {}
            daily_breakdown = {}
            
            # Process logs to get time breakdowns
            for log in logs_data:
                # Group breakdown
                group = log["group"]
                if group not in time_by_group:
                    time_by_group[group] = 0
                time_by_group[group] += log["duration_minutes"]
                
                # Category breakdown
                category = log["category"]
                if category not in time_by_category:
                    time_by_category[category] = {}
                if group not in time_by_category[category]:
                    time_by_category[category][group] = 0
                time_by_category[category][group] += log["duration_minutes"]
                
                # Daily breakdown
                log_date = datetime.strptime(log["timestamp"].split()[0], "%Y-%m-%d").date()
                day_str = log_date.strftime("%Y-%m-%d")
                
                if day_str not in daily_breakdown:
                    daily_breakdown[day_str] = DailyTimeBreakdown(
                        date=day_str,
                        total_minutes=0,
                        time_by_group={},
                        time_by_category={}
                    )
                
                daily_breakdown[day_str].total_minutes += log["duration_minutes"]
                
                if group not in daily_breakdown[day_str].time_by_group:
                    daily_breakdown[day_str].time_by_group[group] = 0
                daily_breakdown[day_str].time_by_group[group] += log["duration_minutes"]
                
                if category not in daily_breakdown[day_str].time_by_category:
                    daily_breakdown[day_str].time_by_category[category] = 0
                daily_breakdown[day_str].time_by_category[category] += log["duration_minutes"]
            
            # Create visualizations dictionary
            visualizations = {}
            
            # Generate HTML report with embedded charts
            from report_templates import generate_html_report
            html_report = generate_html_report(first_day_previous_month, last_day_previous_month, 
                                             total_time, time_by_group, time_by_category, 
                                             daily_breakdown, visualizations, logs_data)
            
            # Create the monthly report with HTML only
            from reports import MonthlyReport
            monthly_report = MonthlyReport(
                html_report=html_report
            )
            
            # Convert to dictionary for JSON serialization
            report_data = monthly_report.model_dump()
            
            # Save the report
            month_name = first_day_previous_month.strftime("%B")
            year = first_day_previous_month.year
            report_filename = os.path.join(
                MONTHLY_REPORTS_DIR, 
                f"monthly_report_{year}_{month_name}.json"
            )
            
            with open(report_filename, "w") as f:
                f.write(json.dumps(report_data, indent=2))
                
            logger.info(f"Monthly report saved to {report_filename}")
        else:
            logger.info(f"No activity logs found for month {first_day_previous_month} to {last_day_previous_month}, skipping report generation")
    
    except Exception as e:
        logger.error(f"Error generating monthly report: {str(e)}")
    finally:
        db.close()

async def generate_quarterly_report():
    """
    Generate a quarterly report for the previous quarter.
    This function is called automatically at the end of each quarter (March, June, September, December).
    """
    # Add logging for quarterly report generation
    logger.info("Starting quarterly report generation")
    
    current_date = date.today()
    current_month = current_date.month
    current_year = current_date.year
    
    # Determine the previous quarter
    previous_quarter = (current_month - 1) // 3
    if previous_quarter == 0:
        previous_quarter = 4
        year = current_year - 1
    else:
        year = current_year
    
    # Calculate the start and end dates of the previous quarter
    start_month = (previous_quarter - 1) * 3 + 1
    end_month = previous_quarter * 3
    
    # Create dates using date constructor to avoid datetime.datetime issues
    start_date = date(year, start_month, 1)
    if end_month == 12:
        end_date = date(year, end_month, 31)
    else:
        next_month_date = date(year, end_month + 1, 1)
        end_date = next_month_date - timedelta(days=1)
    
    logger.info(f"Generating quarterly report for Q{previous_quarter} {year} ({start_date} to {end_date})")
    
    try:
        # Get activity logs for the quarter
        db = SessionLocal()
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)
        
        logs = db.query(ActivityLog).filter(
            and_(
                ActivityLog.timestamp >= start_datetime,
                ActivityLog.timestamp <= end_datetime
            )
        ).all()
        
        # Convert logs to the format expected by the report generator
        logs_data = [{
            "group": log.group,
            "category": log.category,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "duration_minutes": log.duration_minutes,
            "description": log.description
        } for log in logs]
        
        # Generate the quarterly report
        if logs_data:
            logger.info("Generating quarterly report with HTML content")
            
            # Calculate total time
            total_time = sum(log["duration_minutes"] for log in logs_data)
            
            # Calculate time by group and category
            time_by_group = {}
            time_by_category = {}
            daily_breakdown = {}
            
            # Process logs to get time breakdowns
            for log in logs_data:
                # Group breakdown
                group = log["group"]
                if group not in time_by_group:
                    time_by_group[group] = 0
                time_by_group[group] += log["duration_minutes"]
                
                # Category breakdown
                category = log["category"]
                if category not in time_by_category:
                    time_by_category[category] = {}
                if group not in time_by_category[category]:
                    time_by_category[category][group] = 0
                time_by_category[category][group] += log["duration_minutes"]
                
                # Daily breakdown
                log_date = datetime.strptime(log["timestamp"].split()[0], "%Y-%m-%d").date()
                day_str = log_date.strftime("%Y-%m-%d")
                
                if day_str not in daily_breakdown:
                    daily_breakdown[day_str] = DailyTimeBreakdown(
                        date=day_str,
                        total_minutes=0,
                        time_by_group={},
                        time_by_category={}
                    )
                
                daily_breakdown[day_str].total_minutes += log["duration_minutes"]
                
                if group not in daily_breakdown[day_str].time_by_group:
                    daily_breakdown[day_str].time_by_group[group] = 0
                daily_breakdown[day_str].time_by_group[group] += log["duration_minutes"]
                
                if category not in daily_breakdown[day_str].time_by_category:
                    daily_breakdown[day_str].time_by_category[category] = 0
                daily_breakdown[day_str].time_by_category[category] += log["duration_minutes"]
            
            # Create visualizations dictionary
            visualizations = {}
            
            # Generate HTML report with embedded charts
            from report_templates import generate_html_report
            html_report = generate_html_report(start_date, end_date, 
                                             total_time, time_by_group, time_by_category, 
                                             daily_breakdown, visualizations, logs_data)
            
            # Create the quarterly report with HTML only
            from reports import QuarterlyReport
            quarterly_report = QuarterlyReport(
                html_report=html_report
            )
            
            # Convert to dictionary for JSON serialization
            report_data = quarterly_report.model_dump()
            
            # Save the report
            report_filename = os.path.join(
                QUARTERLY_REPORTS_DIR, 
                f"quarterly_report_Q{previous_quarter}_{year}.json"
            )
            
            with open(report_filename, "w") as f:
                f.write(json.dumps(report_data, indent=2))
                
            logger.info(f"Quarterly report saved to {report_filename}")
        else:
            logger.info(f"No activity logs found for quarter Q{previous_quarter} {year}, skipping report generation")
    
    except Exception as e:
        logger.error(f"Error generating quarterly report: {str(e)}")
    finally:
        db.close()

async def generate_annual_report():
    """
    Generate an annual report for the previous year.
    This function is called automatically at the end of each year.
    """
    # Add logging for annual report generation
    logger.info("Starting annual report generation")
    
    current_date = date.today()
    previous_year = current_date.year - 1
    
    # Create dates using date constructor to avoid datetime.datetime issues
    start_date = date(previous_year, 1, 1)
    end_date = date(previous_year, 12, 31)
    
    logger.info(f"Generating annual report for {previous_year} ({start_date} to {end_date})")
    
    try:
        # Get activity logs for the year
        db = SessionLocal()
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)
        
        logs = db.query(ActivityLog).filter(
            and_(
                ActivityLog.timestamp >= start_datetime,
                ActivityLog.timestamp <= end_datetime
            )
        ).all()
        
        # Convert logs to the format expected by the report generator
        logs_data = [{
            "group": log.group,
            "category": log.category,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "duration_minutes": log.duration_minutes,
            "description": log.description
        } for log in logs]
        
        # Generate the annual report
        if logs_data:
            logger.info("Generating annual report with HTML content")
            
            # Calculate total time
            total_time = sum(log["duration_minutes"] for log in logs_data)
            
            # Calculate time by group and category
            time_by_group = {}
            time_by_category = {}
            daily_breakdown = {}
            
            # Process logs to get time breakdowns
            for log in logs_data:
                # Group breakdown
                group = log["group"]
                if group not in time_by_group:
                    time_by_group[group] = 0
                time_by_group[group] += log["duration_minutes"]
                
                # Category breakdown
                category = log["category"]
                if category not in time_by_category:
                    time_by_category[category] = {}
                if group not in time_by_category[category]:
                    time_by_category[category][group] = 0
                time_by_category[category][group] += log["duration_minutes"]
                
                # Daily breakdown
                log_date = datetime.strptime(log["timestamp"].split()[0], "%Y-%m-%d").date()
                day_str = log_date.strftime("%Y-%m-%d")
                
                if day_str not in daily_breakdown:
                    daily_breakdown[day_str] = DailyTimeBreakdown(
                        date=day_str,
                        total_minutes=0,
                        time_by_group={},
                        time_by_category={}
                    )
                
                daily_breakdown[day_str].total_minutes += log["duration_minutes"]
                
                if group not in daily_breakdown[day_str].time_by_group:
                    daily_breakdown[day_str].time_by_group[group] = 0
                daily_breakdown[day_str].time_by_group[group] += log["duration_minutes"]
                
                if category not in daily_breakdown[day_str].time_by_category:
                    daily_breakdown[day_str].time_by_category[category] = 0
                daily_breakdown[day_str].time_by_category[category] += log["duration_minutes"]
            
            # Create visualizations dictionary
            visualizations = {}
            
            # Generate HTML report with embedded charts
            from report_templates import generate_html_report
            html_report = generate_html_report(start_date, end_date, 
                                             total_time, time_by_group, time_by_category, 
                                             daily_breakdown, visualizations, logs_data)
            
            # Create the annual report with HTML only
            from reports import AnnualReport
            annual_report = AnnualReport(
                html_report=html_report
            )
            
            # Convert to dictionary for JSON serialization
            report_data = annual_report.model_dump()
            
            # Save the report
            report_filename = os.path.join(
                ANNUAL_REPORTS_DIR, 
                f"annual_report_{previous_year}.json"
            )
            
            with open(report_filename, "w") as f:
                f.write(json.dumps(report_data, indent=2))
                
            logger.info(f"Annual report saved to {report_filename}")
        else:
            logger.info(f"No activity logs found for year {previous_year}, skipping report generation")
    
    except Exception as e:
        logger.error(f"Error generating annual report: {str(e)}")
    finally:
        db.close()

def start_scheduler():
    """
    Start the background scheduler with all the scheduled jobs.
    """
    import json  # Import here to avoid circular imports
    
    if scheduler.running:
        logger.warning("Scheduler is already running")
        return
    
    # Schedule daily reports to run at 00:05 every day
    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=0, minute=5),
        id='daily_report',
        name='Generate Daily Report',
        replace_existing=True
    )
    
    # Schedule weekly reports to run at 00:10 every Monday
    scheduler.add_job(
        generate_weekly_report,
        CronTrigger(day_of_week='mon', hour=0, minute=10),
        id='weekly_report',
        name='Generate Weekly Report',
        replace_existing=True
    )
    
    # Schedule monthly reports to run at 00:15 on the 1st day of each month
    scheduler.add_job(
        generate_monthly_report,
        CronTrigger(day=1, hour=0, minute=15),
        id='monthly_report',
        name='Generate Monthly Report',
        replace_existing=True
    )
    
    # Schedule quarterly reports to run at 00:20 on the 1st day of January, April, July, and October
    scheduler.add_job(
        generate_quarterly_report,
        CronTrigger(month='1,4,7,10', day=1, hour=0, minute=20),
        id='quarterly_report',
        name='Generate Quarterly Report',
        replace_existing=True
    )
    
    # Schedule annual reports to run at 00:25 on January 1st
    scheduler.add_job(
        generate_annual_report,
        CronTrigger(month=1, day=1, hour=0, minute=25),
        id='annual_report',
        name='Generate Annual Report',
        replace_existing=True
    )
    
    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started with all report generation jobs")

def stop_scheduler():
    """
    Stop the background scheduler.
    """
    if not scheduler.running:
        logger.warning("Scheduler is not running")
        return
    
    scheduler.shutdown()
    logger.info("Scheduler stopped")

@router.get("/status")
async def get_scheduler_status():
    """Get the status of the scheduler and its jobs"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    
    return {
        "running": scheduler.running,
        "jobs": jobs,
        "job_count": len(jobs)
    }

@router.post("/trigger/{report_type}")
async def trigger_report(report_type: str):
    """Manually trigger a report generation job"""
    valid_types = ["daily", "weekly", "monthly", "quarterly", "annual"]
    if report_type not in valid_types:
        return {"error": f"Invalid report type. Must be one of: {', '.join(valid_types)}"}
    
    try:
        if report_type == "daily":
            await generate_daily_report()
        elif report_type == "weekly":
            await generate_weekly_report()
        elif report_type == "monthly":
            await generate_monthly_report()
        elif report_type == "quarterly":
            await generate_quarterly_report()
        elif report_type == "annual":
            await generate_annual_report()
        
        return {"success": True, "message": f"{report_type.capitalize()} report generation triggered successfully"}
    except Exception as e:
        import traceback
        error_stack = traceback.format_exc()
        logger.error(f"Error triggering {report_type} report: {str(e)}\n{error_stack}")
        return {"success": False, "error": str(e), "traceback": error_stack}

# For testing purposes, you can run this file directly
if __name__ == "__main__":
    start_scheduler()

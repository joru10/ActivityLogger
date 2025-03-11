import os
import json
import logging
import yaml
from datetime import datetime, timedelta, date, time
from fastapi import HTTPException
from sqlalchemy import and_
from models import SessionLocal, ActivityLog, Settings
from config import get_categories_json
from fastapi import APIRouter, Query, HTTPException, Response
from pydantic import BaseModel, Field, ValidationError
import httpx
import sys
import traceback
from pathlib import Path

# Import the report templates module
from report_templates import generate_html_report

# Import model classes from report_templates
from report_templates import DailyTimeBreakdown, ChartData

class WeeklyReportExecutiveSummary(BaseModel):
    total_time: int
    time_by_group: dict[str, int]
    time_by_category: dict[str, int] = {}
    daily_breakdown: dict[str, DailyTimeBreakdown]
    progress_report: str
    key_insights: list[str] = []
    recommendations: list[str] = []

class WeeklyReport(BaseModel):
    html_report: str = ""  # HTML version with embedded charts

class MonthlyReport(BaseModel):
    html_report: str = ""  # HTML version with embedded charts

class QuarterlyReport(BaseModel):
    html_report: str = ""  # HTML version with embedded charts

class AnnualReport(BaseModel):
    html_report: str = ""  # HTML version with embedded charts

# Add json2csv directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'json2csv'))
from json2csv.json2csv import JSON2CSV

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Setup reports directory
base_dir = os.path.dirname(os.path.abspath(__file__))
REPORTS_BASE_DIR = os.path.join(base_dir, "..", "reports")
REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "daily")
WEEKLY_REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "weekly")
MONTHLY_REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "monthly")
QUARTERLY_REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "quarterly")
ANNUAL_REPORTS_DIR = os.path.join(REPORTS_BASE_DIR, "annual")

# Create all report directories
for directory in [REPORTS_DIR, WEEKLY_REPORTS_DIR, MONTHLY_REPORTS_DIR, 
                  QUARTERLY_REPORTS_DIR, ANNUAL_REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Report directory set to: {os.path.abspath(directory)}")

router = APIRouter()

def extract_json_from_response(response: str) -> dict:
    """Extract and validate JSON from LLM response"""
    if response.startswith('```'):
        first_newline = response.find('\n')
        if first_newline != -1:
            last_marker = response.rfind('```')
            if last_marker != -1:
                response = response[first_newline + 1:last_marker].strip()
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        raise ValueError("Invalid JSON response from LLM")

async def call_llm_api(prompt: str) -> dict:
    """Direct LLM API call with improved error handling"""
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings:
            raise ValueError("Settings not configured")
            
        url = f"{settings.lmstudioEndpoint}/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": settings.lmstudioModel,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional activity report analyzer. Return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        logger.info(f"Calling LMStudio with model: {settings.lmstudioModel}")
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                try:

                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code != 200:
                        raise ValueError(f"LLM API error: {response.text}")
                    
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    return extract_json_from_response(content)
                except Exception as e:
                    logger.error(f"An error occurred: {e}")

                    
            except httpx.ReadTimeout:
                logger.error("LLM API timeout - try loading the model first")
                raise ValueError("LLM API timeout - ensure model is ready")
            except httpx.ConnectError:
                logger.error("Could not connect to LLM - check if it's running")
                raise ValueError("Could not connect to LLM - ensure it's running")
            except Exception as e:
                logger.error(f"Error during LLM API call: {str(e)}")
                raise ValueError(f"LLM API error: {str(e)}")
    finally:
        db.close()

def load_report_profile(profile_name: str) -> str:
    """Loads the YAML profile for a given report."""
    profile_path = os.path.join(base_dir, "..", "profiles", f"{profile_name}.yaml")
    if not os.path.exists(profile_path):
        logger.error(f"Profile {profile_name} not found at {profile_path}")
        return ""
    
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = yaml.safe_load(f)
    prompt_template = profile_data.get("prompt", "")
    categories_str = get_categories_json()
    return prompt_template.replace("{categories_json}", categories_str)

async def generate_daily_report_for_date(report_date, logs_data):
    """Generates a daily report from actual logs using LLM."""
    profile_prompt = load_report_profile('ActivityReports_Daily')
    logger.info(f"Generating report for {report_date} with {len(logs_data)} logs")
    logger.info("Entering generate_daily_report_for_date")
    
    if not logs_data:
        logger.warning("No activities found for this date")
        return {
            "executive_summary": {
                "total_time": 0,
                "time_by_group": {},
                "progress_report": "No activities recorded for this date."
            },
            "details": [],
            "markdown_report": "# Daily Report\n\nNo activities recorded for this date."
        }

    try:
        # Calculate actual totals
        total_time = sum(log["duration_minutes"] for log in logs_data)
        time_by_group = {}
        for log in logs_data:
            group = log.get("group", "Other")  # Provide a default value
            duration = log["duration_minutes"]
            time_by_group[group] = time_by_group.get(group, 0) + duration

        # Prepare prompt for LLM
        logs_json = json.dumps(logs_data, indent=2)
        prompt = f"{profile_prompt}\n\nReport Date: {report_date}\nTotal Time: {total_time}\nTime by Group: {json.dumps(time_by_group, indent=2)}\nActivities:\n{logs_json}"
        logger.info(f"Prompt being sent to LLM: {prompt}")
        logger.info("Calling LLM API...")
        llm_response = await call_llm_api(prompt)
        logger.info("LLM response received")
        logger.info(f"LLM response: {llm_response}")
        
        # Validate and return LLM response
        try:
            if isinstance(llm_response, dict):
                required_fields = ['executive_summary', 'details', 'markdown_report']
                if all(field in llm_response for field in required_fields):
                    logger.info("Valid LLM response received")
                    return llm_response
            
            logger.error("Invalid LLM response structure")
            raise ValueError("Invalid LLM response structure")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing or validating LLM response: {e}")
            raise

    except Exception as e:
        logger.error(f"Error in report generation: {str(e)}")
        logger.info(f"Exception details: {e}")
        logger.warning("Falling back to basic report structure")
        return {
            "executive_summary": {
                "total_time": total_time,
                "time_by_group": time_by_group,
                "progress_report": f"Basic report generated from {len(logs_data)} activities."
            },
            "details": logs_data,
            "markdown_report": f"# Daily Report\n\n**Total Time:** {total_time} minutes\n\n" + 
                             "**Time by Group:**\n" + 
                             "\n".join([f"- {k}: {v} minutes" for k, v in time_by_group.items()])
        }
         
@router.post("/force-daily-report")
async def force_daily_report(date_str: str = Query(..., alias="date")):
    """Force generates a report for a specific date using actual DB data."""
    logger.info(f"Entering force_daily_report with date: {date_str}")
    try:
        # Parse date string to date object
        year, month, day = map(int, date_str.split('-'))
        report_date = date(year, month, day)
        logger.info(f"Force generating report for date: {report_date}")
        
        db = SessionLocal()
        try:
            # Steps 1-3 remain the same...
            start_date = datetime.combine(report_date, time.min)
            end_date = datetime.combine(report_date + timedelta(days=1), time.min)
            logger.info(f"Query range: start={start_date.isoformat()}, end={end_date.isoformat()}")

            query = db.query(ActivityLog).filter(
                ActivityLog.timestamp >= start_date,
                ActivityLog.timestamp < end_date
            )
            activities = query.all()
            
            logs_data = [
                {
                    "group": activity.group,
                    "timestamp": activity.timestamp.isoformat(),
                    "duration_minutes": activity.duration_minutes,
                    "description": activity.description or ""
                }
                for activity in activities
            ]
            
        finally:
            db.close()

        # Step 4: Generate Report - Add await here
        logger.info(f"Generating report with {len(logs_data)} activities")
        report_data = await generate_daily_report_for_date(report_date, logs_data)

        if not report_data:
            raise ValueError("Failed to generate report data")

        # Step 5: Save Report
        report_filename = os.path.join(
            REPORTS_DIR, 
            f"{report_date.strftime('%Y-%m-%d')}_report.json"
        )
        
        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        return {
            "message": f"Daily report for {report_date} generated successfully.",
            "report": report_data,
            "debug_info": {
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "activities_found": len(logs_data),
                "report_file": report_filename
            }
        }
        
    except ValueError as e:
        logger.error(f"Value error in force_daily_report: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in force_daily_report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/daily-report")
async def get_daily_report(requested_date: str = Query(None, alias="date")):
    """Fetches an existing report for the given date."""
    try:
        if requested_date:
            year, month, day = map(int, requested_date.split('-'))
            report_date = date(year, month, day)
        else:
            report_date = date.today()
        
        report_filename = os.path.join(REPORTS_DIR, f"{report_date.strftime('%Y-%m-%d')}_report.json")
        logger.info(f"Looking for report file: {report_filename}")
        
        if os.path.exists(report_filename):
            with open(report_filename, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            logger.warning(f"Report not found: {report_filename}")
            return {"message": f"No report found for {report_date}"}
            
    except Exception as e:
        logger.error(f"Error in get_daily_report: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# New function to generate weekly report
async def generate_weekly_report(start_date: date, end_date: date, logs_data: list[dict]):
    """Generates a weekly report for a given period with detailed visualizations."""
    profile_prompt = load_report_profile('ActivityReports_Weekly')
    logger.info(f"Generating weekly report from {start_date} to {end_date} with {len(logs_data)} logs")
    
    # Handle empty logs case
    if not logs_data:
        logger.warning("No activities found for this period")
        empty_report = WeeklyReport(
            executive_summary=WeeklyReportExecutiveSummary(
                total_time=0,
                time_by_group={},
                daily_breakdown={},
                progress_report="No activities recorded for this period."
            ),
            details=[],
            markdown_report="# Weekly Report\n\nNo activities recorded for this period.",
            html_report="<h1>Weekly Report</h1><p>No activities recorded for this period.</p>"
        )
        return empty_report.model_dump()
    
    try:
        # Calculate basic statistics
        total_time = sum(log["duration_minutes"] for log in logs_data)
        
        # Group data by different dimensions
        time_by_group = {}
        time_by_category = {}
        time_by_day = {}
        daily_breakdown = {}
        
        # Process each log entry
        for log in logs_data:
            # Extract data
            group = log.get("group", "Other")
            category = log.get("category", "Other")
            duration = log["duration_minutes"]
            timestamp = log["timestamp"]
            day = timestamp.split()[0]  # Extract YYYY-MM-DD part
            
            # Aggregate by group
            time_by_group[group] = time_by_group.get(group, 0) + duration
            
            # Aggregate by category
            time_by_category[category] = time_by_category.get(category, 0) + duration
            
            # Aggregate by day
            if day not in time_by_day:
                time_by_day[day] = 0
            time_by_day[day] += duration
            
            # Create detailed daily breakdown
            if day not in daily_breakdown:
                daily_breakdown[day] = DailyTimeBreakdown(
                    total_time=0,
                    time_by_group={},
                    time_by_category={}
                )
            
            daily_breakdown[day].total_time += duration
            daily_breakdown[day].time_by_group[group] = daily_breakdown[day].time_by_group.get(group, 0) + duration
            daily_breakdown[day].time_by_category[category] = daily_breakdown[day].time_by_category.get(category, 0) + duration
        
        # Create visualization data
        visualizations = {
            "daily_activity": ChartData(
                chart_type="bar",
                labels=list(time_by_day.keys()),
                datasets=[{
                    "label": "Minutes",
                    "data": list(time_by_day.values()),
                    "backgroundColor": "rgba(54, 162, 235, 0.5)"
                }],
                title="Daily Activity Distribution",
                description="Time spent on activities each day of the week"
            ),
            "group_distribution": ChartData(
                chart_type="pie",
                labels=list(time_by_group.keys()),
                datasets=[{
                    "data": list(time_by_group.values()),
                    "backgroundColor": [
                        "rgba(255, 99, 132, 0.5)",
                        "rgba(54, 162, 235, 0.5)",
                        "rgba(255, 206, 86, 0.5)",
                        "rgba(75, 192, 192, 0.5)",
                        "rgba(153, 102, 255, 0.5)",
                        "rgba(255, 159, 64, 0.5)"
                    ]
                }],
                title="Activity Distribution by Group",
                description="Breakdown of time spent on different activity groups"
            ),
            "category_distribution": ChartData(
                chart_type="pie",
                labels=list(time_by_category.keys()),
                datasets=[{
                    "data": list(time_by_category.values()),
                    "backgroundColor": [
                        "rgba(255, 99, 132, 0.5)",
                        "rgba(54, 162, 235, 0.5)",
                        "rgba(255, 206, 86, 0.5)",
                        "rgba(75, 192, 192, 0.5)",
                        "rgba(153, 102, 255, 0.5)",
                        "rgba(255, 159, 64, 0.5)"
                    ]
                }],
                title="Activity Distribution by Category",
                description="Breakdown of time spent on different activity categories"
            )
        }
        
        # Generate HTML report with embedded charts using the imported function
        html_report = generate_html_report(start_date, end_date, total_time, time_by_group, time_by_category, daily_breakdown, visualizations, logs_data)
        
        # Prepare data for LLM
        logs_json = json.dumps(logs_data, indent=2)
        prompt = f"{profile_prompt}\n\nReport Period: {start_date} to {end_date}\nTotal Time: {total_time}\nTime by Group: {json.dumps(time_by_group, indent=2)}\nTime by Category: {json.dumps(time_by_category, indent=2)}\nDaily Breakdown: {json.dumps({k: v.total_time for k, v in daily_breakdown.items()}, indent=2)}\nActivities:\n{logs_json}"
        
        logger.info("Calling LLM API for weekly report...")
        llm_response = await call_llm_api(prompt)
        logger.info("LLM response received")
        
        # Check if the response is a string containing JSON markers
        if isinstance(llm_response, str):
            try:
                # Use the extract_json_from_response helper
                report_data = extract_json_from_response(llm_response)
                if isinstance(report_data, dict):
                    llm_response = report_data
            except Exception as e:
                logger.error(f"Error extracting JSON from LLM response: {str(e)}")
        
        if isinstance(llm_response, dict):
            try:
                # Validate response using Pydantic model
                report = WeeklyReport(**llm_response)
                # Add the HTML report to the report object
                report.html_report = html_report
                logger.info("Valid LLM response received and validated")
                # Save the report to a file
                report_filename = f"weekly_report_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.json"
                report_path = os.path.join(WEEKLY_REPORTS_DIR, report_filename)
                os.makedirs(WEEKLY_REPORTS_DIR, exist_ok=True)
                with open(report_path, 'w') as f:
                    json.dump(report.model_dump(), f, indent=2)
                logger.info(f"Weekly report saved to {report_path}")
                return report.model_dump()
            except ValidationError as e:
                logger.error(f"Validation error in LLM response: {str(e)}")
                raise ValueError(f"Invalid LLM response structure: {str(e)}")
        
        logger.error("Invalid LLM response structure for weekly report")
        raise ValueError("Invalid LLM response structure")
    except Exception as e:
        logger.error(f"Error generating weekly report: {str(e)}")
        logger.warning("Falling back to basic weekly report structure")
        # Create daily breakdown
        daily_breakdown = {}
        for log in logs_data:
            day = log["timestamp"][:10]  # Get YYYY-MM-DD part
            if day not in daily_breakdown:
                daily_breakdown[day] = DailyTimeBreakdown(
                    total_time=0,
                    time_by_group={}
                )
            daily_breakdown[day].total_time += log["duration_minutes"]
            group = log["group"]
            daily_breakdown[day].time_by_group[group] = daily_breakdown[day].time_by_group.get(group, 0) + log["duration_minutes"]

        basic_report = WeeklyReport(
            executive_summary=WeeklyReportExecutiveSummary(
                total_time=total_time,
                time_by_group=time_by_group,
                daily_breakdown=daily_breakdown,
                progress_report=f"Basic report generated from {len(logs_data)} activities."
            ),
            details=logs_data,
            markdown_report=f"# Weekly Report\n\n**Total Time:** {total_time} minutes\n\n**Time by Group:**\n" + "\n".join([f"- {k}: {v} minutes" for k, v in time_by_group.items()]),
            html_report=html_report
        )
        
        # Save the basic report to a file
        report_filename = f"weekly_report_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.json"
        report_path = os.path.join(WEEKLY_REPORTS_DIR, report_filename)
        os.makedirs(WEEKLY_REPORTS_DIR, exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(basic_report.model_dump(), f, indent=2)
        logger.info(f"Basic weekly report saved to {report_path}")
        return basic_report.model_dump()

@router.get("/weekly-report")
async def get_weekly_report(date: str):
    """Get the weekly report for the week containing the specified date."""
    try:
        # Log starting debug info
        logger.info(f"Starting weekly report generation for date: {date}")
        
        # Parse the date string to a date object
        try:
            year, month, day = map(int, date.split('-'))
            logger.info(f"Parsed date components: year={year}, month={month}, day={day}")
            # Import the date class explicitly to avoid name conflicts
            from datetime import date as date_class
            target_date = date_class(year, month, day)
            logger.info(f"Created target_date: {target_date}")
        except Exception as e:
            logger.error(f"Error parsing date: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid date format. Please use YYYY-MM-DD format. Error: {str(e)}")
        
        # Calculate the start and end of the week containing the target date
        days_since_monday = target_date.weekday()  # 0 = Monday, 6 = Sunday
        logger.info(f"Days since Monday: {days_since_monday}")
        # Calculate the Monday (start) of the week
        start_date = target_date - timedelta(days=days_since_monday)
        # Calculate the Sunday (end) of the week
        end_date = start_date + timedelta(days=6)
        logger.info(f"Week range: {start_date} to {end_date}")
        
        # Create the directory for weekly reports if it doesn't exist
        if not os.path.exists(WEEKLY_REPORTS_DIR):
            os.makedirs(WEEKLY_REPORTS_DIR, exist_ok=True)
            logger.info(f"Created weekly reports directory at {WEEKLY_REPORTS_DIR}")
        
        # Check for an existing report first
        report_filename = f"weekly_report_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.json"
        report_path = os.path.join(WEEKLY_REPORTS_DIR, report_filename)
        logger.info(f"Looking for existing report at: {report_path}")
        
        if os.path.exists(report_path):
            logger.info("Found existing report, loading it")
            try:
                with open(report_path, 'r') as f:
                    report_data = json.load(f)
                # Validate the loaded report using Pydantic
                report = WeeklyReport(**report_data)
                logger.info("Successfully loaded and validated existing report")
                return report.model_dump()
            except Exception as e:
                logger.error(f"Error loading existing report: {e}")
                # Continue to generate a new report if there's an error loading the existing one
        
        # Generate a new report
        logger.info(f"Generating new weekly report for {start_date} to {end_date}")
        
        # Create a database session
        db = SessionLocal()
        
        # Convert date objects to datetime objects for database query
        try:
            # Explicitly import datetime and time to avoid conflicts
            from datetime import datetime as dt, time as tm
            start_datetime = dt.combine(start_date, tm.min)  # Start of day
            end_datetime = dt.combine(end_date, tm.max)      # End of day
            logger.info(f"Query datetime range: {start_datetime} to {end_datetime}")
        except Exception as e:
            logger.error(f"Error creating datetime objects: {e}")
            raise HTTPException(status_code=500, detail=f"Server error creating datetime objects: {str(e)}")
        
        # Query the database for activity logs in the specified date range
        try:
            logger.info("Querying logs from database")
            logs = db.query(ActivityLog).filter(
                and_(
                    ActivityLog.timestamp >= start_datetime,
                    ActivityLog.timestamp <= end_datetime
                )
            ).all()
            logger.info(f"Found {len(logs)} logs in date range")
        except Exception as e:
            logger.error(f"Database query error: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

        # Check if we have any logs
        if not logs:
            logger.warning(f"No activity logs found for week {start_date} to {end_date}")
            
            # Create empty data structures for the report
            time_by_group = {}
            time_by_category = {}
            daily_breakdown = {}
            visualizations = {}
            
            # Generate an empty HTML report
            html_report = generate_html_report(start_date, end_date, 0, time_by_group, 
                                             time_by_category, daily_breakdown, visualizations, [])
            
            # Create a basic empty report with HTML only
            basic_report = WeeklyReport(
                html_report=html_report
            )
            
            # Save the empty report
            report_path = os.path.join(WEEKLY_REPORTS_DIR, report_filename)
            with open(report_path, 'w') as f:
                json.dump(basic_report.model_dump(), f, indent=2)
            logger.info(f"Saved empty weekly report to {report_path}")
            return basic_report.model_dump()
            
        # Convert logs to the format expected by the report generator
        try:
            logger.info("Converting logs to report format")
            logs_data = [{
                "group": log.group,
                "category": log.category,
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "duration_minutes": log.duration_minutes,
                "description": log.description
            } for log in logs]
        except Exception as e:
            logger.error(f"Error converting logs: {e}")
            raise HTTPException(status_code=500, detail=f"Error converting logs: {str(e)}")
            
        # Try to generate the full report with LLM
        try:
            logger.info("Calling generate_weekly_report with data")
            report_data = await generate_weekly_report(start_date, end_date, logs_data)
            logger.info("Weekly report generation completed successfully")
            
            # Log the keys in the report_data to debug
            logger.info(f"Report data keys: {list(report_data.keys() if isinstance(report_data, dict) else [])}")
            logger.info(f"HTML report present: {'html_report' in report_data if isinstance(report_data, dict) else False}")
            
            # Save the successful report
            report_path = os.path.join(WEEKLY_REPORTS_DIR, report_filename)
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            logger.info(f"Saved weekly report to {report_path}")
            
            # If the report is missing the html_report field, regenerate it
            if isinstance(report_data, dict) and 'html_report' not in report_data:
                logger.warning("HTML report missing from generated report, adding it now")
                # Generate HTML report with embedded charts
                if 'executive_summary' in report_data and isinstance(report_data['executive_summary'], dict):
                    exec_summary = report_data['executive_summary']
                    total_time = exec_summary.get('total_time', 0)
                    time_by_group = exec_summary.get('time_by_group', {})
                    time_by_category = exec_summary.get('time_by_category', {})
                    daily_breakdown = exec_summary.get('daily_breakdown', {})
                    visualizations = report_data.get('visualizations', {})
                    
                    # Generate the HTML report
                    html_report = generate_html_report(start_date, end_date, total_time, time_by_group, 
                                                     time_by_category, daily_breakdown, visualizations, logs_data)
                    report_data['html_report'] = html_report
                    
                    # Save the updated report
                    with open(report_path, 'w') as f:
                        json.dump(report_data, f, indent=2)
                    logger.info("Updated report with HTML content")
            
            return report_data
        except Exception as e:
            logger.error(f"Error in weekly report generation: {e}")
            logger.warning("Falling back to basic weekly report structure")
            
            # Create a fallback basic report without requiring LLM
            total_time = sum(log.duration_minutes for log in logs)
            
            # Calculate time by group and category
            time_by_group = {}
            time_by_category = {}
            daily_breakdown = {}
            
            # Process logs to get time breakdowns
            for log in logs:
                # Group breakdown
                group = log.group
                if group not in time_by_group:
                    time_by_group[group] = 0
                time_by_group[group] += log.duration_minutes
                
                # Category breakdown
                category = log.category or "uncategorized"
                if category not in time_by_category:
                    time_by_category[category] = 0
                time_by_category[category] += log.duration_minutes
                
                # Daily breakdown
                day_str = log.timestamp.strftime("%Y-%m-%d")
                if day_str not in daily_breakdown:
                    daily_breakdown[day_str] = DailyTimeBreakdown(
                        total_time=0,
                        time_by_group={},
                        time_by_category={}
                    )
                
                daily_breakdown[day_str].total_time += log.duration_minutes
                
                if group not in daily_breakdown[day_str].time_by_group:
                    daily_breakdown[day_str].time_by_group[group] = 0
                daily_breakdown[day_str].time_by_group[group] += log.duration_minutes
                
                if category not in daily_breakdown[day_str].time_by_category:
                    daily_breakdown[day_str].time_by_category[category] = 0
                daily_breakdown[day_str].time_by_category[category] += log.duration_minutes
            
            # Create visualizations dictionary
            # Note: We don't need to explicitly create visualizations here
            # The generate_html_report function will create default visualizations
            visualizations = {}
            
            # Generate HTML report with embedded charts
            html_report = generate_html_report(start_date, end_date, total_time, time_by_group, 
                                             time_by_category, daily_breakdown, visualizations, logs_data)
            
            # Create the basic report with HTML only
            basic_report = WeeklyReport(
                html_report=html_report
            )
            
            # Save the fallback report
            report_path = os.path.join(WEEKLY_REPORTS_DIR, report_filename)
            with open(report_path, 'w') as f:
                json.dump(basic_report.model_dump(), f, indent=2)
            logger.info(f"Saved fallback weekly report to {report_path}")
            
            return basic_report.model_dump()
        
    except Exception as e:
        error_stack = traceback.format_exc()
        logger.error(f"Error in get_weekly_report: {str(e)}\n{error_stack}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if 'db' in locals():
            logger.info("Closing database connection")
            db.close()

@router.get("/debug-reports")
async def debug_reports():
    """Debug endpoint to check reports directory setup."""
    try:
        return {
            "reports_dir": REPORTS_DIR,
            "exists": os.path.exists(REPORTS_DIR),
            "absolute_path": os.path.abspath(REPORTS_DIR),
            "files": os.listdir(REPORTS_DIR),
            "working_dir": os.getcwd()
        }
    except Exception as e:
        return {"error": str(e)}
    
@router.get("/debug-activities")
async def debug_activities(date: str = Query(...)):
    """Debug endpoint to check activities in database for a specific date."""
    try:
        # Parse date string to date object
        year, month, day = map(int, date.split('-'))
        report_date = date(year, month, day)
        start_date = datetime.combine(report_date, time.min)
        end_date = datetime.combine(report_date + timedelta(days=1), time.min)
        
        db = SessionLocal()
        try:
            activities = db.query(ActivityLog).filter(
                ActivityLog.timestamp >= start_date,
                ActivityLog.timestamp < end_date
            ).all()
            
            return {
                "date": date,
                "activities": [
                    {
                        "id": activity.id,
                        "group": activity.group,
                        "timestamp": activity.timestamp.isoformat(),
                        "duration_minutes": activity.duration_minutes,
                        "description": activity.description
                    }
                    for activity in activities
                ]
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in debug_activities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/debug-llm")
async def debug_llm():
    """Debug endpoint to test LLM connectivity."""
    try:
        db = SessionLocal()
        try:
            settings = db.query(Settings).first()
            if not settings:
                raise ValueError("LLM settings not configured")

            test_prompt = "Generate a short test response to verify connectivity."
            response = await call_llm_api(test_prompt)
            return {
                "status": "success",
                "response": response,
                "provider_info": {
                    "type": "lmstudio",
                    "endpoint": settings.lmstudioEndpoint
                }
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/export-csv/{report_type}")
async def export_report_as_csv(report_type: str, date: str = None):
    """Export a report as CSV.
    
    Args:
        report_type: Type of report (daily, weekly, monthly, quarterly, annual)
        date: Date string in YYYY-MM-DD format for daily reports, or period identifier for others
    
    Returns:
        CSV file as a downloadable response
    """
    valid_types = ["daily", "weekly", "monthly", "quarterly", "annual"]
    if report_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid report type. Must be one of: {', '.join(valid_types)}")
    
    try:
        # Determine report directory and filename based on type
        if report_type == "daily":
            if not date:
                # Default to yesterday if no date provided
                current_date = date.today()
                yesterday = current_date - timedelta(days=1)
                date = yesterday.strftime("%Y-%m-%d")
            report_dir = REPORTS_DIR
            
            # Check both possible filename formats
            possible_filenames = [f"daily_report_{date}.json", f"{date}_report.json"]
            report_file = None
            
            # Log available files in the directory for debugging
            logger.info(f"Looking for report files in: {report_dir}")
            available_files = os.listdir(report_dir)
            logger.info(f"Available files: {available_files}")
            
            # Try each possible filename
            for filename in possible_filenames:
                full_path = os.path.join(report_dir, filename)
                logger.info(f"Checking if file exists: {full_path}")
                if os.path.exists(full_path):
                    report_file = filename
                    logger.info(f"Found report file: {full_path}")
                    break
            
            if not report_file:
                raise HTTPException(status_code=404, detail=f"No daily report found for date: {date}")
                
        elif report_type == "weekly":
            report_dir = WEEKLY_REPORTS_DIR
            # Handle weekly report filename logic
            if not date:
                # Find most recent weekly report
                files = [f for f in os.listdir(report_dir) if f.endswith('.json')]
                if not files:
                    raise HTTPException(status_code=404, detail=f"No {report_type} reports found")
                report_file = sorted(files)[-1]  # Get most recent
            else:
                # Try both possible filename formats
                possible_filenames = [f"weekly_report_{date}.json", f"{date}_weekly_report.json"]
                report_file = None
                for filename in possible_filenames:
                    if os.path.exists(os.path.join(report_dir, filename)):
                        report_file = filename
                        break
                if not report_file:
                    raise HTTPException(status_code=404, detail=f"No weekly report found for date: {date}")
        elif report_type == "monthly":
            report_dir = MONTHLY_REPORTS_DIR
            # Handle monthly report filename logic
            if not date:
                files = [f for f in os.listdir(report_dir) if f.endswith('.json')]
                if not files:
                    raise HTTPException(status_code=404, detail=f"No {report_type} reports found")
                report_file = sorted(files)[-1]  # Get most recent
            else:
                # Try both possible filename formats
                possible_filenames = [f"monthly_report_{date}.json", f"{date}_monthly_report.json"]
                report_file = None
                for filename in possible_filenames:
                    if os.path.exists(os.path.join(report_dir, filename)):
                        report_file = filename
                        break
                if not report_file:
                    raise HTTPException(status_code=404, detail=f"No monthly report found for date: {date}")
        elif report_type == "quarterly":
            report_dir = QUARTERLY_REPORTS_DIR
            # Handle quarterly report filename logic
            if not date:
                files = [f for f in os.listdir(report_dir) if f.endswith('.json')]
                if not files:
                    raise HTTPException(status_code=404, detail=f"No {report_type} reports found")
                report_file = sorted(files)[-1]  # Get most recent
            else:
                # Try both possible filename formats
                possible_filenames = [f"quarterly_report_{date}.json", f"{date}_quarterly_report.json"]
                report_file = None
                for filename in possible_filenames:
                    if os.path.exists(os.path.join(report_dir, filename)):
                        report_file = filename
                        break
                if not report_file:
                    raise HTTPException(status_code=404, detail=f"No quarterly report found for date: {date}")
        elif report_type == "annual":
            report_dir = ANNUAL_REPORTS_DIR
            # Handle annual report filename logic
            if not date:
                files = [f for f in os.listdir(report_dir) if f.endswith('.json')]
                if not files:
                    raise HTTPException(status_code=404, detail=f"No {report_type} reports found")
                report_file = sorted(files)[-1]  # Get most recent
            else:
                # Try both possible filename formats
                possible_filenames = [f"annual_report_{date}.json", f"{date}_annual_report.json"]
                report_file = None
                for filename in possible_filenames:
                    if os.path.exists(os.path.join(report_dir, filename)):
                        report_file = filename
                        break
                if not report_file:
                    raise HTTPException(status_code=404, detail=f"No annual report found for date: {date}")
        
        # Full path to the report file
        json_path = os.path.join(report_dir, report_file)
        logger.info(f"Using JSON report file: {json_path}")
        
        # Generate CSV filename
        csv_filename = Path(report_file).stem + ".csv"
        csv_path = os.path.join(report_dir, csv_filename)
        logger.info(f"CSV output path: {csv_path}")
        
        # Convert JSON to CSV
        converter = JSON2CSV()
        try:
            logger.info(f"Converting {json_path} to CSV format")
            converter.convert_file(json_path, csv_path)
            logger.info(f"Conversion successful, CSV file created at: {csv_path}")
            
            # Read the CSV file
            with open(csv_path, "r") as f:
                csv_content = f.read()
            
            # Return CSV as downloadable file
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename={csv_filename}"
                }
            )
            
        except Exception as e:
            logger.error(f"Error converting to CSV: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error converting to CSV: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting report as CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
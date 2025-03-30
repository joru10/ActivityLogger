import os
import json
import logging
import yaml
import random
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

# Import report utilities
from report_utils import ensure_html_report

# Import the weekly report fix
from weekly_report_fix import generate_weekly_report_html

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
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__))))
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

# Map report types to their directories
REPORT_DIRS = {
    'daily': REPORTS_DIR,
    'weekly': WEEKLY_REPORTS_DIR,
    'monthly': MONTHLY_REPORTS_DIR,
    'quarterly': QUARTERLY_REPORTS_DIR,
    'annual': ANNUAL_REPORTS_DIR
}

# Create all report directories
for directory in [REPORTS_DIR, WEEKLY_REPORTS_DIR, MONTHLY_REPORTS_DIR, 
                  QUARTERLY_REPORTS_DIR, ANNUAL_REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Report directory set to: {os.path.abspath(directory)}")

router = APIRouter()

@router.get("/list-reports/{report_type}")
async def list_reports(report_type: str):
    """List all available reports of a specific type.
    
    Args:
        report_type: Type of reports to list (daily, weekly, monthly, quarterly, annual)
        
    Returns:
        List of available reports with metadata
    """
    # Validate report type
    if report_type not in REPORT_DIRS:
        raise HTTPException(status_code=400, detail=f"Invalid report type: {report_type}. Valid types are: daily, weekly, monthly, quarterly, annual")
    
    # Get the directory for this report type
    report_dir = REPORT_DIRS[report_type]
    
    # Create the directory if it doesn't exist
    if not os.path.exists(report_dir):
        os.makedirs(report_dir, exist_ok=True)
        logger.info(f"Created {report_type} reports directory at {report_dir}")
        return {"reports": []}
    
    # List all files in the directory
    try:
        reports = []
        for filename in os.listdir(report_dir):
            file_path = os.path.join(report_dir, filename)
            if os.path.isfile(file_path):
                # Get file metadata
                file_stats = os.stat(file_path)
                creation_time = datetime.fromtimestamp(file_stats.st_ctime)
                modified_time = datetime.fromtimestamp(file_stats.st_mtime)
                file_size = file_stats.st_size
                
                # Parse date range from filename if possible
                date_range = None
                if '_to_' in filename:
                    parts = filename.split('_')
                    for i, part in enumerate(parts):
                        if part == 'to' and i > 0 and i < len(parts) - 1:
                            try:
                                start_date = parts[i-1]
                                end_date = parts[i+1].split('.')[0]  # Remove file extension
                                date_range = f"{start_date} to {end_date}"
                            except Exception as e:
                                logger.error(f"Error parsing date range from filename {filename}: {e}")
                
                # Add report info to the list
                reports.append({
                    "filename": filename,
                    "path": file_path,
                    "size": file_size,
                    "created": creation_time.isoformat(),
                    "modified": modified_time.isoformat(),
                    "date_range": date_range,
                    "type": report_type
                })
        
        # Sort reports by modification time (newest first)
        reports.sort(key=lambda x: x["modified"], reverse=True)
        return {"reports": reports}
    except Exception as e:
        logger.error(f"Error listing {report_type} reports: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing reports: {str(e)}")

@router.get("/list-reports")
async def list_all_reports():
    """List all available reports of all types.
    
    Returns:
        Dictionary of report types with their available reports
    """
    all_reports = {}
    
    for report_type in REPORT_DIRS:
        try:
            # Get reports for this type
            reports_result = await list_reports(report_type)
            all_reports[report_type] = reports_result["reports"]
        except Exception as e:
            logger.error(f"Error listing {report_type} reports: {e}")
            all_reports[report_type] = []
    
    return all_reports

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

# Import the LLM service functions with explicit imports
from llm_service import call_llm_api, extract_json_from_response, fix_common_json_errors

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
        
        # First check the daily reports directory
        daily_dir = os.path.join(REPORTS_DIR, "daily")
        report_filename = os.path.join(daily_dir, f"{report_date.strftime('%Y-%m-%d')}_report.json")
        
        # If not found, check the legacy location
        if not os.path.exists(report_filename):
            report_filename = os.path.join(REPORTS_DIR, f"{report_date.strftime('%Y-%m-%d')}_report.json")
        
        logger.info(f"Looking for report file: {report_filename}")
        
        if os.path.exists(report_filename):
            with open(report_filename, "r", encoding="utf-8") as f:
                report_data = json.load(f)
                
                # Simple and direct approach - always return in consistent format
                if "report" in report_data:
                    # Already has report wrapper
                    return report_data
                else:
                    # Wrap in report field
                    return {"report": report_data}
        else:
            # If report doesn't exist, generate a basic one
            logger.warning(f"Report not found: {report_filename}")
            empty_report = {
                "executive_summary": {
                    "total_time": 0,
                    "time_by_group": {},
                    "progress_report": "No activities recorded for this date."
                },
                "details": [],
                "markdown_report": "# Daily Report\n\nNo activities recorded for this date."
            }
            return {"report": empty_report}
            
    except Exception as e:
        logger.error(f"Error in get_daily_report: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# New function to generate weekly report
async def generate_weekly_report(start_date: date, end_date: date, logs_data: list[dict], force_refresh: bool = False):
    """Generates a weekly report for a given period with detailed visualizations."""
    profile_prompt = load_report_profile('ActivityReports_Weekly')
    logger.info(f"Generating weekly report from {start_date} to {end_date} with {len(logs_data)} logs")
    
    # Handle empty logs case
    if not logs_data:
        logger.warning("No activities found for this period")
        
        # Create empty daily breakdown for each day of the week
        daily_breakdown = {}
        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime("%Y-%m-%d")
            daily_breakdown[day_str] = DailyTimeBreakdown(
                total_time=0,
                time_by_group={},
                time_by_category={}
            )
            current_date += timedelta(days=1)
            
        empty_report = WeeklyReport(
            executive_summary=WeeklyReportExecutiveSummary(
                total_time=0,
                time_by_group={},
                daily_breakdown=daily_breakdown,
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
        
        # Initialize daily breakdown for each day of the week
        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime("%Y-%m-%d")
            daily_breakdown[day_str] = DailyTimeBreakdown(
                total_time=0,
                time_by_group={},
                time_by_category={}
            )
            time_by_day[day_str] = 0
            current_date += timedelta(days=1)
        
        # Process each log entry
        for log in logs_data:
            # Extract data
            group = log.get("group", "Other")
            category = log.get("category", "Other")
            duration = log["duration_minutes"]
            timestamp = log["timestamp"]
            day = timestamp.split()[0]  # Extract YYYY-MM-DD part
            
            # Ensure the day is within our date range
            if day in daily_breakdown:
                # Aggregate by group
                time_by_group[group] = time_by_group.get(group, 0) + duration
                
                # Aggregate by category
                time_by_category[category] = time_by_category.get(category, 0) + duration
                
                # Aggregate by day
                time_by_day[day] = time_by_day.get(day, 0) + duration
                
                # Update daily breakdown
                daily_breakdown[day].total_time += duration
                daily_breakdown[day].time_by_group[group] = daily_breakdown[day].time_by_group.get(group, 0) + duration
                daily_breakdown[day].time_by_category[category] = daily_breakdown[day].time_by_category.get(category, 0) + duration
            else:
                logger.warning(f"Log entry with date {day} is outside the report range {start_date} to {end_date}")
        
        # Ensure all days in the week are included in the report
        for day_str in daily_breakdown.keys():
            # Make sure this day appears in time_by_day even if it has no activities
            if day_str not in time_by_day:
                time_by_day[day_str] = 0
        
        # Create visualization data
        # Sort the days to ensure they're in chronological order
        sorted_days = sorted(daily_breakdown.keys())
        
        # Format days for better display (e.g., "Mon, Mar 3")
        formatted_days = []
        for day_str in sorted_days:
            try:
                day_date = date.fromisoformat(day_str)
                formatted_days.append(day_date.strftime("%a, %b %d"))
            except ValueError:
                formatted_days.append(day_str)
        
        # Get settings to understand the category-group relationship using the SessionLocal
        group_to_category = {}
        try:
            # Use the existing SessionLocal for database access
            with SessionLocal() as db:
                settings = db.query(Settings).first()
                if settings:
                    categories_config = settings.get_categories() or []
                    logger.info(f"Retrieved {len(categories_config)} categories from settings")
                    
                    # Create a mapping of groups to their categories with exact matches
                    for cat_config in categories_config:
                        cat_name = cat_config.get('name', '')
                        for group_name in cat_config.get('groups', []):
                            # Store both the original case and lowercase version for better matching
                            group_to_category[group_name] = cat_name
                            # Also store lowercase for case-insensitive matching
                            group_to_category[group_name.lower()] = cat_name
                else:
                    logger.error("No settings found in database")
        except Exception as e:
            logger.error(f"Error fetching categories from database: {e}")
            logger.error(traceback.format_exc())
        
        # Organize groups by category with improved matching
        groups_by_category = {}
        
        # Log the group_to_category mapping for debugging
        logger.info(f"Group to category mapping: {json.dumps(group_to_category)}")
        logger.info(f"Groups in time_by_group: {list(time_by_group.keys())}")
        
        # Enhanced function to find the best category match for a group
        def find_category_for_group(group_name):
            # Skip empty group names
            if not group_name or group_name.strip() == "":
                logger.warning(f"Empty group name encountered, assigning to 'Other'")
                return 'Other'
                
            # Direct match (case-sensitive)
            if group_name in group_to_category:
                logger.debug(f"Direct match found for group '{group_name}'")
                return group_to_category[group_name]
            
            # Case-insensitive match
            group_lower = group_name.lower()
            if group_lower in group_to_category:
                logger.debug(f"Case-insensitive match found for group '{group_name}'")
                return group_to_category[group_lower]
            
            # Try to find the best match by checking if the group name contains
            # or is contained in any of the configured groups
            best_match = None
            best_match_score = 0
            
            for configured_group, category in group_to_category.items():
                # Skip lowercase duplicates we added earlier
                if configured_group.lower() != configured_group and configured_group.lower() in group_to_category:
                    continue
                    
                # Calculate match score based on string similarity
                # Simple implementation: length of common substring / max length
                if group_lower in configured_group.lower():
                    score = len(group_lower) / len(configured_group.lower())
                    if score > best_match_score:
                        best_match_score = score
                        best_match = category
                elif configured_group.lower() in group_lower:
                    score = len(configured_group.lower()) / len(group_lower)
                    if score > best_match_score:
                        best_match_score = score
                        best_match = category
            
            # If we found a reasonable match (score > 0.5)
            if best_match and best_match_score > 0.5:
                logger.info(f"Partial match found for group '{group_name}' -> '{best_match}' with score {best_match_score}")
                return best_match
            
            # If no match found, return 'Other'
            logger.warning(f"No category match found for group '{group_name}', assigning to 'Other'")
            return 'Other'
        
        # Process each group
        for group, time in time_by_group.items():
            category = find_category_for_group(group)
            logger.info(f"Assigned group '{group}' to category '{category}'")
            
            if category not in groups_by_category:
                groups_by_category[category] = []
            groups_by_category[category].append({'name': group, 'time': time})
        
        # Generate colors for categories
        import colorsys
        def get_distinct_colors(n):
            colors = []
            for i in range(n):
                hue = i / n
                saturation = 0.7
                value = 0.9
                rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                rgba = f"rgba({int(rgb[0] * 255)}, {int(rgb[1] * 255)}, {int(rgb[2] * 255)}, 0.7)"
                colors.append(rgba)
            return colors
        
        # Create base visualizations
        visualizations = {
            "daily_activity": ChartData(
                chart_type="bar",
                labels=formatted_days,
                datasets=[{
                    "label": "Minutes",
                    "data": [time_by_day.get(day, 0) for day in sorted_days],
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
        
        # ALWAYS add the category-groups stacked bar chart visualization
        logger.info("Ensuring the stacked bar chart visualization is included in the report")
        
        # Define a single color generation function for consistency
        def get_colors(n):
            """Generate a list of distinct colors."""
            base_colors = [
                "rgba(255, 99, 132, 0.7)",   # Red
                "rgba(54, 162, 235, 0.7)",  # Blue
                "rgba(255, 206, 86, 0.7)",  # Yellow
                "rgba(75, 192, 192, 0.7)",  # Teal
                "rgba(153, 102, 255, 0.7)", # Purple
                "rgba(255, 159, 64, 0.7)",  # Orange
                "rgba(46, 204, 113, 0.7)",  # Green
                "rgba(142, 68, 173, 0.7)",  # Violet
                "rgba(241, 196, 15, 0.7)",  # Amber
                "rgba(231, 76, 60, 0.7)",   # Crimson
            ]
            # Ensure we have enough colors
            while len(base_colors) < n:
                base_colors.extend(base_colors)
            return base_colors[:n]
        
        # Step 1: Get the category-to-group mapping from settings
        from models import Settings, SessionLocal
        
        db = SessionLocal()
        try:
            settings = db.query(Settings).first()
            if settings:
                category_groups_mapping = {}
                categories_data = settings.get_categories()
                
                # Create a mapping of group -> category
                group_to_category_map = {}
                for cat_data in categories_data:
                    cat_name = cat_data.get('name')
                    groups = cat_data.get('groups', [])
                    for group in groups:
                        group_to_category_map[group] = cat_name
                
                logger.info(f"Loaded group-to-category mapping: {group_to_category_map}")
            else:
                logger.warning("No settings found, using default categories")
                group_to_category_map = {}
        except Exception as e:
            logger.error(f"Error loading category-group mapping: {e}")
            group_to_category_map = {}
        finally:
            db.close()
            
        # Define categories (either from data or defaults)
        if not time_by_category or len(time_by_category) == 0:
            logger.info("No categories found, creating default categories")
            categories = ['Work', 'Personal', 'Other']
            time_by_category = {cat: 0 for cat in categories}
        else:
            # Get categories and sort them by total time (descending)
            categories = sorted(time_by_category.keys(), key=lambda x: time_by_category[x], reverse=True)
        
        # Step 2: Generate colors for categories
        category_colors = get_colors(len(categories))
        category_color_map = {cat: category_colors[i] for i, cat in enumerate(categories)}
        
        # Step 3: Reorganize groups by category based on the mapping
        reorganized_groups_by_category = {cat: [] for cat in categories}
        
        # For each group in time_by_group
        for group_name, group_time in time_by_group.items():
            # Skip groups with zero time
            if group_time <= 0:
                continue
                
            # Find which category this group belongs to based on the mapping
            if group_name in group_to_category_map:
                category = group_to_category_map[group_name]
            else:
                # If no mapping exists, use the category from the activity log
                # or default to "Other"
                category = "Other"
                
                # If the group's category isn't in our list, add it
                if category not in reorganized_groups_by_category:
                    reorganized_groups_by_category[category] = []
                    if category not in categories:
                        categories.append(category)
                        time_by_category[category] = 0
            
            # Add the group to its proper category
            reorganized_groups_by_category[category].append({
                'name': group_name,
                'time': group_time
            })
            
            # Ensure the category's total time includes this group
            if category in time_by_category:
                # Just verify that the category's total time is at least as much as this group
                # (it should typically be correct from the original data aggregation)
                if time_by_category[category] < group_time:
                    time_by_category[category] = group_time
        
        # Replace the original groups_by_category with our properly organized version
        groups_by_category = reorganized_groups_by_category
        
        # Ensure each category has at least one group
        for category in categories:
            if category not in groups_by_category or not groups_by_category[category]:
                # If no groups for this category, create a default group with the category name
                category_time = time_by_category.get(category, 0)
                groups_by_category[category] = [{'name': category, 'time': category_time}]
                logger.info(f"Created default group for category {category} with time {category_time}")
        
        # Step 4: Create category datasets - one bar per category
        category_dataset = [{
            "label": "Time (minutes)",
            "data": [time_by_category.get(cat, 0) for cat in categories],
            "backgroundColor": [category_color_map[cat] for cat in categories],
            "borderColor": [c.replace('0.7', '1') for c in [category_color_map[cat] for cat in categories]],
            "borderWidth": 1
        }]
        
        # Add the simple category distribution chart
        visualizations["category_distribution"] = ChartData(
            chart_type="bar",
            title="Time by Category",
            description="Total time spent on each category",
            labels=categories,
            datasets=category_dataset
        )
        
        # Step 5: Create stacked bar chart datasets for groups
        group_datasets = []
        
        # For each category, add datasets for its groups
        for cat_idx, category in enumerate(categories):
            # Get groups for this category
            category_groups = groups_by_category.get(category, [])
            
            # Skip if no groups or zero time
            if not category_groups or time_by_category.get(category, 0) == 0:
                continue
            
            # Sort groups by time (descending) for better visualization
            category_groups.sort(key=lambda x: x['time'], reverse=True)
            
            # Get base color for this category
            base_color = category_color_map[category]
            base_rgb = base_color.replace('rgba(', '').replace(')', '').split(',')[:3]
            
            # Add one dataset per group, always stacked by category
            for group_idx, group_info in enumerate(category_groups):
                group_name = group_info['name']
                group_time = group_info['time']
                
                # Skip groups with zero time
                if group_time == 0:
                    continue
                
                # Create a slightly different shade of the category color for this group
                opacity = 0.8 - (group_idx * 0.1) if group_idx < 5 else 0.3
                group_color = f"rgba({','.join(base_rgb)},{opacity})"
                
                # Create data array with zeros for all categories except this one
                data = [0] * len(categories)
                data[cat_idx] = group_time  # Only put time in this category's position
                
                group_datasets.append({
                    "label": f"{category}: {group_name}",
                    "data": data,
                    "backgroundColor": group_color,
                    "borderColor": group_color.replace(str(opacity), '1'),
                    "borderWidth": 1,
                    "stack": category  # Stack by category
                })
        
        # If we have group datasets, add them as a visualization
        if group_datasets:
            visualizations["group_breakdown"] = ChartData(
                chart_type="bar",
                title="Groups by Category Breakdown",
                description="Time spent on each group within its category",
                labels=categories,
                datasets=group_datasets
            )
        else:
            # If no group datasets, just duplicate the category chart
            visualizations["group_breakdown"] = visualizations["category_distribution"]
        
        # Log visualization status
        logger.info(f"Added visualizations with keys: {list(visualizations.keys())}")
        logger.info(f"Created {len(group_datasets)} group datasets across {len(categories)} categories")
        
        # Log visualizations before generating HTML report
        logger.info(f"Visualizations before generating HTML report: {list(visualizations.keys())}")
        for viz_key, viz_data in visualizations.items():
            logger.info(f"Visualization '{viz_key}': {viz_data.chart_type} chart with {len(viz_data.datasets)} datasets")
            
        # Generate HTML report with embedded charts using the imported function
        html_report = generate_html_report(start_date, end_date, total_time, time_by_group, time_by_category, daily_breakdown, visualizations, logs_data)
        
        # Prepare data for LLM
        # Limit the amount of log data to prevent token limit issues
        max_logs = 50  # Limit to a reasonable number of logs
        if len(logs_data) > max_logs:
            logger.warning(f"Limiting logs for LLM prompt from {len(logs_data)} to {max_logs}")
            # Sort logs by timestamp (newest first) and take the first max_logs
            sorted_logs = sorted(logs_data, key=lambda x: x.get('timestamp', ''), reverse=True)
            limited_logs = sorted_logs[:max_logs]
            logs_json = json.dumps(limited_logs, indent=2)
            logger.info(f"Using {len(limited_logs)} most recent logs for LLM prompt")
        else:
            logs_json = json.dumps(logs_data, indent=2)
        
        # Ensure all days in the week are included in the daily breakdown for the LLM prompt
        all_days_breakdown = {}
        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime("%Y-%m-%d")
            all_days_breakdown[day_str] = daily_breakdown.get(day_str, DailyTimeBreakdown(
                total_time=0,
                time_by_group={},
                time_by_category={}
            )).total_time
            current_date += timedelta(days=1)
        
        # Create a simplified prompt with essential information only
        simplified_prompt = f"""Generate a weekly activity report in JSON format for the period {start_date} to {end_date}.

Total Time: {total_time} minutes
Time by Group: {json.dumps(time_by_group, indent=2)}
Time by Category: {json.dumps(time_by_category, indent=2)}
Daily Breakdown: {json.dumps(all_days_breakdown, indent=2)}

Return ONLY valid JSON with the following structure:
{{
  "executive_summary": {{
    "total_time": <total_time>,
    "time_by_group": <time_by_group_dict>,
    "time_by_category": <time_by_category_dict>,
    "daily_breakdown": <daily_breakdown_dict>,
    "progress_report": <summary_text>,
    "key_insights": [<insight1>, <insight2>, ...],
    "recommendations": [<recommendation1>, <recommendation2>, ...]
  }},
  "details": [<activity_logs>],
  "markdown_report": <markdown_formatted_report>
}}

DO NOT include any reasoning, thinking, or explanation tags in your response."""
        
        logger.info(f"Calling LLM API for weekly report with simplified prompt...")
        try:
            # Use the improved call_llm_api with retry logic
            llm_response = await call_llm_api(simplified_prompt, max_retries=2)
            logger.info("LLM response received successfully")
        except Exception as e:
            logger.error(f"Error from LLM API: {str(e)}")
            logger.warning("Falling back to basic report structure due to LLM error")
            # Skip to the fallback report generation
            raise ValueError(f"LLM API error: {str(e)}")
        
        # Check if the response is a string containing JSON markers
        if isinstance(llm_response, str):
            try:
                # Use the extract_json_from_response helper
                report_data = extract_json_from_response(llm_response)
                if isinstance(report_data, dict):
                    llm_response = report_data
                    logger.info("Successfully extracted JSON from string response")
                else:
                    logger.error(f"Extracted data is not a dictionary: {type(report_data)}")
                    raise ValueError("Invalid response format: not a dictionary")
            except Exception as e:
                logger.error(f"Error extracting JSON from LLM response: {str(e)}")
                # Re-raise to trigger the fallback report
                raise ValueError(f"Failed to extract valid JSON: {str(e)}")
        
        if isinstance(llm_response, dict):
            try:
                # Check for required fields before attempting validation
                required_fields = ['executive_summary', 'details', 'markdown_report']
                missing_fields = [field for field in required_fields if field not in llm_response]
                
                if missing_fields:
                    logger.error(f"LLM response missing required fields: {missing_fields}")
                    # Add missing fields with default values
                    if 'executive_summary' not in llm_response:
                        llm_response['executive_summary'] = {
                            'total_time': total_time,
                            'time_by_group': time_by_group,
                            'time_by_category': time_by_category,
                            'daily_breakdown': {k: v.model_dump() for k, v in daily_breakdown.items()},
                            'progress_report': f"Weekly report for {start_date} to {end_date}"
                        }
                    if 'details' not in llm_response:
                        llm_response['details'] = logs_data
                    if 'markdown_report' not in llm_response:
                        llm_response['markdown_report'] = f"# Weekly Report\n\n**Period:** {start_date} to {end_date}\n\n**Total Time:** {total_time} minutes"
                
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
                # Don't raise, fall through to the fallback report
                logger.warning("Using fallback report due to validation error")
                raise ValueError(f"Invalid LLM response structure: {str(e)}")
        
        logger.error("Invalid LLM response structure for weekly report")
        raise ValueError("Invalid LLM response structure")
    except Exception as e:
        logger.error(f"Error generating weekly report: {str(e)}")
        logger.warning("Falling back to basic weekly report structure")
        # Create daily breakdown for all days in the week
        daily_breakdown = {}
        
        # Generate a simple fallback HTML report for the error case
        error_html_report = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Weekly Activity Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }}
                h1, h2, h3 {{ color: #333; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .summary {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .chart {{ margin-bottom: 30px; background-color: #fff; padding: 15px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f8f8; }}
                tr:hover {{ background-color: #f1f1f1; }}
                .error {{ color: #e74c3c; background-color: #fdf3f2; padding: 10px; border-radius: 4px; margin-bottom: 15px; }}
            </style>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body>
            <div class="container">
                <h1>Weekly Activity Report: {start_date} to {end_date}</h1>
                
                <div class="summary">
                    <h2>Executive Summary</h2>
                    <p><strong>Total Time:</strong> {total_time} minutes</p>
                    <div class="error">
                        <p><strong>Note:</strong> Basic report generated due to an error in the detailed report generation.</p>
                        <p><strong>Error:</strong> {str(e)}</p>
                    </div>
                </div>
                
                <div class="chart">
                    <h2>Time by Group</h2>
                    <canvas id="groupChart"></canvas>
                </div>
                
                <script>
                    // Simple chart for groups
                    const groupData = {{
                        labels: {json.dumps(list(time_by_group.keys()))},
                        datasets: [{{
                            label: 'Minutes',
                            data: {json.dumps(list(time_by_group.values()))},
                            backgroundColor: [
                                'rgba(255, 99, 132, 0.7)',
                                'rgba(54, 162, 235, 0.7)',
                                'rgba(255, 206, 86, 0.7)',
                                'rgba(75, 192, 192, 0.7)',
                                'rgba(153, 102, 255, 0.7)',
                                'rgba(255, 159, 64, 0.7)'
                            ],
                            borderWidth: 1
                        }}]
                    }};
                    
                    new Chart(
                        document.getElementById('groupChart'),
                        {{
                            type: 'pie',
                            data: groupData,
                            options: {{
                                responsive: true,
                                plugins: {{
                                    legend: {{
                                        position: 'right',
                                    }},
                                    title: {{
                                        display: true,
                                        text: 'Time Distribution by Group'
                                    }}
                                }}
                            }}
                        }}
                    );
                </script>
            </div>
        </body>
        </html>
        """
        
        # Initialize daily breakdown for each day of the week
        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime("%Y-%m-%d")
            daily_breakdown[day_str] = DailyTimeBreakdown(
                total_time=0,
                time_by_group={},
                time_by_category={}
            )
            current_date += timedelta(days=1)
        
        # Fill in the data from logs
        for log in logs_data:
            day = log["timestamp"][:10]  # Get YYYY-MM-DD part
            daily_breakdown[day].total_time += log["duration_minutes"]
            group = log["group"]
            category = log.get("category", "Other")
            daily_breakdown[day].time_by_group[group] = daily_breakdown[day].time_by_group.get(group, 0) + log["duration_minutes"]
            daily_breakdown[day].time_by_category[category] = daily_breakdown[day].time_by_category.get(category, 0) + log["duration_minutes"]

        # Ensure daily breakdown is ordered chronologically
        ordered_daily_breakdown = {day: daily_breakdown[day] for day in sorted(daily_breakdown.keys())}
        
        basic_report = WeeklyReport(
            executive_summary=WeeklyReportExecutiveSummary(
                total_time=total_time,
                time_by_group=time_by_group,
                daily_breakdown=ordered_daily_breakdown,
                progress_report=f"Basic report generated from {len(logs_data)} activities."
            ),
            details=logs_data,
            markdown_report=f"# Weekly Report\n\n**Total Time:** {total_time} minutes\n\n**Time by Group:**\n" + "\n".join([f"- {k}: {v} minutes" for k, v in time_by_group.items()]),
            html_report=error_html_report
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
async def get_weekly_report(date: str, force_refresh: bool = Query(False, description="Force regeneration of the report even if it already exists")):
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
        
        # For in-progress weeks, use today as the end date if it's before Sunday
        today = date_class.today()
        week_end = start_date + timedelta(days=6)  # Sunday
        
        # Always use the full week range for report generation
        end_date = week_end
        logger.info(f"Week range: {start_date} to {end_date}")
        logger.info(f"Today's date: {today}")
        logger.info(f"Force refresh: {force_refresh}")
        
        # Create the directory for weekly reports if it doesn't exist
        if not os.path.exists(WEEKLY_REPORTS_DIR):
            os.makedirs(WEEKLY_REPORTS_DIR, exist_ok=True)
            logger.info(f"Created weekly reports directory at {WEEKLY_REPORTS_DIR}")
        
        # For in-progress weeks, always generate a fresh report to ensure all days are included
        report_filename = f"weekly_report_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.json"
        report_path = os.path.join(WEEKLY_REPORTS_DIR, report_filename)
        logger.info(f"Report will be saved to: {report_path}")
        
        # Check if the report already exists and load it unless force_refresh is true
        if os.path.exists(report_path) and not force_refresh:
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
        # If force_refresh is true and report exists, delete it to force regeneration
        elif os.path.exists(report_path) and force_refresh:
            logger.info(f"Force refresh requested. Deleting existing report to force regeneration.")
            try:
                os.remove(report_path)
                logger.info(f"Deleted existing report at {report_path}")
            except Exception as e:
                logger.error(f"Error deleting existing report: {e}")
            # Continue to generate a new report - DO NOT try to load the deleted report
        
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
            groups_by_category = {}
            
            # Generate an empty HTML report
            html_report = generate_html_report(start_date, end_date, 0, time_by_group, 
                                             time_by_category, daily_breakdown, visualizations, [])
            
            # Create a basic empty report with HTML only
            basic_report = WeeklyReport(
                html_report=error_html_report
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
            logger.info(f"Calling generate_weekly_report with data (force_refresh: {force_refresh})")
            report_data = await generate_weekly_report(start_date, end_date, logs_data, force_refresh=force_refresh)
            logger.info("Weekly report generation completed successfully")
            
            # Log the keys in the report_data to debug
            logger.info(f"Report data keys: {list(report_data.keys() if isinstance(report_data, dict) else [])}")
            logger.info(f"HTML report present: {'html_report' in report_data if isinstance(report_data, dict) else False}")
            
            # Check if html_report is empty or missing
            if isinstance(report_data, dict) and ('html_report' not in report_data or not report_data.get('html_report')):
                logger.warning("HTML report is missing or empty in the generated report")
            
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
            
            # Initialize daily breakdown for each day of the week
            current_date = start_date
            while current_date <= end_date:
                day_str = current_date.strftime("%Y-%m-%d")
                daily_breakdown[day_str] = DailyTimeBreakdown(
                    total_time=0,
                    time_by_group={},
                    time_by_category={}
                )
                current_date += timedelta(days=1)
            
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
                html_report=error_html_report
            )
            
            # Log the HTML report length
            logger.info(f"Generated weekly HTML report with length: {len(html_report) if html_report else 0}")
            
            # Ensure the HTML report is not empty
            if not html_report or len(html_report) < 100:  # If HTML is empty or too small
                logger.warning("Weekly HTML report is empty or too small, generating placeholder")
                title = f"Weekly Activity Report - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                from report_utils import generate_placeholder_html
                basic_report.html_report = generate_placeholder_html(f"weekly_report_{start_date}_to_{end_date}.json", "Weekly")
            
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
    
@router.get("/monthly-report")
async def get_monthly_report(date: str = Query(...)):
    """Get the monthly report for the month containing the specified date."""
    try:
        # Log starting debug info
        logger.info(f"Starting monthly report generation for date: {date}")
        
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
        
        # Calculate the first day of the month
        first_day = date_class(year, month, 1)
        
        # Calculate the last day of the month
        if month == 12:
            last_day = date_class(year, month, 31)
        else:
            next_month = date_class(year, month + 1, 1)
            last_day = next_month - timedelta(days=1)
        
        logger.info(f"Month range: {first_day} to {last_day}")
        
        # Create the directory for monthly reports if it doesn't exist
        if not os.path.exists(MONTHLY_REPORTS_DIR):
            os.makedirs(MONTHLY_REPORTS_DIR, exist_ok=True)
            logger.info(f"Created monthly reports directory at {MONTHLY_REPORTS_DIR}")
        
        # Check for an existing report first
        month_name = first_day.strftime('%B')
        report_filename = f"monthly_report_{year}_{month_name}.json"
        report_path = os.path.join(MONTHLY_REPORTS_DIR, report_filename)
        logger.info(f"Looking for existing report at: {report_path}")
        
        if os.path.exists(report_path):
            logger.info("Found existing report, loading it")
            try:
                with open(report_path, 'r') as f:
                    report_data = json.load(f)
                # Validate the loaded report using Pydantic
                report = MonthlyReport(**report_data)
                logger.info("Successfully loaded and validated existing report")
                return report.model_dump()
            except Exception as e:
                logger.error(f"Error loading existing report: {e}")
                # If there's an error loading the existing report, return a 404
                raise HTTPException(status_code=404, detail=f"Error loading monthly report: {str(e)}")
        else:
            # Report doesn't exist, generate a new one
            logger.info(f"No monthly report found for {month_name} {year}, generating a new one")
            
            # Get activity logs for the month
            db = SessionLocal()
            start_datetime = datetime.combine(first_day, time.min)
            end_datetime = datetime.combine(last_day, time.max)
            
            try:
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
                
                if logs_data:
                    # Generate the monthly report using the report_templates module
                    from report_templates import generate_html_report
                    
                    # Create chart data and time breakdown for the month
                    chart_data = ChartData()
                    daily_breakdown = {}
                    
                    # Process logs to create time breakdowns by day
                    for log in logs_data:
                        log_date = datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S.%f").date().strftime("%Y-%m-%d")
                        if log_date not in daily_breakdown:
                            daily_breakdown[log_date] = DailyTimeBreakdown(total_time=0, time_by_group={}, time_by_category={})
                        
                        # Update daily breakdown
                        daily_time = daily_breakdown[log_date]
                        daily_time.total_time += log["duration_minutes"]
                        
                        # Update group time
                        if log["group"] not in daily_time.time_by_group:
                            daily_time.time_by_group[log["group"]] = 0
                        daily_time.time_by_group[log["group"]] += log["duration_minutes"]
                        
                        # Update category time
                        if log["category"] not in daily_time.time_by_category:
                            daily_time.time_by_category[log["category"]] = 0
                        daily_time.time_by_category[log["category"]] += log["duration_minutes"]
                        
                        # Update chart data
                        chart_data.add_activity(log)
                    
                    # Generate the HTML report
                    title = f"Monthly Activity Report - {month_name} {year}"
                    html_report = generate_html_report(title, first_day, last_day, logs_data, chart_data, daily_breakdown)
                    
                    # Create the monthly report object
                    report = MonthlyReport(html_report=html_report)
                    
                    # Save the report
                    with open(report_path, 'w') as f:
                        json.dump(report.model_dump(), f, indent=2)
                    
                    logger.info(f"Monthly report saved to {report_path}")
                    return report.model_dump()
                else:
                    logger.warning(f"No activity logs found for {month_name} {year}")
                    raise HTTPException(status_code=404, detail=f"No activity logs found for {month_name} {year}")
            finally:
                db.close()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_monthly_report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quarterly-report")
async def get_quarterly_report(date: str = Query(...)):
    """Get the quarterly report for the quarter containing the specified date."""
    try:
        # Log starting debug info
        logger.info(f"Starting quarterly report generation for date: {date}")
        
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
        
        # Determine the quarter
        quarter = (month - 1) // 3 + 1
        
        # Calculate the first day of the quarter
        first_month = (quarter - 1) * 3 + 1
        first_day = date_class(year, first_month, 1)
        
        # Calculate the last day of the quarter
        if quarter == 4:
            last_day = date_class(year, 12, 31)
        else:
            next_quarter_first_month = quarter * 3 + 1
            next_quarter_first_day = date_class(year, next_quarter_first_month, 1)
            last_day = next_quarter_first_day - timedelta(days=1)
        
        logger.info(f"Quarter range: {first_day} to {last_day}")
        
        # Create the directory for quarterly reports if it doesn't exist
        if not os.path.exists(QUARTERLY_REPORTS_DIR):
            os.makedirs(QUARTERLY_REPORTS_DIR, exist_ok=True)
            logger.info(f"Created quarterly reports directory at {QUARTERLY_REPORTS_DIR}")
        
        # Check for an existing report first
        report_filename = f"quarterly_report_Q{quarter}_{year}.json"
        report_path = os.path.join(QUARTERLY_REPORTS_DIR, report_filename)
        logger.info(f"Looking for existing report at: {report_path}")
        
        if os.path.exists(report_path):
            logger.info("Found existing report, loading it")
            try:
                with open(report_path, 'r') as f:
                    report_data = json.load(f)
                # Validate the loaded report using Pydantic
                report = QuarterlyReport(**report_data)
                logger.info("Successfully loaded and validated existing report")
                return report.model_dump()
            except Exception as e:
                logger.error(f"Error loading existing report: {e}")
                # If there's an error loading the existing report, return a 404
                raise HTTPException(status_code=404, detail=f"Error loading quarterly report: {str(e)}")
        else:
            # Report doesn't exist, generate a new one
            logger.info(f"No quarterly report found for Q{quarter} {year}, generating a new one")
            
            # Get activity logs for the quarter
            db = SessionLocal()
            start_datetime = datetime.combine(first_day, time.min)
            end_datetime = datetime.combine(last_day, time.max)
            
            try:
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
                
                if logs_data:
                    # Generate the quarterly report using the report_templates module
                    from report_templates import generate_html_report
                    
                    # Create chart data and time breakdown for the quarter
                    chart_data = ChartData()
                    daily_breakdown = {}
                    
                    # Process logs to create time breakdowns by day
                    for log in logs_data:
                        log_date = datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S.%f").date().strftime("%Y-%m-%d")
                        if log_date not in daily_breakdown:
                            daily_breakdown[log_date] = DailyTimeBreakdown(total_time=0, time_by_group={}, time_by_category={})
                        
                        # Update daily breakdown
                        daily_time = daily_breakdown[log_date]
                        daily_time.total_time += log["duration_minutes"]
                        
                        # Update group time
                        if log["group"] not in daily_time.time_by_group:
                            daily_time.time_by_group[log["group"]] = 0
                        daily_time.time_by_group[log["group"]] += log["duration_minutes"]
                        
                        # Update category time
                        if log["category"] not in daily_time.time_by_category:
                            daily_time.time_by_category[log["category"]] = 0
                        daily_time.time_by_category[log["category"]] += log["duration_minutes"]
                        
                        # Update chart data
                        chart_data.add_activity(log)
                    
                    # Generate the HTML report
                    title = f"Quarterly Activity Report - Q{quarter} {year}"
                    html_report = generate_html_report(title, first_day, last_day, logs_data, chart_data, daily_breakdown)
                    
                    # Create the quarterly report object
                    report = QuarterlyReport(html_report=html_report)
                    
                    # Save the report
                    with open(report_path, 'w') as f:
                        json.dump(report.model_dump(), f, indent=2)
                    
                    logger.info(f"Quarterly report saved to {report_path}")
                    return report.model_dump()
                else:
                    logger.warning(f"No activity logs found for Q{quarter} {year}")
                    raise HTTPException(status_code=404, detail=f"No activity logs found for Q{quarter} {year}")
            finally:
                db.close()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_quarterly_report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/annual-report")
async def get_annual_report(date: str = Query(...)):
    """Get the annual report for the year specified in the date."""
    try:
        # Log starting debug info
        logger.info(f"Starting annual report generation for date: {date}")
        
        # Parse the date string to a date object
        try:
            year, month, day = map(int, date.split('-'))
            logger.info(f"Parsed date components: year={year}, month={month}, day={day}")
        except Exception as e:
            logger.error(f"Error parsing date: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid date format. Please use YYYY-MM-DD format. Error: {str(e)}")
        
        # Create the directory for annual reports if it doesn't exist
        if not os.path.exists(ANNUAL_REPORTS_DIR):
            os.makedirs(ANNUAL_REPORTS_DIR, exist_ok=True)
            logger.info(f"Created annual reports directory at {ANNUAL_REPORTS_DIR}")
        
        # Check for an existing report first
        report_filename = f"annual_report_{year}.json"
        report_path = os.path.join(ANNUAL_REPORTS_DIR, report_filename)
        logger.info(f"Looking for existing report at: {report_path}")
        
        if os.path.exists(report_path):
            logger.info("Found existing report, loading it")
            try:
                with open(report_path, 'r') as f:
                    report_data = json.load(f)
                # Validate the loaded report using Pydantic
                report = AnnualReport(**report_data)
                logger.info("Successfully loaded and validated existing report")
                return report.model_dump()
            except Exception as e:
                logger.error(f"Error loading existing report: {e}")
                # If there's an error loading the existing report, return a 404
                raise HTTPException(status_code=404, detail=f"Error loading annual report: {str(e)}")
        else:
            # Report doesn't exist, generate a new one
            logger.info(f"No annual report found for year {year}, generating a new one")
            
            # Calculate the first and last day of the year
            from datetime import date as date_class
            first_day = date_class(year, 1, 1)
            last_day = date_class(year, 12, 31)
            
            # Get activity logs for the year
            db = SessionLocal()
            start_datetime = datetime.combine(first_day, time.min)
            end_datetime = datetime.combine(last_day, time.max)
            
            try:
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
                
                if logs_data:
                    # Generate the annual report using the report_templates module
                    from report_templates import generate_html_report
                    
                    # Create chart data and time breakdown for the year
                    chart_data = ChartData()
                    daily_breakdown = {}
                    
                    # Process logs to create time breakdowns by day
                    for log in logs_data:
                        log_date = datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S.%f").date().strftime("%Y-%m-%d")
                        if log_date not in daily_breakdown:
                            daily_breakdown[log_date] = DailyTimeBreakdown(total_time=0, time_by_group={}, time_by_category={})
                        
                        # Update daily breakdown
                        daily_time = daily_breakdown[log_date]
                        daily_time.total_time += log["duration_minutes"]
                        
                        # Update group time
                        if log["group"] not in daily_time.time_by_group:
                            daily_time.time_by_group[log["group"]] = 0
                        daily_time.time_by_group[log["group"]] += log["duration_minutes"]
                        
                        # Update category time
                        if log["category"] not in daily_time.time_by_category:
                            daily_time.time_by_category[log["category"]] = 0
                        daily_time.time_by_category[log["category"]] += log["duration_minutes"]
                        
                        # Update chart data
                        chart_data.add_activity(log)
                    
                    # Generate the HTML report
                    title = f"Annual Activity Report - {year}"
                    html_report = generate_html_report(title, first_day, last_day, logs_data, chart_data, daily_breakdown)
                    
                    # Create the annual report object
                    report = AnnualReport(html_report=html_report)
                    
                    # Save the report
                    with open(report_path, 'w') as f:
                        json.dump(report.model_dump(), f, indent=2)
                    
                    logger.info(f"Annual report saved to {report_path}")
                    return report.model_dump()
                else:
                    logger.warning(f"No activity logs found for year {year}")
                    raise HTTPException(status_code=404, detail=f"No activity logs found for year {year}")
            finally:
                db.close()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_annual_report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
    """Debug endpoint to test LLM connectivity and validate JSON extraction."""
    logger.info("Testing LLM connectivity...")
    try:
        db = SessionLocal()
        try:
            settings = db.query(Settings).first()
            if not settings:
                logger.error("No settings found in database")
                raise ValueError("LLM settings not configured")
            
            if not settings.lmstudioEndpoint:
                logger.error("LLM Studio endpoint not configured in settings")
                raise ValueError("LLM Studio endpoint not configured")
            
            logger.info(f"Using LLM endpoint: {settings.lmstudioEndpoint}")
            logger.info(f"Using LLM model: {settings.lmstudioModel or 'default'}")

            # Test basic connectivity
            test_prompt = "Generate a short test response in JSON format with the following structure: {\"message\": \"your message\", \"timestamp\": \"current time\"}."
            
            logger.info("Sending test prompt to LLM API...")
            response = await call_llm_api(test_prompt, max_retries=2)
            logger.info("Received response from LLM API")
            
            # Test JSON extraction
            if isinstance(response, dict) and "choices" in response:
                logger.info("Testing JSON extraction from response...")
                content = response["choices"][0]["message"]["content"]
                extracted_json = extract_json_from_response(content)
                logger.info("JSON extraction successful")
                
                return {
                    "status": "success",
                    "raw_response": response,
                    "extracted_json": extracted_json,
                    "provider_info": {
                        "type": "lmstudio",
                        "endpoint": settings.lmstudioEndpoint,
                        "model": settings.lmstudioModel or "default"
                    }
                }
            else:
                # Already got a parsed response
                return {
                    "status": "success",
                    "response": response,
                    "provider_info": {
                        "type": "lmstudio",
                        "endpoint": settings.lmstudioEndpoint,
                        "model": settings.lmstudioModel or "default"
                    }
                }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"LLM debug test failed: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@router.get("/serve-file/{report_type}/{filename}")
async def serve_report_file(report_type: str, filename: str):
    """Serve a report file directly (HTML, CSV, etc).
    
    Args:
        report_type: Type of report (daily, weekly, monthly, quarterly, annual)
        filename: Name of the file to serve
    
    Returns:
        The file content with appropriate content type
    """
    valid_types = ["daily", "weekly", "monthly", "quarterly", "annual"]
    if report_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid report type. Must be one of: {', '.join(valid_types)}")
    
    try:
        # Determine the report directory based on type
        if report_type == "daily":
            report_dir = os.path.join(REPORTS_DIR, "daily")
        elif report_type == "weekly":
            report_dir = WEEKLY_REPORTS_DIR
        elif report_type == "monthly":
            report_dir = MONTHLY_REPORTS_DIR
        elif report_type == "quarterly":
            report_dir = QUARTERLY_REPORTS_DIR
        elif report_type == "annual":
            report_dir = ANNUAL_REPORTS_DIR
        
        # Construct the full path to the file
        file_path = os.path.join(report_dir, filename)
        
        # Check if the file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")
        
        # Determine the content type based on file extension
        content_type = "text/plain"
        if filename.endswith(".html"):
            content_type = "text/html"
        elif filename.endswith(".csv"):
            content_type = "text/csv"
        elif filename.endswith(".json"):
            content_type = "application/json"
        
        # Read the file content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # For JSON files, we need to ensure they're properly parsed and returned
        if content_type == "application/json":
            try:
                # Parse JSON to ensure it's valid
                json_content = json.loads(content)
                # Return as a JSON response
                return json_content
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON file {filename}: {str(e)}")
                # If parsing fails, return as plain text
                return Response(content=content, media_type="text/plain")
        
        # Return the file content with appropriate content type
        return Response(content=content, media_type=content_type)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
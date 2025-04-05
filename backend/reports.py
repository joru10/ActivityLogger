import os
import json
import logging
import yaml
import random
import re
from datetime import datetime, timedelta, date, time
from fastapi import HTTPException
from sqlalchemy import and_
from models import SessionLocal, ActivityLog, Settings, ReportCache
from config import get_categories_json
from fastapi import APIRouter, Query, HTTPException, Response
from fastapi.responses import RedirectResponse
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
    total_time: float
    time_by_group: dict[str, float]
    time_by_category: dict[str, float] = {}
    daily_breakdown: dict[str, DailyTimeBreakdown] = {}
    progress_report: str = ""
    key_insights: list[str] = []
    recommendations: list[str] = []

class WeeklyReport(BaseModel):
    executive_summary: WeeklyReportExecutiveSummary = None
    details: list = []
    markdown_report: str = ""
    html_report: str = ""  # HTML version with embedded charts
    group_to_category_mapping: dict = {}  # Mapping of groups to their categories

class MonthlyReport(BaseModel):
    html_report: str = ""  # HTML version with embedded charts

    def model_dump(self):
        """Return a dictionary representation of the model."""
        return {
            "html_report": self.html_report
        }

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
    # Log the force_refresh parameter
    logger.info(f"generate_weekly_report called with force_refresh={force_refresh}")
    """Generates a weekly report for a given period with detailed visualizations."""

    # Check if we have a cached report and force_refresh is False
    if not force_refresh:
        try:
            # Create a session
            db = SessionLocal()
            # Look for a cached report for this date range
            cached_report = db.query(ReportCache).filter(
                ReportCache.report_type == 'weekly',
                ReportCache.date == start_date.isoformat()
            ).first()

            if cached_report:
                logger.info(f"Found cached weekly report for {start_date} to {end_date}")
                # Return the cached report
                return cached_report.get_report_data()
            else:
                logger.info(f"No cached weekly report found for {start_date} to {end_date}")
        except Exception as e:
            logger.error(f"Error checking for cached report: {e}")
        finally:
            db.close()
    else:
        logger.info(f"Force refresh requested, skipping cache check")

    # Load the profile but we'll use it later in the LLM prompt construction
    _ = load_report_profile('ActivityReports_Weekly')
    logger.info(f"Generating weekly report from {start_date} to {end_date} with {len(logs_data)} logs and force_refresh={force_refresh}")

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
            # Import here to avoid circular imports
            from models import SessionLocal, Settings
            # Use the existing SessionLocal for database access
            with SessionLocal() as db:
                settings = db.query(Settings).first()
                if settings:
                    categories_config = settings.get_categories() or []
                    logger.info(f"Retrieved {len(categories_config)} categories from settings")

                    # Build group-to-category mapping
                    for category in categories_config:
                        cat_name = category.get('name', '')
                        for group in category.get('groups', []):
                            # Handle both string and dictionary formats for groups
                            if isinstance(group, dict) and 'name' in group:
                                group_name = group['name']
                            else:
                                group_name = str(group)

                            # Add to mapping
                            group_to_category[group_name] = cat_name
                            # Also add lowercase version for case-insensitive matching
                            group_to_category[group_name.lower()] = cat_name

                            logger.debug(f"Mapped group '{group_name}' to category '{cat_name}'")

                    # Ensure all groups in logs have a category
                    for log in logs_data:
                        group = log.get('group')
                        if group and group not in group_to_category:
                            group_to_category[group] = 'Other'
                            logger.warning(f"Group '{group}' not found in settings, defaulting to 'Other' category")

                        # We've already built the mapping above, no need to do it again
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

        # Helper function to normalize group names
        def normalize_group_name(name):
            """Normalize group name by removing special characters and standardizing format."""
            if not name:
                return ""
            # Convert to string
            name = str(name)
            # Remove special characters and extra spaces
            name = re.sub(r'[^\w\s]', '', name)
            # Replace multiple spaces with a single space
            name = re.sub(r'\s+', ' ', name)
            # Trim and lowercase
            return name.strip().lower()

        # Enhanced function to find the best category match for a group
        def find_category_for_group(group_name):
            # Skip empty group names
            if not group_name or group_name.strip() == "":
                logger.warning("Empty group name encountered, assigning to 'Other'")
                return 'Other'

            # First check for exact matches (case-sensitive)
            if group_name in group_to_category:
                logger.debug(f"Exact match found for group '{group_name}'")
                return group_to_category[group_name]

            # Check for normalized matches (trim whitespace, lowercase)
            normalized_group = group_name.strip().lower()
            if normalized_group in group_to_category:
                logger.debug(f"Normalized match found for group '{group_name}'")
                return group_to_category[normalized_group]

            # Try more aggressive normalization
            fully_normalized = normalize_group_name(group_name)
            if fully_normalized in group_to_category:
                logger.info(f"Fully normalized match found: '{group_name}' -> '{fully_normalized}' -> '{group_to_category[fully_normalized]}'")
                return group_to_category[fully_normalized]

            # Check for partial matches in group names
            for configured_group, category in group_to_category.items():
                # Skip lowercase duplicates we added earlier
                if configured_group.lower() != configured_group and configured_group.lower() in group_to_category:
                    continue

                # Check if group_name is a substring of configured_group or vice versa
                if normalized_group in configured_group.lower() or configured_group.lower() in normalized_group:
                    logger.info(f"Partial match found for group '{group_name}' -> '{category}'")
                    return category

                # Try matching with fully normalized strings
                configured_normalized = normalize_group_name(configured_group)
                if fully_normalized in configured_normalized or configured_normalized in fully_normalized:
                    logger.info(f"Normalized partial match: '{group_name}' -> '{configured_group}' -> '{category}'")
                    return category

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

        # Create base visualizations - convert minutes to hours
        daily_hours = [round(time_by_day.get(day, 0) / 60.0, 1) for day in sorted_days]
        logger.info(f"Daily hours: {list(zip(formatted_days, daily_hours))}")

        visualizations = {
            "daily_activity": ChartData(
                chart_type="bar",
                labels=formatted_days,
                datasets=[{
                    "label": "Hours",
                    "data": daily_hours,  # Use hours instead of minutes
                    "backgroundColor": "rgba(54, 162, 235, 0.5)"
                }],
                title="Daily Activity Distribution",
                description="Time spent on activities each day of the week"
            ),
            "group_distribution": ChartData(
                chart_type="pie",
                labels=list(time_by_group.keys()),
                datasets=[{
                    "data": [round(time / 60.0, 1) for time in time_by_group.values()],  # Convert to hours
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
                description="Breakdown of time spent on different activity groups (in hours)"
            ),
            "category_distribution": ChartData(
                chart_type="pie",
                labels=list(time_by_category.keys()),
                datasets=[{
                    "data": [round(time / 60.0, 1) for time in time_by_category.values()],  # Convert to hours
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
                description="Breakdown of time spent on different activity categories (in hours)"
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
                categories_data = settings.get_categories()

                # Helper function to normalize group names
                def normalize_group_name(name):
                    """Normalize group name by removing special characters and standardizing format."""
                    if not name:
                        return ""
                    # Convert to string
                    name = str(name)
                    # Remove special characters and extra spaces
                    name = re.sub(r'[^\w\s]', '', name)
                    # Replace multiple spaces with a single space
                    name = re.sub(r'\s+', ' ', name)
                    # Trim and lowercase
                    return name.strip().lower()

                # Create a mapping of group -> category
                group_to_category_map = {}
                normalized_group_map = {}  # Map normalized names to original names

                for cat_data in categories_data:
                    cat_name = cat_data.get('name')
                    groups = cat_data.get('groups', [])
                    for group in groups:
                        # Handle both string and dictionary formats for groups
                        if isinstance(group, dict) and 'name' in group:
                            group_name = group['name']
                        else:
                            group_name = str(group)

                        # Add to mapping
                        group_to_category_map[group_name] = cat_name
                        # Also add lowercase version for case-insensitive matching
                        group_to_category_map[group_name.lower()] = cat_name

                        # Add normalized version
                        normalized_name = normalize_group_name(group_name)
                        group_to_category_map[normalized_name] = cat_name
                        normalized_group_map[normalized_name] = group_name

                        # Log the mapping
                        logger.debug(f"Group mapping: '{group_name}' -> '{cat_name}' (normalized: '{normalized_name}')")

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
        # Convert minutes to hours
        category_dataset = [{
            "label": "Time (hours)",
            "data": [round(time_by_category.get(cat, 0) / 60.0, 1) for cat in categories],  # Convert to hours
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
                # Convert minutes to hours with 1 decimal place
                group_time_hours = round(group_time / 60.0, 1)
                data[cat_idx] = group_time_hours  # Only put time in this category's position (in hours)

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
                description="Time spent on each group within its category (in hours)",
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

        # Convert time_by_group from minutes to hours for the chart
        time_by_group_hours = {}
        for group, minutes in time_by_group.items():
            # Convert minutes to hours with 1 decimal place
            hours = round(float(minutes) / 60.0, 1)
            time_by_group_hours[group] = hours
            logger.info(f"Converted {group}: {minutes} minutes to {hours} hours")

        # Convert time_by_category from minutes to hours for the chart
        time_by_category_hours = {}
        for category, minutes in time_by_category.items():
            # Convert minutes to hours with 1 decimal place
            hours = round(float(minutes) / 60.0, 1)
            time_by_category_hours[category] = hours
            logger.info(f"Converted category {category}: {minutes} minutes to {hours} hours")

        # Log the conversion results
        logger.info(f"Original time_by_group (minutes): {time_by_group}")
        logger.info(f"Converted time_by_group (hours): {time_by_group_hours}")

        # Generate HTML report with embedded charts using the imported function
        # Use the original time_by_group (in minutes) for the report
        html_report = generate_html_report(start_date, end_date, total_time, time_by_group, time_by_category, daily_breakdown, visualizations, logs_data)

        # Prepare data for LLM
        # Limit the amount of log data to prevent token limit issues
        max_logs = 50  # Limit to a reasonable number of logs
        if len(logs_data) > max_logs:
            logger.warning(f"Limiting logs for LLM prompt from {len(logs_data)} to {max_logs}")
            # Sort logs by timestamp (newest first) and take the first max_logs
            sorted_logs = sorted(logs_data, key=lambda x: x.get('timestamp', ''), reverse=True)
            limited_logs = sorted_logs[:max_logs]
            # Just log the number of logs
            logger.info(f"Using {len(limited_logs)} most recent logs for LLM prompt")
        else:
            # Just log the number of logs, no need to store the JSON string
            logger.info(f"Using all {len(logs_data)} logs for LLM prompt")

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

        # Create a detailed prompt with category-group dependencies
        category_group_info = "\nCATEGORY/GROUP STRUCTURE (EXACT MAPPING - IMPORTANT FOR CHART GENERATION):\n"

        # Get the complete category structure from settings
        from models import SessionLocal, Settings  # Import here to avoid circular imports
        with SessionLocal() as db:
            settings = db.query(Settings).first()
            if settings:
                categories_data = settings.get_categories()
                logger.info(f"Loaded categories data: {json.dumps(categories_data, indent=2)}")

                # Format categories for better readability in the prompt
                for cat in categories_data:
                    cat_name = cat['name']
                    category_group_info += f"CATEGORY: {cat_name}\n"
                    category_group_info += f"GROUPS IN {cat_name}:\n"
                    for group in cat.get('groups', []):
                        # Handle both string and dictionary formats for groups
                        if isinstance(group, dict) and 'name' in group:
                            group_name = group['name']
                        else:
                            group_name = str(group)
                        category_group_info += f"  * {group_name} (BELONGS TO {cat_name})\n"

                        # Also add the mapping to group_to_category if not already there
                        if group_name not in group_to_category:
                            group_to_category[group_name] = cat_name
                            logger.info(f"Added missing mapping: {group_name} -> {cat_name}")
                    category_group_info += "\n"
            else:
                # Fallback to the mapping we already have
                category_group_info = "\nCATEGORY-GROUP MAPPING (EXACT):\n"
                # Group by category first
                categories_to_groups = {}
                for group, category in group_to_category_map.items():
                    # Only include the original group names (not lowercase duplicates)
                    if group.lower() != group and group.lower() in group_to_category_map:
                        continue
                    if category not in categories_to_groups:
                        categories_to_groups[category] = []
                    categories_to_groups[category].append(group)

                # Now output by category
                for category, groups in categories_to_groups.items():
                    category_group_info += f"CATEGORY: {category}\n"
                    category_group_info += f"GROUPS IN {category}:\n"
                    for group in groups:
                        category_group_info += f"  * {group} (BELONGS TO {category})\n"
                    category_group_info += "\n"

        # Create a simplified prompt with essential information including category-group dependencies
        simplified_prompt = f"""Generate a weekly activity report in JSON format for the period {start_date} to {end_date}.

Total Time: {total_time} minutes
Time by Group (in minutes): {json.dumps(time_by_group, indent=2)}
Time by Category (in minutes): {json.dumps(time_by_category, indent=2)}
Daily Breakdown (in minutes): {json.dumps(all_days_breakdown, indent=2)}

IMPORTANT: The time values above are in MINUTES. When creating the JSON response, convert these values to HOURS by dividing by 60 and include only the numeric results in your JSON. For example, if a group has 90 minutes, include 1.5 in your JSON, not '90 / 60'.

=== CATEGORY-GROUP STRUCTURE ===
This is the structure of categories and their groups. You MUST follow this structure:
{category_group_info}

=== IMPORTANT INSTRUCTIONS FOR GROUP CATEGORIZATION ===
1. For groups that EXACTLY match those listed above, use the specified category.
2. For groups that don't have an exact match, use the following approach:
   a. First, check if the group name is similar to any of the groups listed above (e.g., case differences, minor spelling variations)
   b. If similar, assign it to the same category as the similar group
   c. If no similar group is found, use your best judgment to assign it to the most appropriate category based on the group name
   d. Only use the 'Other' category as a last resort when the group cannot be reasonably assigned to any existing category

=== SPECIFIC GROUP ASSIGNMENTS ===
Based on the data provided, here are some specific group assignments you MUST follow in your response:
- "Deep Learning Specialization" belongs to "Training" category
- "DeepLearning" belongs to "Training" category
- "NLP Course" belongs to "Training" category
- "AI News" belongs to "Research" category
- "AI-News" belongs to "Research" category
- "Papers" belongs to "Research" category
- "Articles" belongs to "Research" category
- "Videos" belongs to "Research" category
- "ActivityReports" belongs to "Coding" category
- "Tools" belongs to "Coding" category
- "tools" belongs to "Coding" category
- "Colabs" belongs to "Coding" category
- "MultiAgent" belongs to "Coding" category
- "EdgeTabs" belongs to "Coding" category
- "MediaConversion" belongs to "Coding" category
- "OneNoteRAG" belongs to "Coding" category
- "Work" belongs to "Work&Finance" category
- "Unemployment" belongs to "Work&Finance" category
- "Pensions" belongs to "Work&Finance" category
- "taxes" belongs to "Work&Finance" category

IMPORTANT: In your JSON response, make sure that each group is assigned to the correct category as specified above. The time_by_group and time_by_category values should be consistent with these assignments.
3. Be consistent with your categorization - the same group should always be assigned to the same category
4. NEVER create new categories beyond those specified above

=== DAILY BREAKDOWN STRUCTURE ===
The daily_breakdown field must be a dictionary where each key is a date string (YYYY-MM-DD) and each value is an object with:
- total_time: The total time spent on that day (in hours)
- time_by_group: A dictionary mapping group names to hours spent
- time_by_category: A dictionary mapping category names to hours spent

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

=== CRITICAL VISUALIZATION INSTRUCTIONS ===
When creating the stacked bar chart visualization:
1. Each category MUST have exactly ONE bar
2. Each bar MUST be composed of segments representing ONLY the groups that belong to that category
3. For groups explicitly listed in the category-group structure or specific group assignments, use the EXACT category specified
4. For groups NOT explicitly listed, use your best judgment to assign them to the most appropriate category:
   a. First try to match with similar group names in the same category
   b. If no similar group exists, assign based on the group name's meaning
   c. Only use 'Other' category as a last resort
5. Be consistent - the same group should always be assigned to the same category
6. Make sure all groups in time_by_group are properly mapped to their categories
7. The chart must accurately represent the hierarchical relationship between categories and their groups
8. All time values in the charts should be in HOURS, not minutes. IMPORTANT: First calculate hours by dividing minutes by 60, then include only the final numeric result in the JSON.
9. Make sure to display the y-axis with hour values, not minutes.
10. DO NOT include expressions like '90 / 60' in your JSON - calculate these values first (e.g., 1.5) and then include only the numeric result.
11. CRITICAL: Follow the specific group assignments listed above. For example, "Deep Learning Specialization" MUST be in the "Training" category, "AI-News" MUST be in the "Research" category, etc.
12. CRITICAL: In the 'details' section of your response, make sure each activity log has the correct category assigned based on the group-category mappings specified above.

DO NOT include any reasoning, thinking, or explanation tags in your response."""

        logger.info("Calling LLM API for weekly report with simplified prompt...")
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

                # Fix daily_breakdown if it's not in the correct format
                if 'executive_summary' in llm_response and 'daily_breakdown' in llm_response['executive_summary']:
                    daily_bd = llm_response['executive_summary']['daily_breakdown']
                    if isinstance(daily_bd, dict):
                        # Check if any values are not dictionaries (i.e., simple numbers)
                        for day, value in list(daily_bd.items()):
                            if not isinstance(value, dict):
                                logger.warning(f"Converting simple value {value} to DailyTimeBreakdown for day {day}")
                                # Convert simple value to DailyTimeBreakdown
                                daily_bd[day] = {
                                    "total_time": float(value),
                                    "time_by_group": {},
                                    "time_by_category": {}
                                }

                # Define the correct group-to-category mappings
                correct_mappings = {
                    "Deep Learning Specialization": "Training",
                    "DeepLearning": "Training",
                    "NLP Course": "Training",
                    "AI News": "Research",
                    "AI-News": "Research",
                    "Papers": "Research",
                    "Articles": "Research",
                    "Videos": "Research",
                    "ActivityReports": "Coding",
                    "Tools": "Coding",
                    "tools": "Coding",
                    "Colabs": "Coding",
                    "MultiAgent": "Coding",
                    "EdgeTabs": "Coding",
                    "MediaConversion": "Coding",
                    "OneNoteRAG": "Coding",
                    "Work": "Work&Finance",
                    "Unemployment": "Work&Finance",
                    "Pensions": "Work&Finance",
                    "taxes": "Work&Finance"
                }

                # Fix group-to-category mappings in the details section
                if 'details' in llm_response and isinstance(llm_response['details'], list):
                    for item in llm_response['details']:
                        if isinstance(item, dict) and 'group' in item:
                            group = item['group']
                            # If this group has a specific mapping, use it
                            if group in correct_mappings:
                                item['category'] = correct_mappings[group]
                                logger.info(f"Fixed category for group '{group}' to '{correct_mappings[group]}'")

                # Fix time_by_category in executive_summary
                if 'executive_summary' in llm_response and 'time_by_group' in llm_response['executive_summary']:
                    time_by_group = llm_response['executive_summary']['time_by_group']

                    # Recalculate time_by_category based on correct mappings
                    recalculated_time_by_category = {
                        'Training': 0,
                        'Research': 0,
                        'Coding': 0,
                        'Work&Finance': 0,
                        'Other': 0
                    }

                    # Create a mapping of all groups to their categories
                    group_to_category = {}

                    for group, time in time_by_group.items():
                        category = None
                        # Check if this group has a specific mapping
                        if group in correct_mappings:
                            category = correct_mappings[group]
                        else:
                            # Try to find a similar group
                            for known_group, cat in correct_mappings.items():
                                if group.lower() in known_group.lower() or known_group.lower() in group.lower():
                                    category = cat
                                    logger.info(f"Found similar group '{known_group}' for '{group}', assigning to '{cat}'")
                                    break

                        # If no mapping found, use 'Other'
                        if not category:
                            category = 'Other'
                            logger.info(f"No mapping found for group '{group}', assigning to 'Other'")

                        # Store the mapping for this group
                        group_to_category[group] = category

                        # Add to the recalculated time_by_category
                        recalculated_time_by_category[category] += float(time)

                    # Replace the time_by_category with the recalculated one
                    if 'time_by_category' in llm_response['executive_summary']:
                        logger.info(f"Original time_by_category: {llm_response['executive_summary']['time_by_category']}")
                        logger.info(f"Recalculated time_by_category: {recalculated_time_by_category}")
                        llm_response['executive_summary']['time_by_category'] = recalculated_time_by_category

                    # Add a special field to help the frontend with group-to-category mapping
                    llm_response['group_to_category_mapping'] = group_to_category
                    logger.info(f"Added group_to_category_mapping: {group_to_category}")

                # Validate response using Pydantic model
                try:
                    report = WeeklyReport(**llm_response)
                except ValidationError as e:
                    logger.warning(f"First validation attempt failed: {e}")
                    # Try to fix the response and validate again
                    if 'executive_summary' in llm_response:
                        exec_summary = llm_response['executive_summary']

                        # Ensure all numeric values are floats
                        if 'total_time' in exec_summary and isinstance(exec_summary['total_time'], (int, float)):
                            exec_summary['total_time'] = float(exec_summary['total_time'])

                        # Convert time_by_group values to float
                        if 'time_by_group' in exec_summary and isinstance(exec_summary['time_by_group'], dict):
                            for group, time in list(exec_summary['time_by_group'].items()):
                                if isinstance(time, (int, float)):
                                    exec_summary['time_by_group'][group] = float(time)

                        # Convert time_by_category values to float
                        if 'time_by_category' in exec_summary and isinstance(exec_summary['time_by_category'], dict):
                            for category, time in list(exec_summary['time_by_category'].items()):
                                if isinstance(time, (int, float)):
                                    exec_summary['time_by_category'][category] = float(time)

                        # Ensure progress_report is a string
                        if 'progress_report' not in exec_summary or exec_summary['progress_report'] is None:
                            exec_summary['progress_report'] = f"Weekly report for {start_date} to {end_date}"

                    # Try validation again
                    report = WeeklyReport(**llm_response)

                # Add the HTML report to the report object
                report.html_report = html_report
                logger.info("Valid LLM response received and validated")
                # Save the report to a file
                report_filename = f"weekly_report_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.json"
                report_path = os.path.join(WEEKLY_REPORTS_DIR, report_filename)
                os.makedirs(WEEKLY_REPORTS_DIR, exist_ok=True)
                with open(report_path, 'w') as f:
                    report_dict = report.model_dump()
                    json.dump(report_dict, f, indent=2)
                logger.info(f"Weekly report saved to {report_path}")

                # Cache the report for future use
                try:
                    # Create a session
                    db = SessionLocal()

                    # Check if we already have a cached report for this date
                    existing_cache = db.query(ReportCache).filter(
                        ReportCache.report_type == 'weekly',
                        ReportCache.date == start_date.isoformat()
                    ).first()

                    if existing_cache:
                        # Update the existing cache
                        logger.info(f"Updating cached weekly report for {start_date} to {end_date}")
                        existing_cache.report_data = json.dumps(report_dict)
                        existing_cache.created_at = datetime.utcnow()
                    else:
                        # Create a new cache entry
                        logger.info(f"Creating new cached weekly report for {start_date} to {end_date}")
                        cache_entry = ReportCache(
                            report_type='weekly',
                            date=start_date.isoformat(),
                            report_data=json.dumps(report_dict),
                            created_at=datetime.utcnow()
                        )
                        db.add(cache_entry)

                    # Commit the changes
                    db.commit()
                    logger.info(f"Successfully cached weekly report for {start_date} to {end_date}")
                except Exception as e:
                    logger.error(f"Error caching report: {e}")
                    # Roll back any changes
                    db.rollback()
                finally:
                    # Close the session
                    db.close()

                return report_dict
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
    logger.error("*******************************************************************************")
    logger.error("* USING ORIGINAL WEEKLY REPORT ENDPOINT *")
    logger.error("* REDIRECTING TO CUSTOM WEEKLY REPORT ENDPOINT *")
    logger.error("*******************************************************************************")

    # Create a redirect response to the custom weekly report endpoint
    return RedirectResponse(url=f"/api/reports/custom-weekly-report?date={date}&force_refresh={force_refresh}")

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
async def get_monthly_report(date: str = Query(...), force_refresh: bool = Query(False)):
    """Get the monthly report for the month containing the specified date.
    If force_refresh is True, regenerate the report even if it already exists."""
    logger.info(f"Monthly report requested for date: {date}, force_refresh: {force_refresh}")
    logger.info(f"force_refresh type: {type(force_refresh)}")

    # Convert force_refresh to boolean if it's a string
    if isinstance(force_refresh, str):
        force_refresh = force_refresh.lower() == 'true'
        logger.info(f"Converted force_refresh to boolean: {force_refresh}")
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

        if os.path.exists(report_path) and not force_refresh:
            logger.info("Found existing report and force_refresh is False, loading it")
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
            # Report doesn't exist or force_refresh is True, generate a new one
            if force_refresh:
                logger.info(f"Force refresh requested for {month_name} {year}, generating a new report")
            else:
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

                    # Create time breakdown for the month
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

                    # Calculate total time and time breakdowns
                    total_time = sum(log["duration_minutes"] for log in logs_data)
                    time_by_group = {}
                    time_by_category = {}

                    # Process logs to create time breakdowns by group and category
                    for log in logs_data:
                        # Update group time
                        if log["group"] not in time_by_group:
                            time_by_group[log["group"]] = 0
                        time_by_group[log["group"]] += log["duration_minutes"]

                        # Update category time
                        if log["category"] not in time_by_category:
                            time_by_category[log["category"]] = 0
                        time_by_category[log["category"]] += log["duration_minutes"]

                    # Create visualizations dictionary
                    visualizations = {}

                    # Generate the HTML report
                    html_report = generate_html_report(
                        start_date=first_day,
                        end_date=last_day,
                        total_time=total_time,
                        time_by_group=time_by_group,
                        time_by_category=time_by_category,
                        daily_breakdown=daily_breakdown,
                        visualizations=visualizations,
                        logs_data=logs_data
                    )

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
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
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
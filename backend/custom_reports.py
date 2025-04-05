import json
import logging
import os
import traceback
from datetime import datetime, timedelta, date, time
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_
from models import SessionLocal, ActivityLog, Settings
from report_templates import DailyTimeBreakdown, ChartData, generate_html_report
from reports import WeeklyReport, generate_weekly_report

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create a router for the custom reports
router = APIRouter()

@router.get("/custom-weekly-report")
async def get_custom_weekly_report(date: str, force_refresh: bool = Query(True, description="Force regeneration of the report even if it already exists")):
    """Get a custom weekly report for the week containing the specified date, using our custom code instead of the LLM."""
    logger.error("*******************************************************************************")
    logger.error("* USING CUSTOM WEEKLY REPORT ENDPOINT *")
    logger.error("* FORCE REFRESH VALUE: " + str(force_refresh) + " *")
    logger.error("*******************************************************************************")
    try:
        # Parse the date
        try:
            report_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date}. Use YYYY-MM-DD.")

        # Calculate the start and end of the week
        start_date = report_date - timedelta(days=report_date.weekday())
        end_date = start_date + timedelta(days=6)
        logger.info(f"Generating custom weekly report for week {start_date} to {end_date}")

        # Create the report directory if it doesn't exist
        WEEKLY_REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../reports/weekly")
        os.makedirs(WEEKLY_REPORTS_DIR, exist_ok=True)

        # Define the report filename
        report_filename = f"custom_weekly_report_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.json"
        report_path = os.path.join(WEEKLY_REPORTS_DIR, report_filename)
        logger.info(f"Custom report will be saved to: {report_path}")

        # Always regenerate the report if force_refresh is True
        if force_refresh and os.path.exists(report_path):
            logger.info("Force refresh requested. Deleting existing custom report.")
            try:
                os.remove(report_path)
                logger.info(f"Deleted existing custom report at {report_path}")
            except Exception as e:
                logger.error(f"Error deleting existing custom report: {e}")

        # Check if the report already exists
        if os.path.exists(report_path) and not force_refresh:
            logger.info("Found existing custom report, loading it")
            try:
                with open(report_path, 'r') as f:
                    report_data = json.load(f)
                return report_data
            except Exception as e:
                logger.error(f"Error loading existing custom report: {e}")

        # Get the logs for the week
        with SessionLocal() as db:
            logs = db.query(ActivityLog).filter(
                ActivityLog.timestamp >= datetime.combine(start_date, time.min),
                ActivityLog.timestamp <= datetime.combine(end_date, time.max)
            ).all()

        if not logs:
            logger.warning("No logs found for the specified week")
            return {"message": "No logs found for the specified week"}

        # Convert logs to the format expected by the report generator
        logs_data = [{
            "group": log.group,
            "category": log.category,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "duration_minutes": log.duration_minutes,
            "description": log.description
        } for log in logs]

        # Calculate total time and time by group/category
        total_time = sum(log["duration_minutes"] for log in logs_data)
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

        # Process each log
        for log in logs_data:
            group = log["group"]
            category = log["category"]
            duration = log["duration_minutes"]
            log_date = datetime.strptime(log["timestamp"].split()[0], "%Y-%m-%d").date()
            day_str = log_date.strftime("%Y-%m-%d")

            # Update time by group
            if group not in time_by_group:
                time_by_group[group] = 0
            time_by_group[group] += duration

            # Update time by category
            if category not in time_by_category:
                time_by_category[category] = 0
            time_by_category[category] += duration

            # Update daily breakdown
            if day_str in daily_breakdown:
                daily_time = daily_breakdown[day_str]
                daily_time.total_time += duration

                # Update group time
                if group not in daily_time.time_by_group:
                    daily_time.time_by_group[group] = 0
                daily_time.time_by_group[group] += duration

                # Update category time
                if category not in daily_time.time_by_category:
                    daily_time.time_by_category[category] = 0
                daily_time.time_by_category[category] += duration

        # Use the LLM to generate the report
        try:
            logger.info(f"Calling generate_weekly_report with LLM (force_refresh: {force_refresh})")
            # Only regenerate the report if force_refresh is True
            report_data = await generate_weekly_report(start_date, end_date, logs_data, force_refresh=force_refresh)
            logger.info("Weekly report generation with LLM completed successfully")

            # Log the report data for debugging
            logger.info(f"Report data keys: {list(report_data.keys() if isinstance(report_data, dict) else [])}")

            # Check if the report contains HTML
            if isinstance(report_data, dict) and 'html_report' in report_data:
                html_length = len(report_data['html_report'])
                logger.info(f"HTML report length: {html_length}")
                # Log a snippet of the HTML to see if it contains our chart
                if html_length > 0:
                    html_snippet = report_data['html_report'][:500] + '... [truncated]'
                    logger.info(f"HTML snippet: {html_snippet}")
            else:
                logger.warning("No HTML report found in the generated data")

            # Modify the report data to include our custom HTML
            if isinstance(report_data, dict):
                # Generate a custom HTML report with our modified chart
                custom_html = generate_html_report(
                    start_date=start_date,
                    end_date=end_date,
                    total_time=total_time,
                    time_by_group=time_by_group,
                    time_by_category=time_by_category,
                    daily_breakdown=daily_breakdown,
                    visualizations={},
                    logs_data=logs_data
                )

                # Replace the HTML report with our custom one
                report_data['html_report'] = custom_html
                logger.info("Replaced HTML report with custom one containing modified chart")

            # Return the modified report data
            return report_data

        except Exception as e:
            logger.error(f"Error generating report with LLM: {e}")
            logger.error(traceback.format_exc())
            logger.warning("Falling back to basic report generation without LLM")

            # Create visualizations
            visualizations = {}

            # Generate the HTML report as a fallback
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

            # Create the report object
            report = WeeklyReport(html_report=html_report)

        # Save the report
        with open(report_path, 'w') as f:
            json.dump(report.model_dump(), f, indent=2)
        logger.info(f"Custom weekly report saved to {report_path}")

        return report.model_dump()

    except Exception as e:
        logger.error(f"Error generating custom weekly report: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error generating custom weekly report: {str(e)}")

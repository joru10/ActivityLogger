#!/usr/bin/env python3
"""
Test script for weekly report generation with enhanced visualizations.
This script will call the weekly report generation endpoint and save the HTML report to a file.
"""

import os
import json
import asyncio
import logging
from datetime import date, timedelta
from reports import generate_weekly_report
from models import SessionLocal, ActivityLog

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_weekly_report():
    """Test the weekly report generation with sample data."""
    # Get current date and calculate the start of the week (Monday)
    today = date.today()
    days_since_monday = today.weekday()
    start_date = today - timedelta(days=days_since_monday)
    end_date = start_date + timedelta(days=6)  # Sunday
    
    logger.info(f"Generating weekly report for period: {start_date} to {end_date}")
    
    # Create a database session
    db = SessionLocal()
    
    try:
        # Query the database for activity logs in the specified date range
        from datetime import datetime, time
        start_datetime = datetime.combine(start_date, time.min)  # Start of day
        end_datetime = datetime.combine(end_date, time.max)      # End of day
        
        logs = db.query(ActivityLog).filter(
            ActivityLog.timestamp >= start_datetime,
            ActivityLog.timestamp <= end_datetime
        ).all()
        
        logger.info(f"Found {len(logs)} logs in date range")
        
        # Convert logs to the format expected by the report generator
        logs_data = [{
            "group": log.group,
            "category": log.category,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "duration_minutes": log.duration_minutes,
            "description": log.description
        } for log in logs]
        
        # Generate the weekly report
        report_data = await generate_weekly_report(start_date, end_date, logs_data)
        
        # Save the HTML report to a file
        html_report = report_data.get("html_report", "")
        if html_report:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports", "test")
            os.makedirs(output_dir, exist_ok=True)
            
            output_file = os.path.join(output_dir, f"weekly_report_{start_date.strftime('%Y-%m-%d')}_test.html")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html_report)
            
            logger.info(f"HTML report saved to {output_file}")
            print(f"\nHTML report saved to {output_file}")
            print(f"Open this file in a web browser to view the report with visualizations.")
        else:
            logger.error("No HTML report generated")
            
    except Exception as e:
        logger.error(f"Error testing weekly report: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_weekly_report())

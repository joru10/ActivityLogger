"""
Module for generating daily activity reports.
"""

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

def generate_daily_report_html(start_date, end_date, logs_data):
    """
    Generate an HTML daily report.
    
    Args:
        start_date: Start date of the report period
        end_date: End date of the report period
        logs_data: List of activity log dictionaries
        
    Returns:
        HTML string containing the report
    """
    logger.info(f"Generating daily report HTML for {start_date} to {end_date}")
    
    # Initialize variables
    total_time = 0
    time_by_group = {}
    time_by_category = {}
    
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
        total_time += log.get("duration_minutes", 0)
        
        # Update group time with safe access
        group = log.get("group", "Uncategorized")
        if group not in time_by_group:
            time_by_group[group] = 0
        time_by_group[group] += log.get("duration_minutes", 0)
        
        # Update category time with safe access
        category = log.get("category", "Uncategorized")
        if category not in time_by_category:
            time_by_category[category] = 0
        time_by_category[category] += log.get("duration_minutes", 0)
    
    # Generate visualizations data in the format expected by report_templates.py
    visualizations = {
        "group_distribution": ChartData(
            chart_type="doughnut",
            labels=list(time_by_group.keys()),
            datasets=[{
                "label": "Time Spent (minutes)",
                "data": list(time_by_group.values()),
                "backgroundColor": [
                    f"rgba({i*50 % 255}, {i*100 % 255}, {i*150 % 255}, 0.7)" 
                    for i in range(len(time_by_group))
                ]
            }],
            title="Time Spent by Group",
            description="Distribution of time spent across different groups"
        ),
        "category_distribution": ChartData(
            chart_type="pie",
            labels=list(time_by_category.keys()),
            datasets=[{
                "label": "Time Spent (minutes)",
                "data": list(time_by_category.values()),
                "backgroundColor": [
                    f"rgba({i*75 % 255}, {i*125 % 255}, {i*200 % 255}, 0.7)" 
                    for i in range(len(time_by_category))
                ]
            }],
            title="Time Spent by Category",
            description="Distribution of time spent across different categories"
        )
    }
    
    # Generate the HTML report
    return generate_html_report(
        start_date=start_date,
        end_date=end_date,
        total_time=total_time,
        time_by_group=time_by_group,
        time_by_category=time_by_category,
        daily_breakdown={},  # Not used for daily reports
        visualizations=visualizations,
        logs_data=logs_data
    )

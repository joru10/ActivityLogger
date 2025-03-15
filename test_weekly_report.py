#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime, date, time, timedelta
from sqlalchemy import and_

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import required modules
from backend.models import SessionLocal, ActivityLog, Settings
from backend.report_templates import generate_html_report, ChartData, DailyTimeBreakdown

def test_weekly_report():
    """
    Generate a test weekly report to verify the combined visualization functionality.
    """
    # Calculate the date range for the current week
    today = date.today()
    days_since_monday = today.weekday()  # 0 = Monday, 6 = Sunday
    start_date = today - timedelta(days=days_since_monday)
    end_date = start_date + timedelta(days=6)
    
    print(f"Generating weekly report for: {start_date} to {end_date}")
    
    # Create a database session
    db = SessionLocal()
    
    try:
        # Convert date objects to datetime objects for database query
        start_datetime = datetime.combine(start_date, time.min)  # Start of day
        end_datetime = datetime.combine(end_date, time.max)      # End of day
        
        # Query the database for activity logs in the specified date range
        logs = db.query(ActivityLog).filter(
            and_(
                ActivityLog.timestamp >= start_datetime,
                ActivityLog.timestamp <= end_datetime
            )
        ).all()
        
        print(f"Found {len(logs)} logs in date range")
        
        # Check if we have any logs
        if not logs:
            print(f"No activity logs found for week {start_date} to {end_date}")
            return
        
        # Convert logs to the format expected by the report generator
        logs_data = [{
            "group": log.group,
            "category": log.category,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "duration_minutes": log.duration_minutes,
            "description": log.description
        } for log in logs]
        
        # Calculate time by group and category
        time_by_group = {}
        time_by_category = {}
        daily_breakdown = {}
        
        # Process logs to calculate time distributions
        for log in logs_data:
            group = log.get("group", "Uncategorized")
            category = log.get("category", "Uncategorized")
            duration = log.get("duration_minutes", 0)
            log_date = log.get("timestamp", "").split()[0]  # Extract date part
            
            # Update time by group
            time_by_group[group] = time_by_group.get(group, 0) + duration
            
            # Update time by category
            time_by_category[category] = time_by_category.get(category, 0) + duration
            
            # Update daily breakdown
            if log_date not in daily_breakdown:
                daily_breakdown[log_date] = DailyTimeBreakdown(
                    total_time=0,
                    time_by_group={},
                    time_by_category={}
                )
            
            daily_breakdown[log_date].total_time += duration
            daily_breakdown[log_date].time_by_group[group] = daily_breakdown[log_date].time_by_group.get(group, 0) + duration
            daily_breakdown[log_date].time_by_category[category] = daily_breakdown[log_date].time_by_category.get(category, 0) + duration
        
        # Create visualizations data
        visualizations = {
            "daily_activity": ChartData(
                chart_type="bar",
                title="Daily Activity Distribution",
                labels=[],
                datasets=[{
                    "label": "Minutes",
                    "data": []
                }]
            ),
            "group_distribution": ChartData(
                chart_type="pie",
                title="Activity Distribution by Group",
                labels=list(time_by_group.keys()),
                datasets=[{
                    "label": "Minutes",
                    "data": list(time_by_group.values()),
                    "backgroundColor": [f"rgba({(i*50)%255}, {(i*100)%255}, {(i*150)%255}, 0.7)" for i in range(len(time_by_group))]
                }]
            ),
            "category_distribution": ChartData(
                chart_type="doughnut",
                title="Activity Distribution by Category",
                labels=list(time_by_category.keys()),
                datasets=[{
                    "label": "Minutes",
                    "data": list(time_by_category.values()),
                    "backgroundColor": [f"rgba({(i*70)%255}, {(i*120)%255}, {(i*170)%255}, 0.7)" for i in range(len(time_by_category))]
                }]
            )
        }
        
        # Get the settings to understand category-group relationships
        import sqlite3
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', 'activity_logs.db'))
        cursor = conn.cursor()
        cursor.execute('SELECT categories FROM settings LIMIT 1')
        result = cursor.fetchone()
        if result and result[0]:
            categories_config = json.loads(result[0])
        else:
            categories_config = []
        conn.close()
        
        # Create a mapping of groups to their categories
        group_to_category = {}
        for cat_config in categories_config:
            cat_name = cat_config.get('name', '')
            for group_name in cat_config.get('groups', []):
                group_to_category[group_name] = cat_name
        
        # Organize groups by category
        groups_by_category = {}
        for group, group_time in time_by_group.items():
            category = group_to_category.get(group, 'Other')
            if category not in groups_by_category:
                groups_by_category[category] = []
            groups_by_category[category].append({'name': group, 'time': group_time})
        
        # Generate distinct colors for groups
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
        
        # Get all unique groups
        all_groups = list(time_by_group.keys())
        group_colors = get_distinct_colors(len(all_groups))
        group_color_map = {group: color for group, color in zip(all_groups, group_colors)}
        
        # Create datasets for the combined chart
        combined_datasets = []
        categories = list(time_by_category.keys())
        
        # For each category, create datasets for each of its groups
        for category in categories:
            category_groups = groups_by_category.get(category, [])
            category_groups.sort(key=lambda x: x['time'], reverse=True)
            
            for group_info in category_groups:
                group_name = group_info['name']
                group_time = group_info['time']
                
                # Create data array with zeros for all categories except this one
                data = [0] * len(categories)
                category_index = categories.index(category)
                data[category_index] = group_time
                
                combined_datasets.append({
                    "label": f"{category} - {group_name}",
                    "data": data,
                    "backgroundColor": group_color_map.get(group_name, "rgba(200, 200, 200, 0.7)"),
                    "borderColor": group_color_map.get(group_name, "rgba(200, 200, 200, 1)").replace('0.7', '1'),
                    "borderWidth": 1,
                    "stack": category  # Stack bars by category
                })
        
        # Add the combined category-group chart
        visualizations["category_group_chart"] = ChartData(
            chart_type="bar",
            title="Combined Category-Group Distribution",
            labels=categories,
            datasets=combined_datasets
        )
        
        # Generate the HTML report
        total_time = sum(log.get("duration_minutes", 0) for log in logs_data)
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
        
        # Save the HTML report to a file for inspection
        reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "weekly")
        os.makedirs(reports_dir, exist_ok=True)
        
        report_filename = f"test_weekly_report_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.html"
        report_path = os.path.join(reports_dir, report_filename)
        
        with open(report_path, 'w') as f:
            f.write(html_report)
        
        print(f"Weekly report saved to: {report_path}")
        
    except Exception as e:
        print(f"Error generating weekly report: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_weekly_report()

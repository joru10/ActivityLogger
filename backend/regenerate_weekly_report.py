"""
Script to regenerate the HTML report for a specific weekly report.
This script uses the actual data in the report to generate a proper HTML report.
"""

import json
import os
import logging
from datetime import datetime, date
from pathlib import Path
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the reports directory
REPORTS_DIR = Path(__file__).parent.parent / "reports"
WEEKLY_REPORTS_DIR = REPORTS_DIR / "weekly"

def generate_proper_html_report(report_data):
    """
    Generate a proper HTML report using the visualization logic from report_templates.py.
    
    Args:
        report_data: The report data dictionary
        
    Returns:
        HTML string containing the report
    """
    from datetime import date
    from report_templates import generate_html_report, ChartData
    
    # Extract data from the report
    executive_summary = report_data.get("executive_summary", {})
    total_time = executive_summary.get("total_time", 0)
    time_by_group = executive_summary.get("time_by_group", {})
    time_by_category = executive_summary.get("time_by_category", {})
    daily_breakdown = executive_summary.get("daily_breakdown", {})
    details = report_data.get("details", [])
    
    # Convert dates to date objects
    start_date = date.fromisoformat(report_data.get("start_date"))
    end_date = date.fromisoformat(report_data.get("end_date"))
    
    # Convert daily_breakdown to use DailyTimeBreakdown objects
    processed_daily_breakdown = {}
    for day, data in daily_breakdown.items():
        processed_daily_breakdown[day] = {
            "total_time": data.get("total_time", 0),
            "time_by_group": data.get("time_by_group", {}),
            "time_by_category": data.get("time_by_category", {})
        }
    
    # Generate the HTML report using the template function
    return generate_html_report(
        start_date=start_date,
        end_date=end_date,
        total_time=total_time,
        time_by_group=time_by_group,
        time_by_category=time_by_category,
        daily_breakdown=processed_daily_breakdown,
        visualizations={
            "time_by_group": ChartData(
                chart_type="bar",
                title="Time Spent by Group",
                description="Total time spent on each activity group",
                labels=list(time_by_group.keys()),
                datasets=[{
                    "label": "Hours",
                    "data": [time / 60 for time in time_by_group.values()],  # Convert minutes to hours
                    "backgroundColor": "rgba(54, 162, 235, 0.5)",
                    "borderColor": "rgba(54, 162, 235, 1)",
                    "borderWidth": 1
                }]
            )
        },
        logs_data=details
    )
    
    # Create HTML for activity log
    activity_log_html = ""
    for activity in details:
        timestamp = activity.get("timestamp", "")
        if timestamp:
            try:
                formatted_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M")
            except ValueError:
                formatted_time = timestamp
        else:
            formatted_time = ""
            
        group = activity.get("group", "")
        category = activity.get("category", "")
        duration = activity.get("duration_minutes", 0)
        description = activity.get("description", "")
        
        activity_log_html += f"""
        <tr>
            <td>{formatted_time}</td>
            <td>{group}</td>
            <td>{category}</td>
            <td>{duration} minutes</td>
            <td>{description}</td>
        </tr>
        """
    
    # Generate the full HTML report
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Weekly Activity Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            .section {{
                margin-bottom: 30px;
                border: 1px solid #eee;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .day-section {{
                margin-bottom: 20px;
                padding: 15px;
                background-color: #f9f9f9;
                border-radius: 5px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th, td {{
                padding: 12px 15px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }}
            th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}
            tr:hover {{
                background-color: #f5f5f5;
            }}
            .chart-container {{
                height: 400px;
                margin-bottom: 30px;
            }}
            .summary-stats {{
                display: flex;
                justify-content: space-between;
                flex-wrap: wrap;
                margin-bottom: 20px;
            }}
            .stat-card {{
                flex: 1;
                min-width: 200px;
                margin: 10px;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .stat-card h3 {{
                margin-top: 0;
                color: #3498db;
            }}
            .stat-card p {{
                font-size: 1.5em;
                font-weight: bold;
                margin: 10px 0;
            }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        <h1>Weekly Activity Report</h1>
        
        <div class="section">
            <h2>Executive Summary</h2>
            
            <div class="summary-stats">
                <div class="stat-card">
                    <h3>Total Time</h3>
                    <p>{time_display}</p>
                </div>
                <div class="stat-card">
                    <h3>Activities</h3>
                    <p>{len(details)}</p>
                </div>
                <div class="stat-card">
                    <h3>Groups</h3>
                    <p>{len(time_by_group)}</p>
                </div>
            </div>
            
            <div class="chart-container">
                <canvas id="timeByGroupChart"></canvas>
            </div>
            
            <h3>Time by Group</h3>
            <table>
                <thead>
                    <tr>
                        <th>Group</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    {time_by_group_html}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>Daily Breakdown</h2>
            {daily_breakdown_html}
        </div>
        
        <div class="section">
            <h2>Activity Log</h2>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Group</th>
                        <th>Category</th>
                        <th>Duration</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    {activity_log_html}
                </tbody>
            </table>
        </div>
        
        <script>
            // Create chart for time by group
            const ctx = document.getElementById('timeByGroupChart').getContext('2d');
            const timeByGroupChart = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: {json.dumps(list(time_by_group.keys()))},
                    datasets: [{{
                        label: 'Time (minutes)',
                        data: {json.dumps(list(time_by_group.values()))},
                        backgroundColor: [
                            'rgba(54, 162, 235, 0.7)',
                            'rgba(255, 99, 132, 0.7)',
                            'rgba(255, 206, 86, 0.7)',
                            'rgba(75, 192, 192, 0.7)',
                            'rgba(153, 102, 255, 0.7)',
                            'rgba(255, 159, 64, 0.7)',
                            'rgba(199, 199, 199, 0.7)',
                            'rgba(83, 102, 255, 0.7)',
                            'rgba(40, 159, 64, 0.7)',
                            'rgba(210, 199, 199, 0.7)'
                        ],
                        borderColor: [
                            'rgba(54, 162, 235, 1)',
                            'rgba(255, 99, 132, 1)',
                            'rgba(255, 206, 86, 1)',
                            'rgba(75, 192, 192, 1)',
                            'rgba(153, 102, 255, 1)',
                            'rgba(255, 159, 64, 1)',
                            'rgba(199, 199, 199, 1)',
                            'rgba(83, 102, 255, 1)',
                            'rgba(40, 159, 64, 1)',
                            'rgba(210, 199, 199, 1)'
                        ],
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            title: {{
                                display: true,
                                text: 'Minutes'
                            }}
                        }}
                    }},
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Time Spent by Group',
                            font: {{
                                size: 16
                            }}
                        }},
                        legend: {{
                            display: false
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return html

def regenerate_report(report_path):
    """
    Regenerate the HTML report for a specific report file.
    
    Args:
        report_path: Path to the report file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read the report file
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        # Generate a proper HTML report
        html_report = generate_proper_html_report(report_data)
        
        # Update the report data
        report_data['html_report'] = html_report
        
        # Save the updated report
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"Successfully regenerated HTML report for {report_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error regenerating report {report_path}: {e}")
        return False

def main():
    # Check if a specific report file was specified
    if len(sys.argv) > 1:
        report_file = sys.argv[1]
        report_path = WEEKLY_REPORTS_DIR / report_file
        if not report_path.exists():
            logger.error(f"Report file {report_path} does not exist")
            return
        
        regenerate_report(report_path)
    else:
        # Regenerate all weekly reports
        report_files = list(WEEKLY_REPORTS_DIR.glob("weekly_report_*.json"))
        logger.info(f"Found {len(report_files)} weekly report files")
        
        success_count = 0
        for report_file in report_files:
            if regenerate_report(report_file):
                success_count += 1
        
        logger.info(f"Successfully regenerated {success_count} out of {len(report_files)} reports")

if __name__ == "__main__":
    main()

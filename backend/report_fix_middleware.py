"""
Middleware for fixing report generation issues.
This module provides functions to ensure that all reports have valid HTML content.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
import importlib.util
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the reports directory
REPORTS_DIR = Path(__file__).parent.parent / "reports"
WEEKLY_REPORTS_DIR = REPORTS_DIR / "weekly"
MONTHLY_REPORTS_DIR = REPORTS_DIR / "monthly"
QUARTERLY_REPORTS_DIR = REPORTS_DIR / "quarterly"
ANNUAL_REPORTS_DIR = REPORTS_DIR / "annual"

def ensure_report_directories():
    """Ensure all report directories exist."""
    for directory in [REPORTS_DIR, WEEKLY_REPORTS_DIR, MONTHLY_REPORTS_DIR, QUARTERLY_REPORTS_DIR, ANNUAL_REPORTS_DIR]:
        os.makedirs(directory, exist_ok=True)

def generate_proper_html_report(report_data, report_type="weekly"):
    """
    Generate a proper HTML report using the actual data in the report.
    
    Args:
        report_data: The report data dictionary
        report_type: Type of report (weekly, monthly, etc.)
        
    Returns:
        HTML string containing the report
    """
    # Try to import the enhanced report generator
    try:
        from enhanced_report_generator import generate_enhanced_html_report
        return generate_enhanced_html_report(report_data)
    except ImportError:
        logger.warning("Enhanced report generator not found, using basic report generator")
        
    # Extract data from the report
    executive_summary = report_data.get("executive_summary", {})
    total_time = executive_summary.get("total_time", 0)
    time_by_group = executive_summary.get("time_by_group", {})
    time_by_category = executive_summary.get("time_by_category", {})
    daily_breakdown = executive_summary.get("daily_breakdown", {})
    details = report_data.get("details", [])
    
    # Format time as hours and minutes
    hours = total_time // 60
    minutes = total_time % 60
    time_display = f"{hours} hours {minutes} minutes"
    
    # Prepare data for daily activity distribution chart
    days = sorted(daily_breakdown.keys())
    daily_times = [daily_breakdown[day].get("total_time", 0) for day in days]
    formatted_days = [datetime.strptime(day, "%Y-%m-%d").strftime("%a %m-%d") for day in days]
    
    # Create HTML for time by group
    time_by_group_html = ""
    for group, minutes in time_by_group.items():
        group_hours = minutes // 60
        group_minutes = minutes % 60
        time_by_group_html += f"<tr><td>{group}</td><td>{group_hours} hours {group_minutes} minutes</td></tr>"
    
    # Create HTML for time by category
    time_by_category_html = ""
    for category, minutes in time_by_category.items():
        category_hours = minutes // 60
        category_minutes = minutes % 60
        time_by_category_html += f"<tr><td>{category}</td><td>{category_hours} hours {category_minutes} minutes</td></tr>"
    
    # Create HTML for daily breakdown
    daily_breakdown_html = ""
    for day, data in sorted(daily_breakdown.items()):
        day_date = datetime.strptime(day, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        day_total = data.get("total_time", 0)
        day_hours = day_total // 60
        day_minutes = day_total % 60
        
        # Create HTML for groups in this day
        day_groups_html = ""
        for group, minutes in data.get("time_by_group", {}).items():
            group_hours = minutes // 60
            group_minutes = minutes % 60
            day_groups_html += f"<tr><td>{group}</td><td>{group_hours} hours {group_minutes} minutes</td></tr>"
        
        # Create HTML for categories in this day
        day_categories_html = ""
        for category, minutes in data.get("time_by_category", {}).items():
            category_hours = minutes // 60
            category_minutes = minutes % 60
            day_categories_html += f"<tr><td>{category}</td><td>{category_hours} hours {category_minutes} minutes</td></tr>"
        
        daily_breakdown_html += f"""
        <div class="day-section">
            <h3>{day_date}</h3>
            <p>Total time: {day_hours} hours {day_minutes} minutes</p>
            <div class="day-tables">
                <div class="day-table">
                    <h4>Time by Group</h4>
                    <table class="group-table">
                        <thead>
                            <tr>
                                <th>Group</th>
                                <th>Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {day_groups_html}
                        </tbody>
                    </table>
                </div>
                <div class="day-table">
                    <h4>Time by Category</h4>
                    <table class="category-table">
                        <thead>
                            <tr>
                                <th>Category</th>
                                <th>Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {day_categories_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """
    
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
        <title>{report_type.capitalize()} Activity Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3, h4 {{
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
            .day-tables {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }}
            .day-table {{
                flex: 1;
                min-width: 300px;
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
            .charts-row {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
                margin-bottom: 30px;
            }}
            .chart-box {{
                flex: 1;
                min-width: 45%;
                height: 400px;
                padding: 15px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
        <h1>{report_type.capitalize()} Activity Report</h1>
        
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
            
            <h3>Visualizations</h3>
            
            <div class="chart-container">
                <canvas id="dailyActivityChart"></canvas>
            </div>
            
            <div class="charts-row">
                <div class="chart-box">
                    <canvas id="timeByGroupChart"></canvas>
                </div>
                <div class="chart-box">
                    <canvas id="timeByCategory"></canvas>
                </div>
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
            
            <h3>Time by Category</h3>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    {time_by_category_html}
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
            // Create chart for daily activity
            const dailyCtx = document.getElementById('dailyActivityChart').getContext('2d');
            const dailyActivityChart = new Chart(dailyCtx, {{
                type: 'bar',
                data: {{
                    labels: {json.dumps(formatted_days)},
                    datasets: [{{
                        label: 'Minutes',
                        data: {json.dumps(daily_times)},
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
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
                            text: 'Daily Activity Distribution',
                            font: {{
                                size: 16
                            }}
                        }},
                        legend: {{
                            display: true
                        }}
                    }}
                }}
            }});
            
            // Create chart for time by group
            const groupCtx = document.getElementById('timeByGroupChart').getContext('2d');
            const timeByGroupChart = new Chart(groupCtx, {{
                type: 'pie',
                data: {{
                    labels: {json.dumps(list(time_by_group.keys()))},
                    datasets: [{{
                        label: 'Time (minutes)',
                        data: {json.dumps(list(time_by_group.values()))},
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.7)',
                            'rgba(54, 162, 235, 0.7)',
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
                            'rgba(255, 99, 132, 1)',
                            'rgba(54, 162, 235, 1)',
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
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Activity Distribution by Group',
                            font: {{
                                size: 16
                            }}
                        }},
                        legend: {{
                            display: true,
                            position: 'right'
                        }}
                    }}
                }}
            }});
            
            // Create chart for time by category
            const categoryCtx = document.getElementById('timeByCategory').getContext('2d');
            const timeByCategoryChart = new Chart(categoryCtx, {{
                type: 'pie',
                data: {{
                    labels: {json.dumps(list(time_by_category.keys()))},
                    datasets: [{{
                        label: 'Time (minutes)',
                        data: {json.dumps(list(time_by_category.values()))},
                        backgroundColor: [
                            'rgba(75, 192, 192, 0.7)',
                            'rgba(153, 102, 255, 0.7)',
                            'rgba(255, 159, 64, 0.7)',
                            'rgba(255, 99, 132, 0.7)',
                            'rgba(54, 162, 235, 0.7)',
                            'rgba(255, 206, 86, 0.7)',
                            'rgba(199, 199, 199, 0.7)',
                            'rgba(83, 102, 255, 0.7)',
                            'rgba(40, 159, 64, 0.7)',
                            'rgba(210, 199, 199, 0.7)'
                        ],
                        borderColor: [
                            'rgba(75, 192, 192, 1)',
                            'rgba(153, 102, 255, 1)',
                            'rgba(255, 159, 64, 1)',
                            'rgba(255, 99, 132, 1)',
                            'rgba(54, 162, 235, 1)',
                            'rgba(255, 206, 86, 1)',
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
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Activity Distribution by Category',
                            font: {{
                                size: 16
                            }}
                        }},
                        legend: {{
                            display: true,
                            position: 'right'
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return html

def fix_report(report_path, report_type="weekly"):
    """
    Fix a report by ensuring it has valid HTML content.
    
    Args:
        report_path: Path to the report file
        report_type: Type of report (weekly, monthly, etc.)
        
    Returns:
        True if the report was fixed, False otherwise
    """
    try:
        # Read the report file
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        # Check if the HTML report is empty or too small
        html_report = report_data.get('html_report', '')
        if not html_report or len(html_report) < 100:
            logger.info(f"Fixing empty HTML report in {report_path}")
            
            # Generate a proper HTML report
            html_report = generate_proper_html_report(report_data, report_type)
            
            # Update the report data
            report_data['html_report'] = html_report
            
            # Save the updated report
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            logger.info(f"Fixed {report_type} report {report_path}")
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"Error fixing report {report_path}: {e}")
        return False

def fix_all_reports():
    """Fix all reports by ensuring they have valid HTML content."""
    ensure_report_directories()
    
    # Fix weekly reports
    weekly_reports = list(WEEKLY_REPORTS_DIR.glob("weekly_report_*.json"))
    logger.info(f"Found {len(weekly_reports)} weekly reports")
    fixed_weekly = sum(1 for r in weekly_reports if fix_report(r, "weekly"))
    
    # Fix monthly reports
    monthly_reports = list(MONTHLY_REPORTS_DIR.glob("monthly_report_*.json"))
    logger.info(f"Found {len(monthly_reports)} monthly reports")
    fixed_monthly = sum(1 for r in monthly_reports if fix_report(r, "monthly"))
    
    # Fix quarterly reports
    quarterly_reports = list(QUARTERLY_REPORTS_DIR.glob("quarterly_report_*.json"))
    logger.info(f"Found {len(quarterly_reports)} quarterly reports")
    fixed_quarterly = sum(1 for r in quarterly_reports if fix_report(r, "quarterly"))
    
    # Fix annual reports
    annual_reports = list(ANNUAL_REPORTS_DIR.glob("annual_report_*.json"))
    logger.info(f"Found {len(annual_reports)} annual reports")
    fixed_annual = sum(1 for r in annual_reports if fix_report(r, "annual"))
    
    logger.info(f"Fixed reports: {fixed_weekly} weekly, {fixed_monthly} monthly, {fixed_quarterly} quarterly, {fixed_annual} annual")

def patch_report_generation():
    """
    Patch the report generation functions to ensure they always produce valid HTML reports.
    This function monkey-patches the necessary functions at runtime.
    """
    try:
        # Import the reports module
        import reports
        
        # Store the original generate_html_report function
        original_generate_html_report = reports.generate_html_report
        
        # Define a wrapper function that ensures HTML content is generated
        def generate_html_report_wrapper(*args, **kwargs):
            try:
                # Call the original function
                html_report = original_generate_html_report(*args, **kwargs)
                
                # Check if the HTML report is empty or too small
                if not html_report or len(html_report) < 100:
                    logger.warning("HTML report is empty or too small, generating fallback")
                    
                    # Create a fallback report
                    if len(args) >= 8:  # If we have all the expected arguments
                        start_date, end_date, total_time, time_by_group, time_by_category, daily_breakdown, _, logs_data = args[:8]
                        
                        # Create report data
                        report_data = {
                            "executive_summary": {
                                "total_time": total_time,
                                "time_by_group": time_by_group,
                                "time_by_category": time_by_category,
                                "daily_breakdown": daily_breakdown,
                                "progress_report": f"Basic report generated from {len(logs_data)} activities."
                            },
                            "details": logs_data
                        }
                        
                        # Generate a proper HTML report
                        html_report = generate_proper_html_report(report_data)
                
                return html_report
            except Exception as e:
                logger.error(f"Error in generate_html_report_wrapper: {e}")
                # Return a minimal HTML report as a last resort
                return """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Activity Report</title>
                    <style>
                        body { font-family: Arial, sans-serif; padding: 20px; }
                        h1 { color: #2c3e50; }
                        .error { color: red; }
                    </style>
                </head>
                <body>
                    <h1>Activity Report</h1>
                    <div class="error">
                        <p>There was an error generating the report. Please try regenerating this report.</p>
                    </div>
                </body>
                </html>
                """
        
        # Replace the original function with our wrapper
        reports.generate_html_report = generate_html_report_wrapper
        logger.info("Successfully patched report generation functions")
        
    except Exception as e:
        logger.error(f"Error patching report generation functions: {e}")

# Run the fix when the module is imported
fix_all_reports()

# Try to patch the report generation functions
try:
    patch_report_generation()
except Exception as e:
    logger.error(f"Error patching report generation: {e}")

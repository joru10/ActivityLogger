"""
This script fixes the weekly report generation issue by ensuring that the HTML report
is properly generated and not empty.

Run this script with:
python fix_weekly_report.py
"""

import os
import json
import logging
from datetime import datetime, date, time
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the reports directory
REPORTS_DIR = Path(__file__).parent.parent / "reports"
WEEKLY_REPORTS_DIR = REPORTS_DIR / "weekly"

def fix_weekly_reports():
    """
    Fix all weekly reports by ensuring they have proper HTML content.
    """
    logger.info(f"Checking weekly reports directory: {WEEKLY_REPORTS_DIR}")
    
    # Create the directory if it doesn't exist
    os.makedirs(WEEKLY_REPORTS_DIR, exist_ok=True)
    
    # Get all weekly report files
    report_files = list(WEEKLY_REPORTS_DIR.glob("weekly_report_*.json"))
    logger.info(f"Found {len(report_files)} weekly report files")
    
    fixed_count = 0
    
    for report_file in report_files:
        try:
            with open(report_file, 'r') as f:
                report_data = json.load(f)
            
            # Check if the HTML report is empty
            if not report_data.get('html_report'):
                logger.info(f"Fixing empty HTML report in {report_file}")
                
                # Generate a simple HTML report
                html_report = generate_simple_html_report(report_file.name)
                
                # Update the report data
                report_data['html_report'] = html_report
                
                # Save the updated report
                with open(report_file, 'w') as f:
                    json.dump(report_data, f, indent=2)
                
                fixed_count += 1
                logger.info(f"Fixed report {report_file}")
            else:
                logger.info(f"Report {report_file} already has HTML content")
        
        except Exception as e:
            logger.error(f"Error processing {report_file}: {e}")
    
    logger.info(f"Fixed {fixed_count} weekly reports")

def generate_simple_html_report(report_name):
    """
    Generate a simple HTML report that will display properly in the frontend.
    """
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
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    </head>
    <body>
        <h1>Weekly Activity Report</h1>
        
        <div class="section">
            <h2>Executive Summary</h2>
            <p>This is a fixed weekly report that was previously empty. The original report data may have been incomplete.</p>
            <p>Please try generating a new report using the "Force Generate Report" button.</p>
        </div>
        
        <div class="section">
            <h2>Activity Log</h2>
            <p>No activity data available. Please regenerate this report.</p>
        </div>
        
        <script>
            $(document).ready(function() {{
                console.log('Report loaded successfully');
            }});
        </script>
    </body>
    </html>
    """
    
    return html

if __name__ == "__main__":
    fix_weekly_reports()

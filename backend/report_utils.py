"""
Utility functions for report generation and validation.
"""

import logging
import json
import os
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_html_report(report_path, report_type="report"):
    """
    Ensures that a report file has valid HTML content.
    If the HTML content is empty, generates a placeholder HTML report.
    
    Args:
        report_path: Path to the report JSON file
        report_type: Type of report (weekly, monthly, etc.) for logging
        
    Returns:
        True if the report was fixed, False if no fix was needed
    """
    try:
        # Read the report file
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        # Check if the HTML report is empty
        if not report_data.get('html_report'):
            logger.info(f"Fixing empty HTML report in {report_path}")
            
            # Generate a simple HTML report
            report_name = os.path.basename(report_path)
            html_report = generate_placeholder_html(report_name, report_type)
            
            # Update the report data
            report_data['html_report'] = html_report
            
            # Save the updated report
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            logger.info(f"Fixed {report_type} report {report_path}")
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"Error processing {report_path}: {e}")
        return False

def generate_placeholder_html(report_name, report_type="Weekly"):
    """
    Generate a placeholder HTML report that will display properly in the frontend.
    
    Args:
        report_name: Name of the report file
        report_type: Type of report (Weekly, Monthly, etc.)
        
    Returns:
        HTML string for the placeholder report
    """
    title = f"{report_type.capitalize()} Activity Report"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
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
            .alert {{
                background-color: #f8d7da;
                color: #721c24;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .info {{
                background-color: #d1ecf1;
                color: #0c5460;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
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
            .button {{
                display: inline-block;
                padding: 10px 15px;
                background-color: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                cursor: pointer;
            }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    </head>
    <body>
        <h1>{title}</h1>
        
        <div class="alert">
            <h3>Report Notice</h3>
            <p>This is a placeholder report. The original report data may have been incomplete or missing.</p>
            <p>Please try generating a new report using the "Force Generate Report" button.</p>
        </div>
        
        <div class="section">
            <h2>Executive Summary</h2>
            <p>No activity data available. Please regenerate this report.</p>
        </div>
        
        <div class="section">
            <h2>Activity Log</h2>
            <p>No activity data available. Please regenerate this report.</p>
        </div>
        
        <script>
            $(document).ready(function() {{
                console.log('Placeholder report loaded successfully');
            }});
        </script>
    </body>
    </html>
    """
    
    return html

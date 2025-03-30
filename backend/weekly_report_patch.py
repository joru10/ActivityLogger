"""
This is a patch script to fix the weekly report generation issue.
Run this script to apply the fix to the reports.py file.
"""

import os
import re

def apply_patch():
    # Path to the reports.py file
    reports_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports.py")
    
    # Read the current content of the file
    with open(reports_file, 'r') as f:
        content = f.read()
    
    # Find the weekly report generation code
    pattern = r'# Generate HTML report with embedded charts\s+html_report = generate_html_report\(start_date, end_date, total_time, time_by_group,\s+time_by_category, daily_breakdown, visualizations, logs_data\)'
    
    # Replacement code that uses the correct function signature
    replacement = """# Generate HTML report with embedded charts
            # Import the report_templates module to ensure we have the latest version
            from report_templates import generate_html_report
            
            # Create a title for the report
            title = f"Weekly Activity Report - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            
            # Generate the HTML report with the correct parameters
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
            
            # Log the HTML report length to verify it's not empty
            logger.info(f"Generated weekly HTML report with length: {len(html_report)}")"""
    
    # Apply the replacement
    new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Write the updated content back to the file
    with open(reports_file, 'w') as f:
        f.write(new_content)
    
    print("Patch applied successfully!")

if __name__ == "__main__":
    apply_patch()

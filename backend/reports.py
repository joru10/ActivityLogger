# backend/reports.py
import os
import json
import re
import requests
import logging
import yaml
from datetime import datetime, timedelta, date
from apscheduler.schedulers.background import BackgroundScheduler
from models import SessionLocal, ActivityLog

logger = logging.getLogger(__name__)

# Compute the reports directory relative to this file's location.
base_dir = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(base_dir, "..", "reports", "daily")
os.makedirs(REPORTS_DIR, exist_ok=True)

def load_report_profile(profile_name: str) -> str:
    """
    Loads the YAML profile for reports from the profiles folder.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_path = os.path.join(base_dir, "..", "profiles", f"{profile_name}.yaml")
    if not os.path.exists(profile_path):
        logger.error(f"Profile {profile_name} not found at {profile_path}")
        return ""
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = yaml.safe_load(f)
    return profile_data.get("prompt", "")

def remove_json_comments(json_str: str) -> str:
    """Remove C++-style inline comments from a JSON string."""
    return re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)

def generate_daily_report():
    logger.info("Generating Daily Report")
    # Get today's date (assume report for today)
    today = date.today()
    start_date = datetime.combine(today, datetime.min.time())
    end_date = start_date + timedelta(days=1)

    db = SessionLocal()
    try:
        logs = db.query(ActivityLog).filter(
            ActivityLog.timestamp >= start_date,
            ActivityLog.timestamp < end_date
        ).all()
        logs_data = [
            {k: v for k, v in log.__dict__.items() if k != "_sa_instance_state"}
            for log in logs
        ]
    except Exception as e:
        logger.error("Error fetching logs: " + str(e))
        logs_data = []
    finally:
        db.close()
    
    # Load the daily report profile
    report_profile_prompt = load_report_profile("ActivityReports_Daily")
    if not report_profile_prompt:
        logger.error("ActivityReports_Daily profile could not be loaded.")
        return

    # Construct the full prompt.
    full_prompt = f"{report_profile_prompt}\n\nActivity Logs:\n{json.dumps(logs_data, indent=2, default=str)}"
    payload = {
        "model": "phi-4",
        "messages": [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": json.dumps(logs_data, default=str)}
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
    }
    
    llm_api_url = "http://localhost:1234/v1/chat/completions"
    
    try:
        response = requests.post(llm_api_url, json=payload)
        if response.status_code == 200:
            report_response = response.json()
            # Extract JSON block from the response (assume it's wrapped in triple backticks)
            content = report_response["choices"][0]["message"]["content"]
            match = re.search(r"\{(.|\n)*\}", content)
            if match:
                report_json_text = match.group(0).strip()
                report_data = json.loads(report_json_text)
                # Save the report to a file.
                report_filename = os.path.join(REPORTS_DIR, f"{today}_report.json")
                with open(report_filename, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, indent=2, default=str)
                logger.info(f"Daily report generated and saved to {report_filename}")
            else:
                logger.error("No JSON block found in LLM report response.")
        else:
            logger.error(f"LLM returned status code {response.status_code} for report generation")
    except Exception as e:
        logger.error("Error generating daily report: " + str(e))

# For debugging, schedule the report generation to run every minute.
scheduler = BackgroundScheduler()
scheduler.add_job(generate_daily_report, 'interval', minutes=1)
scheduler.start()

# The server's main loop will keep the scheduler alive.
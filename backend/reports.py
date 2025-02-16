import os
import json
import logging
import yaml
from datetime import datetime, timedelta, date
from models import SessionLocal, ActivityLog, Settings
from config import get_categories_json
from fastapi import APIRouter, Query, HTTPException
import httpx

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Setup reports directory
base_dir = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(base_dir, "..", "reports", "daily")
os.makedirs(REPORTS_DIR, exist_ok=True)
logger.info(f"Reports directory set to: {os.path.abspath(REPORTS_DIR)}")

router = APIRouter()

def extract_json_from_response(response: str) -> dict:
    """Extract and validate JSON from LLM response"""
    if response.startswith('```'):
        first_newline = response.find('\n')
        if first_newline != -1:
            last_marker = response.rfind('```')
            if last_marker != -1:
                response = response[first_newline + 1:last_marker].strip()
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        raise ValueError("Invalid JSON response from LLM")

async def call_llm_api(prompt: str) -> dict:
    """Direct LLM API call with improved error handling"""
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings:
            raise ValueError("Settings not configured")
            
        url = f"{settings.lmstudioEndpoint}/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": settings.lmstudioModel,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional activity report analyzer. Return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        logger.info(f"Calling LMStudio with model: {settings.lmstudioModel}")
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                try:

                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code != 200:
                        raise ValueError(f"LLM API error: {response.text}")
                    
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    return extract_json_from_response(content)
                except Exception as e:
                    logger.error(f"An error occurred: {e}")

                    
            except httpx.ReadTimeout:
                logger.error("LLM API timeout - try loading the model first")
                raise ValueError("LLM API timeout - ensure model is ready")
            except httpx.ConnectError:
                logger.error("Could not connect to LLM - check if it's running")
                raise ValueError("Could not connect to LLM - ensure it's running")
            except Exception as e:
                logger.error(f"Error during LLM API call: {str(e)}")
                raise ValueError(f"LLM API error: {str(e)}")
    finally:
        db.close()

def load_report_profile(profile_name: str) -> str:
    """Loads the YAML profile for a given report."""
    profile_path = os.path.join(base_dir, "..", "profiles", f"{profile_name}.yaml")
    if not os.path.exists(profile_path):
        logger.error(f"Profile {profile_name} not found at {profile_path}")
        return ""
    
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = yaml.safe_load(f)
    prompt_template = profile_data.get("prompt", "")
    categories_str = get_categories_json()
    return prompt_template.replace("{categories_json}", categories_str)

async def generate_daily_report_for_date(report_date, logs_data):
    profile_prompt = load_report_profile('ActivityReports_Daily')


    """Generates a daily report from actual logs using LLM."""
    logger.info(f"Generating report for {report_date} with {len(logs_data)} logs")
    logger.info("Entering generate_daily_report_for_date")
    
    if not logs_data:
        logger.warning("No activities found for this date")
        return {
            "executive_summary": {
                "total_time": 0,
                "time_by_group": {},
                "progress_report": "No activities recorded for this date."
            },
            "details": [],
            "markdown_report": "# Daily Report\n\nNo activities recorded for this date."
        }

    try:
        # Calculate actual totals
        total_time = sum(log["duration_minutes"] for log in logs_data)
        time_by_group = {}
        for log in logs_data:
            group = log.get("group", "Other")  # Provide a default value
            duration = log["duration_minutes"]
            time_by_group[group] = time_by_group.get(group, 0) + duration

        # Prepare prompt for LLM
        logs_json = json.dumps(logs_data, indent=2)
        prompt = f"{profile_prompt}\n\nReport Date: {report_date}\nTotal Time: {total_time}\nTime by Group: {json.dumps(time_by_group, indent=2)}\nActivities:\n{logs_json}"
        logger.info(f"Prompt being sent to LLM: {prompt}")
        logger.info("Calling LLM API...")
        llm_response = await call_llm_api(prompt)
        logger.info("LLM response received")
        logger.info(f"LLM response: {llm_response}")
        
        # Validate and return LLM response
        try:
            if isinstance(llm_response, dict):
                required_fields = ['executive_summary', 'details', 'markdown_report']
                if all(field in llm_response for field in required_fields):
                    logger.info("Valid LLM response received")
                    return llm_response
            
            logger.error("Invalid LLM response structure")
            raise ValueError("Invalid LLM response structure")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing or validating LLM response: {e}")
            raise

    except Exception as e:
        logger.error(f"Error in report generation: {str(e)}")
        logger.info(f"Exception details: {e}")
        logger.warning("Falling back to basic report structure")
        return {
            "executive_summary": {
                "total_time": total_time,
                "time_by_group": time_by_group,
                "progress_report": f"Basic report generated from {len(logs_data)} activities."
            },
            "details": logs_data,
            "markdown_report": f"# Daily Report\n\n**Total Time:** {total_time} minutes\n\n" + 
                             "**Time by Group:**\n" + 
                             "\n".join([f"- {k}: {v} minutes" for k, v in time_by_group.items()])
        }
         
@router.post("/force-daily-report")
async def force_daily_report(date_str: str = Query(..., alias="date")):
    """Force generates a report for a specific date using actual DB data."""
    logger.info(f"Entering force_daily_report with date: {date_str}")
    try:
        report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        logger.info(f"Force generating report for date: {report_date}")
        
        db = SessionLocal()
        try:
            # Steps 1-3 remain the same...
            start_date = datetime.combine(report_date, datetime.min.time())
            end_date = start_date + timedelta(days=1)
            logger.info(f"Query range: start={start_date.isoformat()}, end={end_date.isoformat()}")

            query = db.query(ActivityLog).filter(
                ActivityLog.timestamp >= start_date,
                ActivityLog.timestamp < end_date
            )
            activities = query.all()
            
            logs_data = [
                {
                    "group": activity.group,
                    "timestamp": activity.timestamp.isoformat(),
                    "duration_minutes": activity.duration_minutes,
                    "description": activity.description or ""
                }
                for activity in activities
            ]
            
        finally:
            db.close()

        # Step 4: Generate Report - Add await here
        logger.info(f"Generating report with {len(logs_data)} activities")
        report_data = await generate_daily_report_for_date(report_date, logs_data)

        if not report_data:
            raise ValueError("Failed to generate report data")

        # Step 5: Save Report
        report_filename = os.path.join(
            REPORTS_DIR, 
            f"{report_date.strftime('%Y-%m-%d')}_report.json"
        )
        
        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        return {
            "message": f"Daily report for {report_date} generated successfully.",
            "report": report_data,
            "debug_info": {
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "activities_found": len(logs_data),
                "report_file": report_filename
            }
        }
        
    except ValueError as e:
        logger.error(f"Value error in force_daily_report: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in force_daily_report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/daily-report")
async def get_daily_report(requested_date: str = Query(None, alias="date")):
    """Fetches an existing report for the given date."""
    try:
        report_date = datetime.strptime(requested_date, "%Y-%m-%d").date() if requested_date else date.today()
        
        report_filename = os.path.join(REPORTS_DIR, f"{report_date.strftime('%Y-%m-%d')}_report.json")
        logger.info(f"Looking for report file: {report_filename}")
        
        if os.path.exists(report_filename):
            with open(report_filename, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            logger.warning(f"Report not found: {report_filename}")
            return {"message": f"No report found for {report_date}"}
            
    except Exception as e:
        logger.error(f"Error in get_daily_report: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/debug-reports")
async def debug_reports():
    """Debug endpoint to check reports directory setup."""
    try:
        return {
            "reports_dir": REPORTS_DIR,
            "exists": os.path.exists(REPORTS_DIR),
            "absolute_path": os.path.abspath(REPORTS_DIR),
            "files": os.listdir(REPORTS_DIR),
            "working_dir": os.getcwd()
        }
    except Exception as e:
        return {"error": str(e)}
    
@router.get("/debug-activities")
async def debug_activities(date: str = Query(...)):
    """Debug endpoint to check activities in database for a specific date."""
    try:
        report_date = datetime.strptime(date, "%Y-%m-%d").date()
        start_date = datetime.combine(report_date, datetime.min.time())
        end_date = start_date + timedelta(days=1)
        
        db = SessionLocal()
        try:
            activities = db.query(ActivityLog).filter(
                ActivityLog.timestamp >= start_date,
                ActivityLog.timestamp < end_date
            ).all()
            
            return {
                "date": date,
                "activities": [
                    {
                        "id": activity.id,
                        "group": activity.group,
                        "timestamp": activity.timestamp.isoformat(),
                        "duration_minutes": activity.duration_minutes,
                        "description": activity.description
                    }
                    for activity in activities
                ]
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in debug_activities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/debug-llm")
async def debug_llm():
    """Debug endpoint to test LLM connectivity."""
    try:
        db = SessionLocal()
        try:
            settings = db.query(Settings).first()
            if not settings:
                raise ValueError("LLM settings not configured")

            test_prompt = "Generate a short test response to verify connectivity."
            response = await call_llm_api(test_prompt)
            return {
                "status": "success",
                "response": response,
                "provider_info": {
                    "type": "lmstudio",
                    "endpoint": settings.lmstudioEndpoint
                }
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
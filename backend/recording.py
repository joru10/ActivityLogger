# backend/recording.py
import os
import datetime
import uuid
from pathlib import Path
import logging
import requests
import json
import re
from pydantic import BaseModel, ValidationError, field_validator
from typing import List
import yaml
from models import SessionLocal, ActivityLog, Settings
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from llm_service import call_llm_api  # Now actually used below

router = APIRouter()
logger = logging.getLogger(__name__)

# Define a storage directory (relative to the project root)
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Define a Pydantic model for an activity log record.
class Activity(BaseModel):
    group: str
    category: str = "Other"  # Make category optional with a default value
    timestamp: str
    duration_minutes: int
    description: str
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v):
        """Validate that the timestamp is in a proper ISO format"""
        try:
            # Try to parse the timestamp
            datetime.datetime.fromisoformat(v.split('+')[0].strip())
            return v
        except (ValueError, TypeError) as e:
            # If it fails, generate a valid timestamp
            logger.warning(f"Invalid timestamp format '{v}', using current time instead")
            return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    @field_validator('duration_minutes')
    @classmethod
    def validate_duration(cls, v):
        """Ensure duration is a positive integer"""
        if not isinstance(v, int) or v <= 0:
            logger.warning(f"Invalid duration '{v}', using default of 30 minutes")
            return 30
        return v
    
    @field_validator('group')
    @classmethod
    def validate_group(cls, v):
        """Ensure group is not empty"""
        if not v or not v.strip():
            return "Other"
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        """Ensure description is not empty"""
        if not v or not v.strip():
            return "No description provided"
        return v

def save_activity_logs(activity_logs: list):
    """
    Saves a list of activity log records (dictionaries) into the database.
    """
    db = SessionLocal()
    try:
        for record in activity_logs:
            new_log = ActivityLog(
                group=record.get("group", "others"),
                category=record.get("category", "others"),
                timestamp=datetime.datetime.fromisoformat(record.get("timestamp").split('+')[0].strip()),
                duration_minutes=record.get("duration_minutes", 15),
                description=record.get("description", "")
            )
            db.add(new_log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving activity logs: {e}")
    finally:
        db.close()

def get_today_directory() -> Path:
    """Returns a Path object for today's directory, creating it if necessary."""
    today_str = datetime.date.today().isoformat()
    day_dir = STORAGE_DIR / today_str
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir

@router.post("/start")
async def start_recording():
    """
    Initiates a recording session.
    In a real scenario, the frontend would control the recording.
    Here, we simply generate and return a session ID.
    """
    session_id = str(uuid.uuid4())
    logger.info(f"Recording session {session_id} started.")
    return {"session_id": session_id}

@router.post("/stop")
async def stop_recording(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    Ends a recording session.
    Expects a WAV file upload and a session_id.
    The file is saved, then processed:
      1. Transcribe the audio using OpenAI Whisper.
      2. Save the transcript.
      3. Process the transcript with an LLM provider using the ActivityLogs profile.
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    
    # Save the uploaded WAV file
    day_dir = get_today_directory()
    wav_filename = f"recording_{session_id}.wav"
    wav_path = day_dir / wav_filename

    with wav_path.open("wb") as f:
        content = await file.read()
        f.write(content)
    logger.info(f"Recording saved to {wav_path}")

    # Get the file's modification time as the recording timestamp.
    file_mod_time = os.path.getmtime(wav_path)
    file_dt = datetime.datetime.fromtimestamp(file_mod_time)
    formatted_date = file_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # e.g., "2025-02-12 15:41:23.123"

    # Transcribe the audio using Whisper (replace simulation with a real transcription)
    transcript = transcribe_audio(wav_path)
    transcript_filename = f"recording_{session_id}.txt"
    transcript_path = day_dir / transcript_filename

    with transcript_path.open("w", encoding="utf-8") as f:
        f.write(transcript)
    logger.info(f"Transcript saved to {transcript_path}")

    # Load the ActivityLogs profile prompt.
    profile_prompt = load_profile("ActivityLogs")
    if not profile_prompt:
        logger.error("ActivityLogs profile could not be loaded.")
        return {"error": "ActivityLogs profile could not be loaded."}

    # Process the transcript with the LLM provider using the ActivityLogs profile.
    # Pass the transcript, formatted_date, and profile_prompt.
    llm_response = await process_transcript_with_llm(transcript, formatted_date, profile_prompt)

    # If the response contains an array of activity logs, save them to the database.
    if "error" not in llm_response and isinstance(llm_response, list):
        save_activity_logs(llm_response)
    else:
        logger.error("LLM response did not contain valid activity logs for saving.")

    return {
        "message": "Recording stopped and processed.",
        "llm_response": llm_response
    }

def transcribe_audio(wav_path: Path) -> str:
    """
    Transcribes the audio file using OpenAI Whisper (small model).
    Ensure that you have installed the whisper package and FFmpeg.
    """
    try:
        import whisper
    except ImportError:
        logger.error("Whisper module not found. Please install it (e.g., pip install git+https://github.com/openai/whisper.git).")
        return "Transcription error: whisper module not installed."

    logger.info(f"Transcribing audio file {wav_path} with Whisper model")
    model = whisper.load_model("small")
    result = model.transcribe(str(wav_path))
    transcript = result.get("text", "")
    logger.info("Transcription complete")
    return transcript

def load_profile(profile_name: str) -> str:
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        profile_path = os.path.join(base_dir, "..", "profiles", f"{profile_name}.yaml")
        if not os.path.exists(profile_path):
            logger.error(f"Profile {profile_name} not found at {profile_path}")
            raise HTTPException(status_code=500, detail=f"Profile {profile_name} not found")
            
        with open(profile_path, "r", encoding="utf-8") as f:
            try:
                profile_data = yaml.safe_load(f)
                if not profile_data or "prompt" not in profile_data:
                    raise HTTPException(status_code=500, detail="Invalid profile format")
                return profile_data["prompt"]
            except yaml.YAMLError as e:
                logger.error(f"YAML parsing error: {e}")
                raise HTTPException(status_code=500, detail="Invalid YAML format in profile")
    except Exception as e:
        logger.error(f"Error loading profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to load profile")

def remove_json_comments(json_str: str) -> str:
    """
    Remove C++ style inline comments (// ... ) from a JSON string.
    """
    return re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)

def generate_fallback_activity(transcript: str, recording_date: str) -> dict:
    """
    Generate a fallback activity log when the LLM fails to produce valid logs.
    Uses the transcript to create a basic activity entry.
    """
    logger.info("Generating fallback activity from transcript")
    
    # Get the current time for the timestamp
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    # Extract a summary from the transcript (first 50 chars or less)
    description = transcript[:200] + "..." if len(transcript) > 200 else transcript
    
    # Create a basic activity log
    fallback_activity = {
        "group": "Other",
        "category": "Other",
        "timestamp": current_time,
        "duration_minutes": 30,  # Default duration
        "description": f"Auto-generated from recording: {description}"
    }
    
    logger.info(f"Created fallback activity: {fallback_activity}")
    return fallback_activity

def validate_activity_logs(data: List[dict]) -> List[Activity]:
    """
    Validate a list of activity log records using the Activity Pydantic model.
    Handles validation errors gracefully by logging them and skipping invalid records.
    """
    activities = []
    for item in data:
        try:
            # Add missing category if not present
            if 'category' not in item:
                item['category'] = 'Other'
            
            # Validate and add the activity
            activities.append(Activity.model_validate(item))
        except ValidationError as e:
            logger.warning(f"Skipping invalid activity log: {item}. Error: {str(e)}")
            continue
    
    if not activities:
        logger.warning("No valid activity logs found after validation, creating a default activity")
        # Create a default activity that will definitely pass validation
        default_activity = Activity(
            group="Other",
            category="Other",
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            duration_minutes=30,
            description="Auto-generated default activity"
        )
        activities.append(default_activity)

    return activities

async def process_transcript_with_llm(transcript: str, recording_date: str, profile_prompt: str) -> dict:
    logger.info("Processing transcript with LLM provider using ActivityLogs profile")

    # Create a new session
    with SessionLocal() as db:
        settings = db.query(Settings).first()
        if not settings:
            logger.error("No settings found; cannot retrieve categories.")
            return {"error": "No settings configured"}

        # Get categories as JSON string from settings
        categories = settings.get_categories() or []

        # Construct the full prompt with recording date, categories, and transcript
        full_prompt = (
            f"{profile_prompt}\n\n"
            "AVAILABLE CATEGORY/GROUP STRUCTURE:\n"
            "\n".join(
                f"- {cat['name']}:\n  " + 
                "\n  ".join(f"* {group}" for group in cat.get('groups', []))
                for cat in categories
            ) + "\n\n"
            f"Recording Date: {recording_date}\n"
            "INSTRUCTIONS:\n"
            "1. Match activities to EXACT group names under their categories\n"
            "2. Use ONLY the provided group names\n\n"
            f"Transcript:\n{transcript}"
        )

        payload = {
            "model": settings.lmstudioModel or "phi-4",  # Use model from settings if available
            "messages": [
                {"role": "system", "content": full_prompt},
                {"role": "user", "content": transcript}
            ],
            "temperature": 0.7,
            "max_tokens": -1,
            "stream": False
        }

        llm_api_url = settings.lmstudioEndpoint.rstrip("/") + "/chat/completions" 
        logger.debug(f"Sending to LLM:\nPrompt: {full_prompt}\nTranscript: {transcript}")
        
        try:
            response = await call_llm_api(prompt=full_prompt)
            logger.info(f"LLM response type: {type(response)}")
            logger.debug(f"LLM raw response: {response}")
            
            # Handle different response formats
            if isinstance(response, dict):
                logger.info("LLM returned a dictionary response")
                
                # Handle OpenAI/LMStudio API format with choices
                if "choices" in response:
                    try:
                        content = response["choices"][0]["message"]["content"].strip()
                        logger.debug(f"Raw LLM content: {repr(content)}")

                        # Extract JSON from markdown code blocks if present
                        if '```' in content:
                            # Handle different markdown formats (```json, ```JSON, etc.)
                            pattern = r'```(?:json|JSON)?\s*([\s\S]*?)```'
                            matches = re.findall(pattern, content)
                            if matches:
                                content = matches[0].strip()
                                logger.debug(f"Extracted JSON content: {repr(content)}")
                            else:
                                logger.warning("Could not extract content from code blocks")
                        
                        # Handle case where LLM returns [] with explanatory text
                        if content.startswith('[') and ']' in content:
                            # Extract just the JSON array part
                            array_end = content.find(']') + 1
                            json_part = content[:array_end].strip()
                            logger.debug(f"Extracted array part: {repr(json_part)}")
                            
                            # If there's explanatory text, log it
                            if len(content) > array_end:
                                explanation = content[array_end:].strip()
                                logger.info(f"LLM provided explanation: {explanation}")
                                
                            content = json_part

                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, list):
                                # Check if the list is empty
                                if not parsed:
                                    logger.warning("LLM returned an empty list of logs, generating fallback activity")
                                    # Generate a fallback activity based on the transcript
                                    fallback_activity = generate_fallback_activity(transcript, recording_date)
                                    try:
                                        validated_logs = validate_activity_logs([fallback_activity])
                                        return [log.dict() for log in validated_logs]
                                    except Exception as e:
                                        logger.error(f"Error validating fallback activity: {str(e)}")
                                        # Create a very basic activity that will definitely pass validation
                                        basic_activity = {
                                            "group": "Other",
                                            "category": "Other",
                                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                                            "duration_minutes": 30,
                                            "description": "Auto-generated activity from recording"
                                        }
                                        return [basic_activity]
                                else:
                                    try:
                                        validated_logs = validate_activity_logs(parsed)
                                        return [log.dict() for log in validated_logs]
                                    except Exception as e:
                                        logger.error(f"Error validating parsed logs: {str(e)}")
                                        # Generate a fallback activity
                                        fallback_activity = generate_fallback_activity(transcript, recording_date)
                                        try:
                                            validated_logs = validate_activity_logs([fallback_activity])
                                            return [log.dict() for log in validated_logs]
                                        except Exception as e2:
                                            logger.error(f"Error validating fallback activity: {str(e2)}")
                                            # Create a very basic activity that will definitely pass validation
                                            basic_activity = {
                                                "group": "Other",
                                                "category": "Other",
                                                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                                                "duration_minutes": 30,
                                                "description": "Auto-generated activity from recording"
                                            }
                                            return [basic_activity]
                            else:
                                logger.error(f"Expected a list of logs but got: {type(parsed)}")
                                return {"error": "LLM did not return a list of activity logs"}
                        except json.JSONDecodeError as e:
                            logger.error(f"JSONDecodeError: {e}")
                            logger.error(f"Failed to parse LLM content as JSON: {repr(content)}")
                            logger.warning("Using fallback activity generation due to JSON parsing error")
                            fallback_activity = generate_fallback_activity(transcript, recording_date)
                            validated_logs = validate_activity_logs([fallback_activity])
                            return [log.dict() for log in validated_logs]
                    except Exception as e:
                        logger.error(f"Error parsing LLM content: {str(e)}")
                        logger.warning("Using fallback activity generation due to general error")
                        fallback_activity = generate_fallback_activity(transcript, recording_date)
                        validated_logs = validate_activity_logs([fallback_activity])
                        return [log.dict() for log in validated_logs]
                
                # Handle direct JSON response
                elif "error" in response:
                    logger.error(f"LLM returned an error: {response['error']}")
                    return response
                else:
                    logger.warning(f"Unexpected dictionary format: {list(response.keys())}")
                    return {"error": "Unexpected LLM response format"}
            
            # Handle list response (already parsed JSON)
            elif isinstance(response, list):
                logger.info("LLM returned a list response")
                try:
                    validated_logs = validate_activity_logs(response)
                    return [log.dict() for log in validated_logs]
                except Exception as e:
                    logger.error(f"Error validating activity logs: {str(e)}")
                    return {"error": f"Error validating activity logs: {str(e)}"}
            
            # Handle other response types
            else:
                logger.error(f"Unexpected response type: {type(response)}")
                return {"error": f"Unexpected response type: {type(response)}"}
        except Exception as e:
            logger.error("Error calling LLM: " + str(e))
            return {"error": str(e)}
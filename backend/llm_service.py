import json
import logging
import httpx
from models import SessionLocal, Settings

logger = logging.getLogger(__name__)

async def call_llm_api(prompt: str) -> dict:
    """Call LLM API and return parsed JSON response"""
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
        
        logger.info(f"Calling LLStudio with model: {settings.lmstudioModel}")
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise ValueError(f"LLM API error: {response.text}")
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            return extract_json_from_response(content)
            
    except Exception as e:
        logger.error(f"LLM API call failed: {str(e)}")
        raise
    finally:
        db.close()

def extract_json_from_response(response: str) -> dict:
    """Extract and validate JSON from LLM response"""
    if response.startswith('```'):
        first_newline = response.find('\n')
        if first_newline != -1:
            last_marker = response.rfind('```')
            if last_marker != -1:
                response = response[first_newline + 1:last_marker].strip()
    
    try:
        json_data = json.loads(response)
        validate_response_structure(json_data)
        return json_data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        raise ValueError("Invalid JSON response from LLM")

def validate_response_structure(data: dict) -> None:
    """Validate the structure of the LLM response"""
    required_fields = ['executive_summary', 'details', 'markdown_report']
    missing_fields = [f for f in required_fields if f not in data]
    if missing_fields:
        raise ValueError(f"Missing required fields in LLM response: {missing_fields}")
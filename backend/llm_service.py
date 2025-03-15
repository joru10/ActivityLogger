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
    # Handle various thinking/reasoning tags
    # Define a list of known thinking tags patterns
    thinking_patterns = [
        ('<reasoning>', '</reasoning>'),
        ('<think>', '</think>'),
        ('<thinking>', '</thinking>'),
        ('<rationale>', '</rationale>'),
        ('<analysis>', '</analysis>'),
        ('<reflection>', '</reflection>'),
        ('<thought>', '</thought>'),
        ('<internal>', '</internal>'),
        ('<deliberation>', '</deliberation>')
    ]
    
    # Check for and remove content within thinking tags
    for start_tag, end_tag in thinking_patterns:
        if start_tag in response and end_tag in response:
            logger.info(f"Detected {start_tag} tags in LLM response, removing this section")
            try:
                # Extract content after the end tag
                response = response.split(end_tag)[-1].strip()
            except Exception as e:
                logger.warning(f"Error removing {start_tag} section: {e}")
    
    # Handle markdown code blocks
    if '```json' in response or '```' in response:
        # Extract content between code block markers
        try:
            if '```json' in response:
                # Extract content between ```json and ```
                response = response.split('```json')[-1].split('```')[0].strip()
            elif response.startswith('```') and response.endswith('```'):
                # Remove the first and last ``` markers
                response = response[3:-3].strip()
            elif '```' in response:
                # Find the first and last ``` markers
                first_marker = response.find('```')
                last_marker = response.rfind('```')
                if first_marker != -1 and last_marker != -1 and first_marker != last_marker:
                    # Extract content between the markers
                    first_newline = response.find('\n', first_marker)
                    if first_newline != -1:
                        response = response[first_newline + 1:last_marker].strip()
        except Exception as e:
            logger.warning(f"Error extracting JSON from code blocks: {e}")
    
    # Remove various trailing content markers
    trailing_markers = ['<sep>', '<end>', '<eos>', '<stop>']
    for marker in trailing_markers:
        if marker in response:
            logger.info(f"Detected {marker} tag in LLM response, removing trailing content")
            try:
                response = response.split(marker)[0].strip()
            except Exception as e:
                logger.warning(f"Error removing {marker} section: {e}")
    
    # Try to parse the JSON
    try:
        json_data = json.loads(response)
        validate_response_structure(json_data)
        return json_data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        logger.error(f"Raw response: {response}")
        raise ValueError("Invalid JSON response from LLM")

def validate_response_structure(data) -> None:
    """Validate the structure of the LLM response"""
    # If it's a list, assume it's a list of activity logs
    if isinstance(data, list):
        if len(data) == 0:
            logger.warning("Empty activity log list returned from LLM")
        return
        
    # If it's a report format with specific fields
    if isinstance(data, dict):
        required_fields = ['executive_summary', 'details', 'markdown_report']
        if any(field in data for field in required_fields):
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                logger.warning(f"Missing some report fields in LLM response: {missing_fields}")
        return
        
    # If we got here, it's neither a list nor a recognized dict format
    logger.warning(f"Unexpected response format from LLM: {type(data)}")
import json
import logging
import httpx
import re
from models import SessionLocal, Settings

logger = logging.getLogger(__name__)

async def call_llm_api(prompt: str, max_retries: int = 3) -> dict:
    """Call LLM API and return parsed JSON response with improved retry logic"""
    db = SessionLocal()
    retry_count = 0
    last_error = None
    
    try:
        settings = db.query(Settings).first()
        if not settings:
            logger.error("LLM API call failed: Settings not configured")
            raise ValueError("Settings not configured")
            
        # Ensure the endpoint has the correct format
        endpoint = settings.lmstudioEndpoint.rstrip('/')
        url = f"{endpoint}/chat/completions"
        headers = {"Content-Type": "application/json"}
        
        logger.debug(f"LLM API URL: {url}")
        
        # Loop for retries
        while retry_count <= max_retries:
            try:
                # Use a stronger system prompt to ensure JSON-only responses
                payload = {
                    "model": settings.lmstudioModel or "phi-4",  # Fallback to phi-4 if not set
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a professional activity report analyzer. Extract activities from user input and return them as valid JSON. IMPORTANT: Your response must ONLY contain valid JSON without any explanations, reasoning, or additional text. Do not include markdown code blocks, thinking tags, or any other non-JSON content."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "stream": False,
                    "temperature": 0.3,  # Lower temperature for more consistent outputs
                    "max_tokens": 4000   # Increased token limit for complex reports
                }
                
                logger.info(f"Calling LLStudio with model: {settings.lmstudioModel} (attempt {retry_count + 1}/{max_retries + 1})")
                logger.debug(f"Prompt length: {len(prompt)} characters")
                
                # Increased timeout for longer generations
                async with httpx.AsyncClient(timeout=300.0) as client:
                    logger.debug("Sending request to LLM API...")
                    response = await client.post(url, json=payload, headers=headers)
                    
                    if response.status_code != 200:
                        error_msg = f"LLM API error (HTTP {response.status_code}): {response.text}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                    
                    logger.debug("Received response from LLM API")
                    result = response.json()
                    
                    if 'choices' not in result or len(result['choices']) == 0:
                        raise ValueError(f"Invalid response format from LLM API: {result}")
                        
                    content = result['choices'][0]['message']['content']
                    logger.debug(f"Raw LLM response: {content[:200]}...")
                    
                    # Try to extract JSON
                    try:
                        json_result = extract_json_from_response(content)
                        logger.info("Successfully extracted JSON from LLM response")
                        return json_result
                    except ValueError as e:
                        last_error = e
                        logger.warning(f"Failed to extract JSON on attempt {retry_count + 1}: {str(e)}")
                        # Only retry if we haven't reached max_retries
                        if retry_count < max_retries:
                            retry_count += 1
                            continue
                        else:
                            raise
            except Exception as e:
                last_error = e
                logger.warning(f"Error on attempt {retry_count + 1}: {str(e)}")
                if retry_count < max_retries:
                    retry_count += 1
                    continue
                else:
                    raise
                    
        # If we get here, all retries failed
        raise ValueError(f"All {max_retries + 1} attempts failed: {str(last_error)}")
            
    except Exception as e:
        logger.error(f"LLM API call failed: {str(e)}")
        raise
    finally:
        db.close()

def extract_json_from_response(response: str) -> dict:
    """Extract and validate JSON from LLM response with enhanced error handling"""
    original_response = response  # Keep a copy of the original for debugging
    logger.debug(f"Original response length: {len(original_response)} characters")
    
    # Handle empty or None responses
    if not response or response.isspace():
        logger.error("Empty or whitespace-only response received from LLM")
        raise ValueError("Empty response from LLM")
    
    # Handle various thinking/reasoning tags
    # Define a comprehensive list of known thinking tags patterns
    thinking_patterns = [
        ('<reasoning>', '</reasoning>'),
        ('<think>', '</think>'),
        ('<thinking>', '</thinking>'),
        ('<rationale>', '</rationale>'),
        ('<analysis>', '</analysis>'),
        ('<reflection>', '</reflection>'),
        ('<thought>', '</thought>'),
        ('<thoughts>', '</thoughts>'),
        ('<internal>', '</internal>'),
        ('<deliberation>', '</deliberation>'),
        ('<explanation>', '</explanation>'),
        ('<note>', '</note>'),
        ('<notes>', '</notes>'),
        ('<comment>', '</comment>'),
        ('<comments>', '</comments>')
    ]
    
    # Check for and remove content within thinking tags
    for start_tag, end_tag in thinking_patterns:
        if start_tag in response:
            logger.info(f"Detected {start_tag} tag in LLM response")
            try:
                if end_tag in response:
                    # Extract content after the end tag
                    parts = response.split(end_tag, 1)
                    if len(parts) > 1:
                        response = parts[1].strip()
                        logger.info(f"Successfully removed content between {start_tag} and {end_tag}")
                else:
                    # If we have an opening tag but no closing tag, try to extract content after the tag
                    logger.warning(f"Found opening {start_tag} but no closing {end_tag} - attempting to extract JSON after tag")
                    parts = response.split(start_tag, 1)
                    if len(parts) > 1:
                        # Try to find JSON after the tag
                        response = parts[1].strip()
                        logger.info(f"Extracted content after {start_tag} tag")
            except Exception as e:
                logger.warning(f"Error processing {start_tag} section: {e}")
    
    # Handle markdown code blocks with various language specifiers
    code_block_markers = ['```json', '```JSON', '```javascript', '```js', '```']
    for marker in code_block_markers:
        if marker in response:
            try:
                parts = response.split(marker, 1)
                if len(parts) > 1:
                    after_marker = parts[1]
                    # Find the closing code block
                    if '```' in after_marker:
                        content = after_marker.split('```', 1)[0].strip()
                        logger.info(f"Extracted content from code block with marker {marker}")
                        response = content
                        break
                    else:
                        # No closing marker, use everything after the opening marker
                        response = after_marker.strip()
                        logger.warning(f"No closing ``` found after {marker}, using all content after marker")
                        break
            except Exception as e:
                logger.warning(f"Error extracting content from code block with marker {marker}: {e}")
    
    # Remove various trailing content markers
    trailing_markers = ['<sep>', '<end>', '<eos>', '<stop>', 'human:', ' <sep> human:', '<sep> human:', 
                       'assistant:', 'user:', '```', '</answer>', '</response>']
    for marker in trailing_markers:
        if marker in response:
            try:
                parts = response.split(marker, 1)
                if len(parts) > 1:
                    response = parts[0].strip()
                    logger.info(f"Removed trailing content after marker {marker}")
            except Exception as e:
                logger.warning(f"Error removing content after marker {marker}: {e}")
    
    # Try to extract array JSON if the response contains an array
    if '[' in response and ']' in response:
        try:
            start_idx = response.find('[')
            end_idx = response.rfind(']')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                potential_json = response[start_idx:end_idx+1]
                try:
                    json_data = json.loads(potential_json)
                    if isinstance(json_data, list):
                        logger.info(f"Successfully extracted JSON array with {len(json_data)} items")
                        validate_response_structure(json_data)
                        return json_data
                except json.JSONDecodeError:
                    # If array extraction fails, continue with other methods
                    logger.warning("Failed to extract JSON array, trying other methods")
        except Exception as e:
            logger.warning(f"Error during JSON array extraction: {e}")
    
    # Try to extract object JSON if the response contains an object
    if '{' in response and '}' in response:
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                potential_json = response[start_idx:end_idx+1]
                try:
                    json_data = json.loads(potential_json)
                    logger.info("Successfully extracted JSON object using pattern matching")
                    validate_response_structure(json_data)
                    return json_data
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse extracted JSON object: {e}")
                    # Try to fix common JSON issues
                    fixed_json = fix_common_json_errors(potential_json)
                    if fixed_json != potential_json:
                        try:
                            json_data = json.loads(fixed_json)
                            logger.info("Successfully parsed JSON after fixing common errors")
                            validate_response_structure(json_data)
                            return json_data
                        except json.JSONDecodeError:
                            # If that still fails, continue with the full response
                            logger.warning("Failed to parse JSON even after fixing common errors")
        except Exception as e:
            logger.warning(f"Error during JSON object extraction: {e}")
    
    # Try to parse the entire response as JSON
    try:
        json_data = json.loads(response)
        logger.info(f"Successfully parsed entire response as JSON of type {type(json_data)}")
        validate_response_structure(json_data)
        return json_data
    except json.JSONDecodeError as e:
        # Try to fix common JSON errors in the entire response
        fixed_response = fix_common_json_errors(response)
        if fixed_response != response:
            try:
                json_data = json.loads(fixed_response)
                logger.info("Successfully parsed JSON after fixing common errors in full response")
                validate_response_structure(json_data)
                return json_data
            except json.JSONDecodeError as e2:
                logger.error(f"Failed to parse fixed JSON: {e2}")
        
        # If all attempts fail, log detailed error information
        logger.error(f"Failed to parse JSON: {e}")
        logger.error(f"Processed response: {response[:200]}...")
        logger.error(f"Original response: {original_response[:200]}...")
        raise ValueError(f"Invalid JSON response from LLM: {str(e)}")


def fix_common_json_errors(json_str: str) -> str:
    """Fix common JSON formatting errors"""
    # Replace single quotes with double quotes (but not inside already quoted strings)
    # This is a simplified approach and may not work for all cases
    fixed = ""
    in_string = False
    in_escape = False
    
    for char in json_str:
        if char == '\\' and not in_escape:
            in_escape = True
            fixed += char
        elif in_escape:
            in_escape = False
            fixed += char
        elif char == '"' and not in_escape:
            in_string = not in_string
            fixed += char
        elif char == "'" and not in_string:
            fixed += '"'
        else:
            fixed += char
    
    # Fix trailing commas in arrays and objects
    fixed = fixed.replace(",]", "]")
    fixed = fixed.replace(",}", "}")
    
    # Fix missing quotes around keys
    # This is a simplified approach that won't work for all cases
    fixed = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', fixed)
    
    return fixed

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
import json
import logging
import httpx
import re
from datetime import datetime
from typing import Optional
from .models import SessionLocal, Settings

logger = logging.getLogger(__name__)

async def call_llm_api(prompt: str, max_retries: int = 3, model_type: str = "logs") -> dict:
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
                # Determine which model to use based on the model_type
                if model_type == "logs":
                    model_name = settings.lmstudioLogsModel or settings.lmstudioModel or "phi-3-mini-4k"
                elif model_type == "reports":
                    model_name = settings.lmstudioReportsModel or settings.lmstudioModel or "gemma-7b"
                else:
                    model_name = settings.lmstudioModel or "phi-4"

                logger.info(f"Using model {model_name} for {model_type}")

                # Use a stronger system prompt to ensure JSON-only responses
                payload = {
                    "model": model_name,
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

                logger.info(f"Calling LLStudio with model: {model_name} (attempt {retry_count + 1}/{max_retries + 1})")
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

# Refactored extract_json_from_response with state machine approach
def extract_json_from_response(response: str) -> dict:
    """Extract and validate JSON from LLM response with enhanced error handling"""
    original_response = response
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
    if '[' in response:
        try:
            start_idx = response.find('[')
            # First try with closing bracket if it exists
            if ']' in response:
                end_idx = response.rfind(']')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    potential_json = response[start_idx:end_idx+1]
                    try:
                        json_data = json.loads(potential_json)
                        if isinstance(json_data, list):
                            logger.info(f"Successfully extracted JSON array with {len(json_data)} items")
                            validate_response_structure(json_data)
                            return json_data
                    except json.JSONDecodeError as e:
                        # If array extraction fails, try fixing it
                        logger.warning(f"Failed to extract JSON array: {e}, attempting to fix")
                        fixed_json = fix_common_json_errors(potential_json)
                        if fixed_json != potential_json:
                            try:
                                json_data = json.loads(fixed_json)
                                if isinstance(json_data, list):
                                    logger.info(f"Successfully extracted fixed JSON array with {len(json_data)} items")
                                    validate_response_structure(json_data)
                                    return json_data
                            except json.JSONDecodeError as e2:
                                logger.warning(f"Failed to extract JSON array even after fixing: {e2}, trying other methods")

                                # Special handling for arrays with multiple items but missing commas
                                # This is a common issue with LLMs
                                try:
                                    # Try to manually extract individual items
                                    items = []
                                    item_start = potential_json.find('{')
                                    while item_start != -1:
                                        item_end = potential_json.find('}', item_start)
                                        if item_end == -1:
                                            break
                                        item_json = potential_json[item_start:item_end+1]
                                        try:
                                            # Try to parse each item individually
                                            item_data = json.loads(item_json)
                                            items.append(item_data)
                                            logger.info(f"Successfully extracted individual item: {item_json[:30]}...")
                                        except json.JSONDecodeError:
                                            # Try to fix this individual item
                                            fixed_item = fix_common_json_errors(item_json)
                                            try:
                                                item_data = json.loads(fixed_item)
                                                items.append(item_data)
                                                logger.info(f"Successfully extracted fixed individual item: {fixed_item[:30]}...")
                                            except json.JSONDecodeError:
                                                logger.warning(f"Failed to parse individual item: {item_json[:30]}...")

                                        # Move to next item
                                        item_start = potential_json.find('{', item_end + 1)

                                    if items:
                                        logger.info(f"Successfully extracted {len(items)} individual items from malformed array")
                                        validate_response_structure(items)
                                        return items
                                except Exception as e3:
                                    logger.warning(f"Failed to extract individual items: {e3}")

            # If no closing bracket or extraction failed, try to extract from start to end
            # and let the fix_common_json_errors function handle the missing brackets
            potential_json = response[start_idx:]
            fixed_json = fix_common_json_errors(potential_json)
            try:
                json_data = json.loads(fixed_json)
                if isinstance(json_data, list):
                    logger.info(f"Successfully extracted incomplete JSON array with {len(json_data)} items after fixing")
                    validate_response_structure(json_data)
                    return json_data
            except json.JSONDecodeError as e:
                # If that still fails, try to extract individual items
                logger.warning(f"Failed to extract incomplete JSON array: {e}, trying to extract individual items")
                try:
                    # Try to manually extract individual items
                    items = []
                    item_start = potential_json.find('{')
                    while item_start != -1:
                        item_end = potential_json.find('}', item_start)
                        if item_end == -1:
                            break
                        item_json = potential_json[item_start:item_end+1]
                        try:
                            # Try to parse each item individually
                            item_data = json.loads(item_json)
                            items.append(item_data)
                            logger.info(f"Successfully extracted individual item: {item_json[:30]}...")
                        except json.JSONDecodeError:
                            # Try to fix this individual item
                            fixed_item = fix_common_json_errors(item_json)
                            try:
                                item_data = json.loads(fixed_item)
                                items.append(item_data)
                                logger.info(f"Successfully extracted fixed individual item: {fixed_item[:30]}...")
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse individual item: {item_json[:30]}...")

                        # Move to next item
                        item_start = potential_json.find('{', item_end + 1)

                    if items:
                        logger.info(f"Successfully extracted {len(items)} individual items from malformed array")
                        validate_response_structure(items)
                        return items
                except Exception as e2:
                    logger.warning(f"Failed to extract individual items: {e2}, trying other methods")
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
                    validate_response_structure(json_data)
                    return json_data
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse extracted JSON object: {e}")
                    raise
                except Exception as e:
                    logger.warning(f"Error during JSON object extraction: {e}")
                    raise
        except Exception as e:
            logger.warning(f"Error during JSON object extraction: {e}")
            raise

    # If we get here, no valid JSON was found
    logger.error("No valid JSON found in response")
    raise ValueError("No valid JSON found in response")


class JSONRecoveryError(Exception):
    """Custom exception for JSON recovery failures"""
    pass


class JSONParser:
    """Class-based JSON parser with systematic error recovery"""

    def __init__(self, json_str: str):
        self.json_str = json_str
        self.fixed = json_str
        self._original = json_str

    def fix_unquoted_keys(self):
        """Fix JSON keys that need quotes"""
        self.fixed = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', self.fixed)

    def fix_trailing_commas(self):
        """Fix trailing commas in JSON arrays and objects"""
        self.fixed = self.fixed.replace(",]", "]")
        self.fixed = self.fixed.replace(",}", "}")

    def fix_incomplete_structures(self):
        """Fix imbalanced JSON structures"""
        open_curly = self.fixed.count('{')
        close_curly = self.fixed.count('}')
        open_square = self.fixed.count('[')
        close_square = self.fixed.count(']')

        if open_curly > close_curly:
            self.fixed += '}' * (open_curly - close_curly)

        if open_square > close_square:
            self.fixed += ']' * (open_square - close_square)

    def fix_unescaped_quotes(self):
        """Fix unescaped quotes in JSON strings"""
        # Replace single quotes with double quotes outside strings
        in_string = False
        in_escape = False
        result = ""

        for char in self.fixed:
            if char == '\\' and not in_escape:
                in_escape = True
                result += char
            elif in_escape:
                in_escape = False
                result += char
            elif char == '"' and not in_escape:
                in_string = not in_string
                result += char
            elif char == "'" and not in_string:
                result += '"'
            else:
                result += char

        self.fixed = result

    def fix_incomplete_values(self):
        """Fix incomplete values like "duration_minutes": )"""
        self.fixed = re.sub(r'"duration_minutes"\s*:\s*\)', '"duration_minutes": 30', self.fixed)

    def validate(self) -> bool:
        """Validate the fixed JSON"""
        try:
            json.loads(self.fixed)
            return True
        except json.JSONDecodeError:
            return False

    def get_fixed_json(self) -> str:
        """Get the fixed JSON string"""
        return self.fixed


def extract_json_array(response: str) -> Optional[dict]:
    """Extract JSON array from response"""
    start_idx = response.find('[')
    if start_idx != -1:
        try:
            return json.loads(response[start_idx:response.rfind(']')+1])
        except json.JSONDecodeError:
            pass
    return None


def extract_json_object(response: str) -> Optional[dict]:
    """Extract JSON object from response"""
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return None


def extract_from_code_blocks(response: str) -> Optional[dict]:
    """Extract JSON from code blocks in response"""
    if code_block_match := re.search(r'```json\n(.*?)\n```', response, re.DOTALL):
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def attempt_full_json_parse(response: str) -> dict:
    """Attempt full JSON parsing with error recovery"""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.warning(f"Basic JSON parsing failed: {e}")
        fixed_json = fix_common_json_errors(response)
        return json.loads(fixed_json)


def fix_common_json_errors(json_str: str) -> str:
    """Systematically fix common JSON errors using structured parsing"""
    parser = JSONParser(json_str)

    # Apply systematic fixes
    parser.fix_unquoted_keys()
    parser.fix_trailing_commas()
    parser.fix_incomplete_structures()
    parser.fix_unescaped_quotes()
    parser.fix_incomplete_values()

    # Validate fixed JSON
    if parser.validate():
        return parser.get_fixed_json()
    else:
        raise JSONRecoveryError("Failed to fix JSON structure")

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
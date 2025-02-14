import asyncio
import json
import logging
import httpx
from models import SessionLocal, Settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def call_llm_api(prompt: str):
    """Direct LLM API call for testing"""
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
                    "content": "You are a professional activity report analyzer."
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
        
        logger.info(f"Calling LMStudio at: {url} with model: {settings.lmstudioModel}")
        # Increase timeout to 120 seconds
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    raise ValueError(f"LLM API error: {response.text}")
                
                result = response.json()
                content = result['choices'][0]['message']['content']
                logger.info("LLM response received successfully")
                return content
                
            except httpx.ReadTimeout:
                logger.error("LMStudio API timeout - try loading the model first in LMStudio UI")
                raise ValueError("LMStudio API timeout - ensure model is loaded and ready")
            except httpx.ConnectError:
                logger.error("Could not connect to LMStudio - check if it's running")
                raise ValueError("Could not connect to LMStudio - ensure it's running")
    finally:
        db.close()

# ...existing imports and logging setup...

def extract_json_from_response(response: str) -> dict:
    """Extract JSON from a response that might be wrapped in markdown code blocks"""
    # Remove markdown code block markers if present
    if response.startswith('```'):
        # Find the end of the first line and start after it
        first_newline = response.find('\n')
        if first_newline != -1:
            # Find the last ``` and exclude it
            last_marker = response.rfind('```')
            if last_marker != -1:
                response = response[first_newline + 1:last_marker].strip()
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        logger.debug(f"Attempted to parse: {response}")
        raise

async def test_llm_connection():
    """Test the LLM connection with a sample prompt"""
    success = False
    try:
        logger.info("Testing LMStudio connection...")
        
        # Update system prompt to be more specific about JSON
        test_prompt = """You are a JSON-only response generator. Generate a valid JSON response with this structure:
        {
            "executive_summary": {
                "total_time": 15,
                "time_by_group": {"others": 15},
                "progress_report": "string"
            },
            "details": [],
            "markdown_report": "string"
        }
        Response must be pure JSON without markdown or explanations."""
        
        logger.info("\nCalling LLM API...")
        response = await call_llm_api(test_prompt)
        logger.info("\nLLM Response received:")
        
        try:
            json_data = extract_json_from_response(response)
            # Validate required fields
            required_fields = ['executive_summary', 'details', 'markdown_report']
            missing_fields = [f for f in required_fields if f not in json_data]
            
            if missing_fields:
                logger.error(f"Missing required fields: {missing_fields}")
                success = False
            else:
                logger.info("All required fields present")
                logger.info("Parsed JSON response:")
                logger.info(json.dumps(json_data, indent=2))
                success = True
        except json.JSONDecodeError:
            logger.error("Failed to parse response as JSON")
            logger.info("Raw response:")
            logger.info(response)
            success = False
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        success = False
    finally:
        if success:
            logger.info("✅ Test completed successfully!")
            logger.info("JSON structure is valid and complete")
        else:
            logger.error("❌ Test failed!")
            logger.error("Check the logs above for details")

if __name__ == "__main__":
    asyncio.run(test_llm_connection())
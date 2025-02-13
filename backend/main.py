# backend/main.py
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from recording import router as recording_router
from api import router as api_router  # Import the router from api.py
from reports_api import router as reports_router
import reports  # This will run the code in reports.py, starting the scheduler.

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="ActivityLogger API")

# Add CORS middleware to allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow requests from your React app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the recording router
app.include_router(recording_router, prefix="/api/recording")
app.include_router(api_router, prefix="/api")
app.include_router(reports_router, prefix="/api")  

@app.get("/")
async def root():
    return {"message": "ActivityLogger API is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
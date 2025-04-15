# backend/main.py
import logging
import sys
import os

# Add the parent directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import recording
import api  # Import the router from api.py
import reports
import custom_reports
import scheduler  # Import the scheduler module
from scheduler import start_scheduler

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.info(f"Python version: {sys.version}")

# Import report fix middleware to ensure all reports have valid HTML content
try:
    import report_fix_middleware
    logger.info("Report fix middleware loaded successfully")
except Exception as e:
    logger.error(f"Error loading report fix middleware: {e}")

app = FastAPI(title="ActivityLogger API")

# Add CORS middleware to allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow requests from your React app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include the recording router
app.include_router(recording.router, prefix="/api/recording", tags=["recording"])
app.include_router(api.router, prefix="/api", tags=["api"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(custom_reports.router, prefix="/api/reports", tags=["custom_reports"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])

@app.get("/debug/routes", tags=["debug"])
async def debug_routes():
    """List all registered routes"""
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": route.methods
        })
    return {"routes": routes}

@app.get("/")
async def root():
    return {"message": "ActivityLogger API is running."}

@app.on_event("startup")
async def startup_event():
    logger.info("Starting application initialization...")
    start_scheduler()
    logger.info("Scheduler started successfully")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

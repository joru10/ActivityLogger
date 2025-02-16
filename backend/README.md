# ActivityLogger Backend

FastAPI-based backend service for ActivityLogger application.

## Components

### API Endpoints
- `/api/recording/*`: Audio recording and transcription
- `/api/reports/*`: Report generation and management
- `/api/settings`: Application configuration

### Models
- `ActivityLog`: Activity records with timestamps
- `Settings`: Application configuration with nested categories

### Storage
- Audio files: `/storage/YYYY-MM-DD/`
- Daily reports: `/reports/daily/`
- Database: `activity_logger.db`

## Development

### Local Setup
```bash
# From project root
source venv/bin/activate
cd backend
uvicorn main:app --reload
```

# Database Management
```bash
# Initialize database
python init_db.py

# Backup
cp activity_logger.db activity_logger.db.backup
```

# Environment Variables

OPENAI_API_KEY=your_key_here  # For Whisper transcription
LLM_PROVIDER=LMStudio        # LLM provider selection

# Testing 

pytest tests/

# API Documentation

When running, visit:

OpenAPI UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc


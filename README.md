# ActivityLogger

A personal web application for capturing, transcribing, and analyzing activities through audio recordings and LLM-enhanced reporting.

## Overview

ActivityLogger is designed to:
* Capture and transcribe audio recordings
* Log activities (e.g., work sessions, meetings) into a database
* Generate detailed daily reports using LLM and YAML-based prompts
* Support dynamic configuration of activity categories and groups

## System Architecture

### Backend
* **FastAPI & Uvicorn**: REST API with async support
* **SQLAlchemy & SQLite**: Data persistence
* **OpenAI Whisper**: Audio transcription
* **LLM Integration**: Report generation with configurable providers
* **File System Storage**: 
  - Audio: `/storage/YYYY-MM-DD/`
  - Reports: `/reports/daily/`

### Frontend
* **React**: Web interface with functional components
* **Web Audio API**: Audio recording
* **Axios**: API communication
* **React Router**: Navigation

## Installation

### Prerequisites
* Python 3.8+
* Node.js 16+
* npm 8+
* Virtual environment tools

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/ActivityLogger.git
cd ActivityLogger

# Create and activate virtual environment manually (if setup.sh fails)
python3 -m venv venv
source venv/bin/activate  # On Mac/Linux
# or
.\venv\Scripts\activate  # On Windows

# Install dependencies
./setup.sh  # Uses the automated setup
# or manually:
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

## Running the Application

### Using Launch Script (Recommended)
```bash
./launch.sh         # Start both frontend and backend
./launch.sh backend # Start only backend
./launch.sh frontend # Start only frontend
```

### Manual Startup (If launch.sh fails)

1. Backend:
```bash
# Terminal 1
source venv/bin/activate
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

2. Frontend:
```bash
# Terminal 2
cd frontend
npm start
```

### Access Points
* Frontend UI: http://localhost:3000
* Backend API: http://localhost:8000
* API Documentation: http://localhost:8000/docs

## Development Environment

### VS Code Configuration
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
    "python.linting.enabled": true,
    "editor.formatOnSave": true
}
```

### Virtual Environment Management
```bash
# Create new environment
python3 -m venv venv

# Activate
source venv/bin/activate

# Verify activation
which python  # Should show venv path

# Deactivate when needed
deactivate
```

### Database Management
```bash
# Access SQLite database
sqlite3 backend/activity_logger.db

# Backup database
cp backend/activity_logger.db backend/activity_logger.db.backup
```

## Troubleshooting

### Common Issues
1. Port conflicts:
```bash
lsof -i :3000  # Check frontend port
lsof -i :8000  # Check backend port
kill -9 <PID>  # Free up port if needed
```

2. Virtual environment issues:
```bash
# Rebuild virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
./setup.sh
```

3. Database issues:
```bash
# Reset database
rm backend/activity_logger.db
python backend/init_db.py
```

## Additional Documentation
* [Detailed Architecture](Intro.md)
* [Frontend Details](frontend/README.md)
* [API Documentation](http://localhost:8000/docs)

## License

[Add your license information]

## Contributing

[Add contribution guidelines]
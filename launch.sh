#!/bin/bash
set -e

# Setup environment if needed
if [ ! -d "venv" ]; then
    ./setup.sh
fi

# Function to start backend
start_backend() {
    echo "Starting backend..."
    source venv/bin/activate
    # Run uvicorn from the project root to properly handle package imports
    # This allows relative imports in the backend package to work correctly
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
}

# Function to start frontend
start_frontend() {
    echo "Starting frontend..."
    cd frontend
    npm install
    npm start
}

# Start services based on argument
case $1 in
    "backend")
        start_backend
        ;;
    "frontend")
        start_frontend
        ;;
    *)
        # Start both in parallel
        start_backend &
        start_frontend &
        wait
        ;;
esac
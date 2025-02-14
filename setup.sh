#!/bin/bash
set -e

# Determine the component to install
COMPONENT=${1:-"all"}

echo "Setting up ActivityLogger ($COMPONENT)..."

# Create/update virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

case $COMPONENT in
    "backend")
        pip install -r backend/requirements.txt
        ;;
    "frontend")
        pip install -r frontend/requirements.txt
        ;;
    "dev")
        pip install -r requirements-dev.txt
        ;;
    *)
        pip install -r requirements-base.txt
        pip install -r backend/requirements.txt
        pip install -r frontend/requirements.txt
        ;;
esac

echo "Setup complete for $COMPONENT!"
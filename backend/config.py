# config.py
import os
# config.py
import os

# Compute the project root relative to this file.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Define the storage directory (you can adjust this as needed).
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")

# Define the reports directory for daily reports.
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports", "daily")

# Create directories if they don't exist.
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# Define your nested categories structure as JSON.
CATEGORIES = {
    "categories": [
        {
            "name": "Coding",
            "groups": [
                "ActivityReports project",
                "ColabsReview",
                "MultiAgent"
            ]
        },
        {
            "name": "Training",
            "groups": [
                "NLP Course",
                "Deep Learning Specialization"
            ]
        },
        {
            "name": "Research",
            "groups": [
                "Paper Reading: Transformer-XX",
                "Video: New Architecture"
            ]
        },
        {
            "name": "Business",
            "groups": [
                "Project Bids",
                "Client Meetings"
            ]
        },
        {
            "name": "Work&Finance",
            "groups": [
                "Unemployment",
                "Work-search",
                "Pensions-related"
            ]
        }
    ]
}

# Optionally, define a function to get the categories as a JSON string.
import json
def get_categories_json():
    return json.dumps(CATEGORIES)
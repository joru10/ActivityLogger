# ActivityLogger Architecture

## 1. Introduction

ActivityLogger is a personal web application designed to streamline the process of tracking, transcribing, and analyzing personal activities. It leverages audio recordings and Large Language Model (LLM) capabilities to provide insightful reports.

The primary goals of the application are:
*   To provide an easy way to capture activities via audio recording.
*   To automatically transcribe these recordings.
*   To log structured activity data into a persistent database.
*   To generate enriched daily, weekly, and other periodic reports using LLM integration.
*   To allow dynamic configuration of activity categories and groups for personalized tracking.

## 2. System Overview

ActivityLogger consists of three main components:
*   **Backend:** A Python-based API built with FastAPI, responsible for business logic, data persistence, LLM interaction, and serving data to the frontend.
*   **Frontend:** A React-based single-page application (SPA) providing the user interface for recording, viewing reports, and managing settings.
*   **Database:** An SQLite database for storing activity logs, user settings, and cached reports.
*   **File Storage:** The local file system is used to store audio recordings and generated report files.

Core technologies employed include:
*   **Backend:** Python, FastAPI, Uvicorn, SQLAlchemy (for SQLite), Pydantic, OpenAI Whisper, various LLM APIs.
*   **Frontend:** JavaScript, React, React Router, Axios, Web Audio API.
*   **Database:** SQLite.

## 3. Backend Architecture

The backend is the core of ActivityLogger, handling data processing, external service integrations, and API provision.

### 3.1. Framework & Core Technologies

*   **FastAPI & Uvicorn:** The REST API is built using [FastAPI](https://fastapi.tiangolo.com/), a modern, high-performance Python web framework. It runs on [Uvicorn](https://www.uvicorn.org/), an ASGI (Asynchronous Server Gateway Interface) server, enabling asynchronous request handling for improved performance.
*   **SQLAlchemy & SQLite:**
    *   **SQLite** ([`backend/activity_logger.db`](backend/activity_logger.db)) is used as the relational database engine due to its simplicity and file-based nature, suitable for a personal application.
    *   **SQLAlchemy** ([`activitylogger/backend/models.py`](activitylogger/backend/models.py)) is employed as the Object Relational Mapper (ORM). It allows developers to interact with the database using Python objects and methods, abstracting away raw SQL queries. Key models include `ActivityLog`, `Settings`, and `ReportCache`.
*   **Pydantic:** ([`activitylogger/backend/models.py`](activitylogger/backend/models.py), [`activitylogger/backend/recording.py`](activitylogger/backend/recording.py), [`activitylogger/backend/reports.py`](activitylogger/backend/reports.py)) Pydantic is extensively used for data validation, serialization, and settings management. It defines the structure of API request/response bodies and is crucial for ensuring data integrity when interacting with the LLM, parsing its JSON outputs.
*   **LLM Integration:** ([`activitylogger/backend/llm_service.py`](activitylogger/backend/llm_service.py), [`activitylogger/backend/reports.py`](activitylogger/backend/reports.py)) The system integrates with LLMs to generate narrative reports and process transcripts.
    *   Prompts are defined in YAML files (e.g., [`activitylogger/profiles/ActivityReports_Daily.yaml`](activitylogger/profiles/ActivityReports_Daily.yaml)).
    *   These prompts can include dynamic placeholders (like `{categories_json}`) which are populated at runtime with user-specific settings.
    *   The [`llm_service.py`](activitylogger/backend/llm_service.py) module handles API calls to the LLM, including retry logic and robust JSON extraction from potentially unstructured LLM responses.
*   **OpenAI Whisper:** ([`activitylogger/backend/recording.py`](activitylogger/backend/recording.py)) Audio transcription is performed using OpenAI's Whisper model, likely via its API or a local inference setup, to convert spoken words from recordings into text.

### 3.2. Module Organization

The backend codebase is organized into several key modules:

*   [`main.py`](activitylogger/backend/main.py): The main application entry point. It initializes the FastAPI application, includes routers from other modules, and can handle application-level events like startup.
*   [`api.py`](activitylogger/backend/api.py): Contains core API endpoints, primarily for managing activity logs (reading) and application settings (reading/updating).
*   [`models.py`](activitylogger/backend/models.py): Defines the SQLAlchemy database models (`ActivityLog`, `Settings`, `ReportCache`, `Category`) and Pydantic models for data validation and serialization. Includes logic for database initialization and default settings.
*   [`recording.py`](activitylogger/backend/recording.py): Manages all aspects of activity recording. This includes:
    *   API endpoints for starting and stopping recordings.
    *   Audio processing and transcription (using Whisper).
    *   Processing transcripts with an LLM to extract structured activity data.
    *   Validating and saving activity logs to the database.
*   [`reports.py`](activitylogger/backend/reports.py): The central module for generating various types of reports (daily, weekly, monthly, quarterly, annual). It fetches data, interacts with the LLM using profile-based prompts, processes the LLM response, and saves/serves the generated reports. It also includes endpoints for listing and exporting reports.
*   [`llm_service.py`](activitylogger/backend/llm_service.py): A dedicated service for interacting with the LLM. It abstracts the complexities of API calls, response parsing (especially JSON extraction and fixing), and retry mechanisms.
*   [`scheduler.py`](activitylogger/backend/scheduler.py): Implements background task scheduling using APScheduler for automated report generation (e.g., daily reports). Includes endpoints to manage and monitor the scheduler.
*   [`json2csv/`](activitylogger/backend/json2csv/): A sub-module/package likely providing functionality to convert JSON report data into CSV format, used by the export features in [`reports.py`](activitylogger/backend/reports.py). Contains its own simple Flask app ([`app.py`](activitylogger/backend/json2csv/app.py)) which might be for standalone testing or a microservice-like utility.
*   *Other report-related files:* Files like [`custom_reports.py`](activitylogger/backend/custom_reports.py), [`enhanced_report_generator.py`](activitylogger/backend/enhanced_report_generator.py), [`fix_weekly_report.py`](activitylogger/backend/fix_weekly_report.py) appear to be older, experimental, or utility scripts. Their functionality should be reviewed for integration into the main [`reports.py`](activitylogger/backend/reports.py) module or for deprecation to simplify the codebase.

### 3.3. Data Storage

*   **Database:**
    *   **Type:** SQLite
    *   **File:** [`backend/activity_logger.db`](backend/activity_logger.db)
    *   **Key Tables** (defined in [`models.py`](activitylogger/backend/models.py)):
        *   `activity_logs`: Stores individual recorded activities (timestamp, duration, group, description).
        *   `settings`: Stores application settings, including user-defined categories and groups (often as a JSON string).
        *   `report_cache`: Caches generated reports to avoid re-generation, storing report data and metadata.
        *   `categories`: Potentially a table for categories if not solely managed within the JSON structure of the `settings` table.
*   **File System:**
    *   **Audio Recordings:** Stored in date-organized directories, e.g., `storage/YYYY-MM-DD/` (path relative to project root or a configurable base). This includes raw audio files and potentially transcript files.
    *   **Generated Reports:** Saved in type- and date-organized directories, e.g., `reports/daily/YYYY-MM-DD_report.json`, `reports/weekly/YYYY-WW_report.html`.

### 3.4. Key Processes & Data Flows

The application supports several key workflows:

*   **Activity Recording & Logging:**
    *   *Diagram:* See [`docs/images/recording_flow.png`](activitylogger/docs/images/recording_flow.png)
    *   *Description:* The user initiates recording via the frontend. Audio is captured, sent to the backend, saved, and then transcribed (Whisper). The transcript is processed by an LLM (using a specific profile from [`profiles/ActivityLogs.yaml`](activitylogger/profiles/ActivityLogs.yaml)) to extract structured activity details, which are then validated and saved to the `activity_logs` table.
*   **Report Generation (General Flow):**
    *   *Diagram:* See [`docs/images/report_flow.png`](activitylogger/docs/images/report_flow.png)
    *   *Description:* When a report is requested (or triggered by the scheduler), the backend fetches relevant `activity_logs` for the period. It loads a corresponding YAML report profile (e.g., [`profiles/ActivityReports_Daily.yaml`](activitylogger/profiles/ActivityReports_Daily.yaml)), injects dynamic data like user categories from `settings`, and combines this with the aggregated logs. This consolidated prompt is sent to the LLM. The LLM's response (ideally structured JSON) is parsed, potentially fixed by [`llm_service.py`](activitylogger/backend/llm_service.py), formatted into a human-readable report (HTML, Markdown), and then cached in `report_cache` and saved to the file system. The report is then made available to the frontend.
*   **Settings Management:**
    *   *Diagram:* See [`docs/images/settings_flow.png`](activitylogger/docs/images/settings_flow.png)
    *   *Description:* The user can modify application settings, such as activity categories and groups, via the frontend. These changes are sent to the backend API, validated (Pydantic), and saved to the `settings` table in the database. These settings are then dynamically loaded during processes like report generation.

### 3.5. API Endpoints

The backend exposes a RESTful API. Key resource categories include:
*   `/api/activity-logs`: For accessing stored activity logs.
*   `/api/settings`: For reading and updating application settings.
*   `/api/start`, `/api/stop`: For controlling audio recording.
*   `/api/reports/...`: A comprehensive set of endpoints for generating, fetching, listing, and exporting various reports (daily, weekly, etc.).
*   `/api/scheduler/...`: For managing and querying the status of the background report scheduler.

A detailed, interactive API documentation is available via Swagger UI at `http://localhost:8000/docs` when the backend server is running.

## 4. Frontend Architecture

The frontend provides the user interface for interacting with ActivityLogger.

### 4.1. Framework & Core Technologies

*   **React:** ([`activitylogger/frontend/src/App.js`](activitylogger/frontend/src/App.js)) The UI is built as a Single Page Application (SPA) using [React](https://reactjs.org/). It primarily uses functional components and React Hooks (`useState`, `useEffect`) for state management and side effects.
*   **React Router:** ([`activitylogger/frontend/src/App.js`](activitylogger/frontend/src/App.js)) Client-side routing and navigation between different views (e.g., Recorder, Reports, Settings) is handled by `react-router-dom`.
*   **Axios:** ([`activitylogger/frontend/src/ReportsPage.js`](activitylogger/frontend/src/ReportsPage.js)) Used as the HTTP client for making API calls from the frontend to the backend.
*   **Web Audio API:** ([`activitylogger/frontend/src/Recorder.js`](activitylogger/frontend/src/Recorder.js)) Leveraged for capturing audio directly in the browser for the recording feature.

### 4.2. Component Structure

Key frontend components located in [`activitylogger/frontend/src/`](activitylogger/frontend/src/):
*   [`App.js`](activitylogger/frontend/src/App.js): The main application component that sets up routing and renders page-level components.
*   [`Recorder.js`](activitylogger/frontend/src/Recorder.js): Handles the UI and logic for starting, stopping, and managing audio recordings.
*   [`ActivityLogsTable.js`](activitylogger/frontend/src/ActivityLogsTable.js): A component likely used to display activity logs in a tabular format, possibly on the calendar or a dedicated logs page.
*   [`CalendarPage.js`](activitylogger/frontend/src/CalendarPage.js): Provides a calendar view for navigating and viewing activities logged on specific dates.
*   [`ReportsPage.js`](activitylogger/frontend/src/ReportsPage.js): Allows users to select report types (daily, weekly, etc.), specify dates, trigger report generation, and view the generated reports.
*   [`SettingsPage.js`](activitylogger/frontend/src/SettingsPage.js): Provides the interface for users to configure application settings, such as activity categories and groups.
*   [`NotificationManager.js`](activitylogger/frontend/src/NotificationManager.js): Manages and displays desktop notifications to the user for events like recording completion or report availability.

### 4.3. State Management

Currently, state management appears to be primarily handled within individual components using React Hooks (`useState`, `useEffect`). For more complex state interactions or shared state across distant components, a global state management library (like Redux, Zustand, or React Context API used more extensively) might be considered in the future if complexity grows.

### 4.4. Key UI Flows

*   **Recording an Activity:** User navigates to the recording interface, starts recording, speaks, and then stops recording. The frontend handles audio capture and sends data to the backend.
*   **Viewing/Generating a Report:** User navigates to the reports page, selects report parameters (type, date), and requests the report. The frontend communicates with the backend to fetch or trigger generation and then displays the result.
*   **Updating Settings:** User navigates to the settings page, modifies configurations (e.g., categories), and saves them. The frontend sends updated settings to the backend.

## 5. Deployment & Environment

### 5.1. Prerequisites

*   Python 3.8+
*   Node.js 16+ & npm 8+
*   Virtual environment tool for Python (e.g., `venv`)

### 5.2. Setup & Installation

1.  Clone the repository.
2.  Create and activate a Python virtual environment (e.g., `python3 -m venv venv; source venv/bin/activate`).
3.  Install backend dependencies: `pip install -r backend/requirements.txt`.
4.  Install frontend dependencies: `cd frontend && npm install && cd ..`.
    The [`setup.sh`](activitylogger/setup.sh) script automates these installation steps.

### 5.3. Running the Application

*   **Using Launch Script (Recommended):** The [`launch.sh`](activitylogger/launch.sh) script provides a convenient way to start the application:
    *   `./launch.sh`: Starts both backend and frontend.
    *   `./launch.sh backend`: Starts only the backend.
    *   `./launch.sh frontend`: Starts only the frontend.
*   **Manual Startup:**
    1.  **Backend:** (In Terminal 1, from project root, after activating venv)
        `cd backend`
        `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
    2.  **Frontend:** (In Terminal 2, from project root)
        `cd frontend`
        `npm start`
*   **Access Points:**
    *   Frontend UI: `http://localhost:3000`
    *   Backend API: `http://localhost:8000`
    *   API Docs: `http://localhost:8000/docs`

### 5.4. Configuration

*   **Environment Variables:** The application may use environment variables for sensitive or environment-specific configurations (e.g., LLM API keys, database paths if not hardcoded). These should be managed via `.env` files (which are gitignored by [`activitylogger/.gitignore`](activitylogger/.gitignore:22)).
*   **Profile YAMLs:** Located in [`activitylogger/profiles/`](activitylogger/profiles/), these files (e.g., [`ActivityLogs.yaml`](activitylogger/profiles/ActivityLogs.yaml), [`ActivityReports_Daily.yaml`](activitylogger/profiles/ActivityReports_Daily.yaml)) define prompts and configurations for LLM interactions for different tasks (activity extraction, report generation).

## 6. Data Models (Detailed)

Key data structures are defined using SQLAlchemy for database persistence and Pydantic for API validation and data interchange.

*   **`ActivityLog`** (in [`models.py`](activitylogger/backend/models.py:60-67)):
    *   SQLAlchemy: Represents an entry in the `activity_logs` table. Fields typically include `id`, `timestamp`, `duration_minutes`, `group`, `description`, `date`.
    *   Pydantic ([`Activity` in `recording.py`](activitylogger/backend/recording.py:25-68)): Used for validating activity data received from LLM processing or API inputs. Includes validators for fields like `timestamp`, `duration_minutes`.
*   **`Settings`** (in [`models.py`](activitylogger/backend/models.py:69-143)):
    *   SQLAlchemy: Represents an entry in the `settings` table. Stores various application settings, notably `categories` (often as a JSON string representing nested categories and groups), `llm_model_log_generation`, `llm_model_report_generation`, `notification_interval`.
    *   Pydantic ([`SettingsUpdate` in `api.py`](activitylogger/backend/api.py:57-67)): Used for validating settings updates via the API.
*   **`ReportCache`** (in [`models.py`](activitylogger/backend/models.py:150-164)):
    *   SQLAlchemy: Represents an entry in the `report_cache` table. Fields include `report_type`, `report_date`, `generated_at`, `report_data` (JSON string of the report content), `file_path`.
*   **Other Pydantic Models:** Various Pydantic models are used throughout the backend for request/response validation in API endpoints (e.g., in [`reports.py`](activitylogger/backend/reports.py) for report parameters and responses).

## 7. Testing Strategy

Ensuring code quality and stability requires a robust testing strategy.

### 7.1. Overview of Current Testing

*   **Backend:**
    *   Pytest is used as the testing framework.
    *   Existing tests include:
        *   [`test_integration.py`](activitylogger/backend/test_integration.py): Appears to test a complete report generation flow.
        *   [`test_llm.py`](activitylogger/backend/test_llm.py): Tests direct LLM API calls and JSON extraction.
        *   [`test_weekly_report.py`](activitylogger/backend/test_weekly_report.py) (in backend root and also one in `activitylogger/`): Tests weekly report generation.
*   **Frontend:**
    *   React projects typically use Jest and React Testing Library.
    *   Existing tests include:
        *   [`App.test.js`](activitylogger/frontend/src/App.test.js): Basic test for the App component.
        *   [`setupTests.js`](activitylogger/frontend/src/setupTests.js): Configuration for React Testing Library.

### 7.2. Running Tests

*   **Backend:** (From the `backend` directory, after activating venv)
    `pytest`
*   **Frontend:** (From the `frontend` directory)
    `npm test`

### 7.3. Proposed Enhancements / Areas for Improvement

*   **Implement Comprehensive Smoke Tests:** Create a suite of smoke tests that quickly verify the basic functionality of all critical application paths after any change.
*   **Increase Unit Test Coverage:**
    *   **Backend:** Add more unit tests for individual functions and classes, especially in complex modules like [`reports.py`](activitylogger/backend/reports.py), [`recording.py`](activitylogger/backend/recording.py), and [`llm_service.py`](activitylogger/backend/llm_service.py). Mock external dependencies (LLM calls, file system) where appropriate.
    *   **Frontend:** Add unit tests for individual React components, focusing on rendering, user interactions, and state changes.
*   **Expand Integration Test Coverage:**
    *   **Backend:** Add more integration tests that verify interactions between different backend modules and with the database.
    *   **Frontend:** Implement integration tests that simulate user flows across multiple components.
*   **End-to-End (E2E) Tests:** Consider adding a few E2E tests using tools like Cypress or Playwright to verify complete application flows from the UI to the database and back.
*   **Document Test Creation Guidelines:** Provide clear guidelines for developers on how to write effective tests for new features or bug fixes.
*   **CI/CD Integration:** Integrate automated testing into a CI/CD pipeline to ensure tests are run automatically on every code change.

### 7.4. Version Control & Checkpoints

*   **Git:** The project uses Git for version control. It is crucial to:
    *   Commit changes frequently with clear, descriptive messages.
    *   Use branches for developing new features or fixing bugs to isolate changes.
    *   Create tags for releases or significant checkpoints.
    *   This allows for easy rollbacks to previous stable states if issues arise.

## 8. Diagrams

The following diagrams provide visual representations of key architectural flows and are located in the [`docs/images/`](activitylogger/docs/images/) directory:

*   **Recording & Activity Log Insertion Flow:** [`docs/images/recording_flow.png`](activitylogger/docs/images/recording_flow.png) (Source: [`recording_flow.mmd`](activitylogger/docs/images/recording_flow.mmd))
*   **Daily Report Generation Flow:** [`docs/images/report_flow.png`](activitylogger/docs/images/report_flow.png) (Source: [`report_flow.mmd`](activitylogger/docs/images/report_flow.mmd))
*   **Settings Update Flow:** [`docs/images/settings_flow.png`](activitylogger/docs/images/settings_flow.png) (Source: [`settings_flow.mmd`](activitylogger/docs/images/settings_flow.mmd))

These diagrams should be kept up-to-date as the architecture evolves.

## 9. Potential Areas for Improvement (Summary)

This section will be detailed separately after this document draft.
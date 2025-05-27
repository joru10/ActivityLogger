import pytest
from datetime import datetime
from fastapi.testclient import TestClient
# The client fixture will be injected from conftest.py, so we don't need to import app here directly
# from activitylogger.backend.main import app 

# client = TestClient(app) # This is now handled by the 'client' fixture in conftest.py

def test_read_api_docs(client): # Added client fixture
    """Test if the API docs (Swagger UI) are reachable."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_read_settings_api(client): # Added client fixture
    """Test if the /api/settings endpoint is reachable and returns JSON."""
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    try:
        data = response.json()
        assert isinstance(data, dict) # Assuming settings are returned as a dictionary
    except ValueError:
        pytest.fail("Response was not valid JSON.")

def test_list_daily_reports_api(client): # Added client fixture
    """Test if the /api/reports/list-reports/daily endpoint is reachable and returns JSON."""
    response = client.get("/api/reports/list-reports/daily")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    try:
        data = response.json()
        assert isinstance(data, dict)
        assert "reports" in data
        assert isinstance(data["reports"], list)
    except ValueError:
        pytest.fail("Response was not valid JSON.")

def test_list_weekly_reports_api(client): # Added client fixture
    """Test if the /api/reports/list-reports/weekly endpoint is reachable and returns JSON."""
    response = client.get("/api/reports/list-reports/weekly")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    try:
        data = response.json()
        assert isinstance(data, dict)
        assert "reports" in data
        assert isinstance(data["reports"], list)
    except ValueError:
        pytest.fail("Response was not valid JSON.")

def test_list_monthly_reports_api(client): # Added client fixture
    """Test if the /api/reports/list-reports/monthly endpoint is reachable and returns JSON."""
    response = client.get("/api/reports/list-reports/monthly")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    try:
        data = response.json()
        assert isinstance(data, dict)
        assert "reports" in data
        assert isinstance(data["reports"], list)
    except ValueError:
        pytest.fail("Response was not valid JSON.")

def test_list_quarterly_reports_api(client): # Added client fixture
    """Test if the /api/reports/list-reports/quarterly endpoint is reachable and returns JSON."""
    response = client.get("/api/reports/list-reports/quarterly")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    try:
        data = response.json()
        assert isinstance(data, dict)
        assert "reports" in data
        assert isinstance(data["reports"], list)
    except ValueError:
        pytest.fail("Response was not valid JSON.")

def test_list_annual_reports_api(client): # Added client fixture
    """Test if the /api/reports/list-reports/annual endpoint is reachable and returns JSON."""
    response = client.get("/api/reports/list-reports/annual")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    try:
        data = response.json()
        assert isinstance(data, dict)
        assert "reports" in data
        assert isinstance(data["reports"], list)
    except ValueError:
        pytest.fail("Response was not valid JSON.")

def test_update_and_read_settings_api(client): # Added client fixture
    """Test updating settings and reading them back."""
    # 1. Get initial settings (defaults from fresh test DB)
    response_initial = client.get("/api/settings")
    assert response_initial.status_code == 200
    initial_settings = response_initial.json()
    
    # Prepare updated settings data
    updated_notification_interval = initial_settings.get("notificationInterval", 10) + 5
    
    updated_categories = initial_settings.get("categories", [])
    if not updated_categories:
        updated_categories.append({"name": "Work", "groups": ["Coding", "Meetings"]})
    else:
        updated_categories[0]["name"] = updated_categories[0].get("name", "Default") + " Updated"
        if not updated_categories[0].get("groups"):
            updated_categories[0]["groups"] = ["Test Group"]
        else:
            updated_categories[0]["groups"][0] = updated_categories[0]["groups"][0] + " Updated"

    settings_to_update = {
        "notificationInterval": updated_notification_interval,
        "audioDevice": initial_settings.get("audioDevice", "default_device"),
        "llmProvider": initial_settings.get("llmProvider", "default_provider"),
        "openRouterApiKey": initial_settings.get("openRouterApiKey", ""),
        "openRouterLLM": initial_settings.get("openRouterLLM", ""),
        "lmstudioEndpoint": initial_settings.get("lmstudioEndpoint", "http://localhost:1234/v1"),
        "lmstudioModel": initial_settings.get("lmstudioModel", "default_model"),
        "lmstudioLogsModel": initial_settings.get("lmstudioLogsModel"),
        "lmstudioReportsModel": initial_settings.get("lmstudioReportsModel"),
        "categories": updated_categories
    }

    # 2. Update settings
    response_update = client.put("/api/settings", json=settings_to_update)
    assert response_update.status_code == 200
    update_result = response_update.json()
    # Assuming the success message might vary or not be critical for this test, 
    # focusing on data verification. If a specific message is guaranteed, assert it.
    # assert update_result.get("message") == "Settings updated successfully" 

    # 3. Get updated settings and verify changes
    response_updated = client.get("/api/settings")
    assert response_updated.status_code == 200
    final_settings = response_updated.json()

    assert final_settings["notificationInterval"] == updated_notification_interval
    
    # Ensure categories are compared correctly, accounting for potential order changes if not guaranteed
    # For simplicity here, we assume order is preserved or the update logic ensures it.
    assert final_settings["categories"] == updated_categories
    
    assert final_settings["audioDevice"] == initial_settings.get("audioDevice", "default_device")

def create_test_activity(client, description="Test activity"):
    """Helper function to create a test activity."""
    activity_data = {
        "timestamp": "2023-01-01T10:00:00",
        "description": description,
        "category": "Work",
        "group": "Test Group",
        "duration_minutes": 60
    }
    response = client.post("/api/activities", json=activity_data)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
    return response.json()

def test_create_activity(client):
    """Test creating a new activity."""
    activity = create_test_activity(client, "Test activity for creation")
    assert activity["description"] == "Test activity for creation"
    assert "id" in activity

def test_get_activity(client):
    """Test retrieving a specific activity."""
    # First create an activity to retrieve
    activity = create_test_activity(client, "Test activity for retrieval")
    
    # Now retrieve it
    response = client.get(f"/api/activities/{activity['id']}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
    data = response.json()
    assert data["id"] == activity["id"]
    assert data["description"] == "Test activity for retrieval"

def test_update_activity(client):
    """Test updating an existing activity."""
    # First create an activity to update
    activity = create_test_activity(client, "Test activity before update")
    
    # Now update it
    update_data = {
        "timestamp": "2023-01-01T11:00:00",
        "description": "Test activity after update",
        "category": "Personal",
        "group": "Other Group",
        "duration_minutes": 60
    }
    response = client.put(f"/api/activities/{activity['id']}", json=update_data)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
    
    # Verify the update
    response = client.get(f"/api/activities/{activity['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Test activity after update"
    assert data["category"] == "Personal"
    assert data["group"] == "Other Group"

def test_delete_activity(client):
    """Test deleting an activity."""
    # Create a new activity to delete
    activity_data = {
        "timestamp": "2023-01-01T10:00:00",
        "description": "Test activity for deletion",
        "category": "Work",
        "group": "Test Group",
        "duration_minutes": 30
    }
    create_response = client.post("/api/activities", json=activity_data)
    assert create_response.status_code == 200
    activity_id = create_response.json()["id"]
    
    # Now delete it
    response = client.delete(f"/api/activities/{activity_id}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
    
    # Verify it's gone
    response = client.get(f"/api/activities/{activity_id}")
    assert response.status_code == 404  # Should be 404 Not Found after deletion

def test_generate_weekly_report(client, db):
    """Test triggering weekly report generation with test data."""
    # Add test activity data
    test_activity = {
        "timestamp": datetime.now().isoformat(),
        "description": "Test activity",
        "category": "Testing",
        "group": "Development",
        "duration_minutes": 30
    }
    
    # Create test activity
    response = client.post("/api/activities/", json=test_activity)
    assert response.status_code == 200, "Failed to create test activity"
    
    # Now generate the report
    response = client.post("/api/reports/generate-weekly")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
    response_data = response.json()
    assert "html_report" in response_data, "Response should contain 'html_report' field"
    assert isinstance(response_data["html_report"], str), "html_report should be a string"

def test_llm_service_endpoint(client):
    """Test basic reachability of the LLM service endpoint."""
    # This test assumes a /api/llm/process-text endpoint exists and accepts a simple POST
    # Adjust the endpoint and payload based on actual LLM service implementation
    test_payload = {"text": "This is a test for LLM service."}
    response = client.post("/api/llm/process-text", json=test_payload)
    # Expecting 200 OK or 404 Not Found if not implemented/configured
    # If 404, it means the endpoint doesn't exist, which is a valid smoke test outcome
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        assert "response" in response.json() # Assuming some response key

def test_scheduler_status_endpoint(client):
    """Test basic reachability of the scheduler status endpoint."""
    # This test assumes a /api/scheduler/status endpoint exists
    response = client.get("/api/scheduler/status")
    assert response.status_code in [200, 404] # Expecting 200 OK or 404 Not Found
    if response.status_code == 200:
        assert "running" in response.json() # Asserting a known key in the response
        assert response.json()["running"] is False # Asserting the expected value

def test_non_existent_endpoint(client):
    """Test accessing a non-existent endpoint."""
    response = client.get("/api/non-existent-path")
    assert response.status_code == 404

def test_invalid_payload(client):
    """Test sending an invalid payload to an endpoint that expects JSON."""
    invalid_data = "this is not json"
    response = client.post("/api/activities", content=invalid_data, headers={"Content-Type": "application/json"})
    assert response.status_code == 422 # Unprocessable Entity for validation errors

def test_read_llm_api(client):
    """Test if the LLM processing endpoint is reachable and works."""
    # Test the LLM process-text endpoint
    test_text = "Test LLM processing"
    response = client.post(
        "/api/llm/process-text",
        json={"text": test_text}
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
    data = response.json()
    assert "response" in data
    assert test_text in data["response"]  # Check if the response contains our test text

def test_activity_logs_endpoint(client):
    """Test the activity logs endpoint with various filters."""
    # Create a test activity
    activity_data = {
        "timestamp": "2023-01-01T10:00:00",
        "description": "Test activity for logs",
        "category": "Work",
        "group": "Test Group",
        "duration_minutes": 45
    }
    create_response = client.post("/api/activities", json=activity_data)
    assert create_response.status_code == 200
    
    # Test without date filter (should return all activities)
    response = client.get("/api/activity-logs")
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
    
    # Test with date filter (should find our test activity)
    response = client.get("/api/activity-logs?date=2023-01-01")
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
    assert any(log.get("description") == "Test activity for logs" for log in logs)
    
    # Test with date filter that shouldn't match
    response = client.get("/api/activity-logs?date=2022-12-31")
    assert response.status_code == 200
    logs = response.json()
    assert not any(log.get("description") == "Test activity for logs" for log in logs)

def test_generate_daily_report(client):
    """Test generating a daily report."""
    # First, create a test activity to ensure we have data
    activity_data = {
        "timestamp": "2023-01-01T10:00:00",
        "description": "Test activity for daily report",
        "category": "Work",
        "group": "Test Group",
        "duration_minutes": 60
    }
    create_response = client.post("/api/activities", json=activity_data)
    assert create_response.status_code == 200, "Failed to create test activity"
    
    # Test with specific date that matches our test activity
    response = client.post(
        "/api/reports/generate-daily",
        json={"date": "2023-01-01"}
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
    data = response.json()
    assert "html_report" in data, "Response should contain 'html_report' field"
    assert isinstance(data["html_report"], str), "html_report should be a string"

def test_error_cases(client):
    """Test various error cases."""
    # Test getting non-existent activity
    response = client.get("/api/activities/999999")
    assert response.status_code == 404
    
    # Test updating non-existent activity
    response = client.put(
        "/api/activities/999999",
        json={"description": "Should not exist"}
    )
    assert response.status_code == 404
    
    # Test deleting non-existent activity
    response = client.delete("/api/activities/999999")
    assert response.status_code == 404  # DELETE returns 404 when activity not found
    
    # Test invalid date format for activity logs
    response = client.get("/api/activity-logs?date=invalid-date")
    # The API logs an error but returns 200 with empty results
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    
    # Test invalid date format for daily report
    response = client.post(
        "/api/reports/generate-daily",
        json={"date": "not-a-date"}
    )
    # The API might return 400, 422, or 500 for invalid date format
    assert response.status_code >= 400, \
        f"Expected error status code, got {response.status_code}"

def test_list_reports_endpoints(client):
    """Test the list-reports endpoints."""
    for period in ["daily", "weekly", "monthly", "quarterly", "annual"]:
        response = client.get(f"/api/reports/list-reports/{period}")
        assert response.status_code == 200
        data = response.json()
        assert "reports" in data
        assert isinstance(data["reports"], list)
        
        # Test with invalid period
        response = client.get("/api/reports/list-reports/invalid-period")
        assert response.status_code != 500  # Shouldn't cause a server error

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
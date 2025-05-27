# ActivityLogger Smoke Tests

This document provides comprehensive information about the smoke testing suite for the ActivityLogger application.

## Table of Contents
- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Writing New Tests](#writing-new-tests)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Purpose

Smoke tests are a set of basic tests that verify the core functionality of the application. They are designed to:

- Ensure critical paths work as expected
- Catch major regressions
- Provide quick feedback during development
- Verify API endpoints are functioning

## Prerequisites

Before running the tests, ensure you have:

1. Python 3.8+ installed
2. All project dependencies installed (`pip install -r requirements.txt`)
3. The virtual environment activated (if using one)
4. The backend server is **not** running (to avoid port conflicts)

## Running Tests

### Running All Tests

To run the entire test suite:

```bash
# From the project root directory
pytest backend/test_smoke_api.py -v
```

### Running Specific Tests

To run a specific test:

```bash
# Run a single test
pytest backend/test_smoke_api.py::test_create_activity -v

# Run tests matching a pattern
pytest backend/test_smoke_api.py -k "test_create" -v
```

### Test Output

- `PASSED` - Test completed successfully
- `FAILED` - Test encountered an error or assertion failed
- `SKIPPED` - Test was skipped (usually marked with `@pytest.mark.skip`)
- `WARNING` - Non-critical issues detected

#### Example of a Clean Test Pass

```
==================================== test session starts ====================================
platform darwin -- Python 3.12.9, pytest-8.3.4, pluggy-1.5.0 -- /Users/joru2/miniconda3/bin/python
cachedir: .pytest_cache
rootdir: /Users/joru2/ActivityLogger
configfile: pytest.ini
plugins: asyncio-0.25.3, anyio-4.8.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
collected 22 items

backend/test_smoke_api.py::test_read_api_docs PASSED                                 [  4%]
backend/test_smoke_api.py::test_read_settings_api PASSED                             [  9%]
backend/test_smoke_api.py::test_list_daily_reports_api PASSED                        [ 13%]
backend/test_smoke_api.py::test_list_weekly_reports_api PASSED                       [ 18%]
backend/test_smoke_api.py::test_list_monthly_reports_api PASSED                      [ 22%]
backend/test_smoke_api.py::test_list_quarterly_reports_api PASSED                    [ 27%]
backend/test_smoke_api.py::test_list_annual_reports_api PASSED                       [ 31%]
backend/test_smoke_api.py::test_update_and_read_settings_api PASSED                  [ 36%]
backend/test_smoke_api.py::test_create_activity PASSED                               [ 40%]
backend/test_smoke_api.py::test_get_activity PASSED                                  [ 45%]
backend/test_smoke_api.py::test_update_activity PASSED                               [ 50%]
backend/test_smoke_api.py::test_delete_activity PASSED                               [ 54%]
backend/test_smoke_api.py::test_generate_weekly_report PASSED                        [ 59%]
backend/test_smoke_api.py::test_llm_service_endpoint PASSED                          [ 63%]
backend/test_smoke_api.py::test_scheduler_status_endpoint PASSED                     [ 68%]
backend/test_smoke_api.py::test_non_existent_endpoint PASSED                         [ 72%]
backend/test_smoke_api.py::test_invalid_payload PASSED                               [ 77%]
backend/test_smoke_api.py::test_read_llm_api PASSED                                  [ 81%]
backend/test_smoke_api.py::test_activity_logs_endpoint PASSED                        [ 86%]
backend/test_smoke_api.py::test_generate_daily_report PASSED                         [ 90%]
backend/test_smoke_api.py::test_error_cases PASSED                                   [ 95%]
backend/test_smoke_api.py::test_list_reports_endpoints PASSED                        [100%]

==================================== 22 passed in 0.17s ====================================
```

This output shows a successful test run where all 22 tests passed. Each test is listed with its name and a `PASSED` status, along with a progress percentage. The final line confirms that all tests completed successfully and shows the total execution time.

## Test Structure

The main test file is located at `backend/test_smoke_api.py` and includes tests for:

- API documentation access
- Settings management
- Activity CRUD operations
- Report generation (daily, weekly, etc.)
- Error handling
- Edge cases

## Writing New Tests

### Test Naming

Use descriptive names following the pattern: `test_<feature>_<scenario>`

Example: `test_create_activity_with_valid_data`

### Test Structure

Follow this pattern for new tests:

```python
def test_feature_scenario(client):
    """Test description."""
    # 1. Setup test data
    test_data = {...}
    
    # 2. Execute the action
    response = client.post("/api/endpoint", json=test_data)
    
    # 3. Verify the results
    assert response.status_code == 200
    assert "expected_field" in response.json()
```

### Fixtures

The test suite provides these fixtures:

- `client`: Test client for making requests
- `db`: Database session (use for direct DB operations if needed)

## Troubleshooting

### Common Issues

1. **Port in use**: Ensure no other instance of the application is running
   ```bash
   lsof -i :8000  # Check for processes using port 8000
   kill <PID>     # Terminate the process
   ```

2. **Database issues**: If tests fail with database errors, try:
   ```bash
   rm -f backend/activity_logger.db  # WARNING: This will delete your test database
   pytest backend/test_smoke_api.py -v
   ```

3. **Dependency issues**: Ensure all dependencies are installed
   ```bash
   pip install -r backend/requirements.txt
   ```

### Debugging Tests

To debug a failing test, run with `-s` to see print statements:

```bash
pytest backend/test_smoke_api.py::test_name -v -s
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Cleanup**: Tests should clean up after themselves
3. **Assertions**: Be specific in your assertions
4. **Descriptive**: Use clear test names and docstrings
5. **Performance**: Keep tests fast and focused

## Continuous Integration

These tests are automatically run on pull requests and main branch pushes. Check the CI/CD configuration for details on the test environment.

## Contributing

When adding new features, please add corresponding smoke tests. Update this document if you add new test utilities or change the testing approach.

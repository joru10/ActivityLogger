import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))  # Add project root to path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Import models and app after path is set
from activitylogger.backend.models import Base, init_default_settings, backup_database
from activitylogger.backend.api import get_db as actual_get_db
from activitylogger.backend.main import app

# Use file-based SQLite for tests to avoid in-memory database issues
TEST_DB_PATH = "/tmp/test_activity_logger.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

# Create engine with aggressive connection recycling
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True
)

# Create session factory
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Set up test database
def setup_test_db():
    """Set up the test database with all tables."""
    # Make sure the database file doesn't exist
    if os.path.exists(TEST_DB_PATH):
        os.unlink(TEST_DB_PATH)
    
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    # Initialize with default settings
    db = TestingSessionLocal()
    try:
        init_default_settings(db)
        db.commit()
    finally:
        db.close()

def teardown_test_db():
    """Tear down the test database."""
    if os.path.exists(TEST_DB_PATH):
        os.unlink(TEST_DB_PATH)

# Set up test database before any tests run
setup_test_db()

# Clean up after all tests
def pytest_sessionfinish(session, exitstatus):
    teardown_test_db()

@pytest.fixture(scope="function")
def db():
    """Create a fresh database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    # Start a new transaction with a savepoint
    nested = connection.begin_nested()

    # If the application code calls session.begin_nested(), use that one
    @event.listens_for(session, 'after_transaction_end')
    def restart_savepoint(session, transaction):
        nonlocal nested
        if not connection.in_nested_transaction():
            nested = connection.begin_nested()
    
    try:
        yield session
    finally:
        # Clean up the session and connection
        if session.is_active:
            session.close()
        if connection.in_transaction():
            transaction.rollback()
        connection.close()

@pytest.fixture(scope="function")
def client(db):
    """Create a test client that uses the test database."""
    # Override the get_db dependency
    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()
    
    app.dependency_overrides[actual_get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up overrides
    app.dependency_overrides.clear()
import os
import datetime
import json
import logging
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Setup logging
logger = logging.getLogger(__name__)

# Define the database URL with absolute path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "activity_logs.db"
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create the engine with increased timeout for LLM operations
engine = create_engine(
    DATABASE_URL, 
    connect_args={
        "check_same_thread": False,
        "timeout": 60
    }
)

# Create a configured "SessionLocal" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models
Base = declarative_base()

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    group = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    duration_minutes = Column(Integer)
    description = Column(String)

class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    notificationInterval = Column(Integer, default=30)
    audioDevice = Column(String, default="default")
    llmProvider = Column(String, default="lmstudio")
    lmstudioEndpoint = Column(String, default="http://localhost:1234/v1")
    lmstudioModel = Column(String, default="phi-4")
    openRouterApiKey = Column(String, default="")
    openRouterLLM = Column(String, default="")
    categories = Column(Text, default="{}")

    def get_categories(self):
        """Return the categories as a Python object."""
        try:
            return json.loads(self.categories) if self.categories else {}
        except Exception as e:
            logger.error(f"Error parsing categories: {e}")
            return {}

    def set_categories(self, value):
        """Set the categories from a Python object."""
        try:
            self.categories = json.dumps(value)
        except Exception as e:
            logger.error(f"Error setting categories: {e}")
            self.categories = "{}"

# Initialize database and tables
Base.metadata.create_all(bind=engine)

# Ensure default settings exist
def init_default_settings():
    db = SessionLocal()
    try:
        if not db.query(Settings).first():
            default_settings = Settings()
            db.add(default_settings)
            db.commit()
            logger.info("Default settings initialized")
    except Exception as e:
        logger.error(f"Error initializing settings: {e}")
    finally:
        db.close()

init_default_settings()
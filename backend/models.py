import os
from datetime import datetime
import json
import logging
import atexit
from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session, Mapped, mapped_column
from typing import List, Dict, Any, Optional, Union, TypedDict, Literal
import sqlite3
import os
import logging
import json
from datetime import datetime
import atexit
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing_extensions import Annotated

# Setup logging
logger = logging.getLogger(__name__)

# Define the database URL with absolute path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "activity_logs.db"
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
DATABASE_URL = f"sqlite:///{DB_PATH}"

logger.info(f"Using database at: {DB_PATH}")
# Add after DATABASE_URL definition
logger.info(f"Database exists: {os.path.exists(DB_PATH)}")
logger.info(f"Database size: {os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0} bytes")

# Create the engine with increased timeout for LLM operations
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 60
    }
)
# Add after engine creation
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# After engine creation, before Base.metadata.create_all
def safe_init_database(engine_to_use):
    """Initialize database without dropping existing tables"""
    inspector = inspect(engine_to_use)
    existing_tables = inspector.get_table_names()

    if not existing_tables:
        logger.info("No existing tables found, creating new database")
        Base.metadata.create_all(bind=engine_to_use)
    else:
        logger.info(f"Found existing tables: {existing_tables}")
        # Only create missing tables using the provided engine
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                logger.info(f"Creating missing table: {table.name}")
                table.create(bind=engine_to_use)

# Create a configured "SessionLocal" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models
Base = declarative_base()

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    group = Column(String, index=True)
    category = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    duration_minutes = Column(Integer)
    description = Column(String)

# Pydantic model for category group mapping
class CategoryGroup(TypedDict):
    name: str
    groups: List[str]

# Pydantic model for settings
class SettingsModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra='forbid')
    
    notificationInterval: int = Field(
        default=60,
        ge=1,
        le=1440,  # 24 hours in minutes
        description="Notification interval in minutes"
    )
    audioDevice: str = Field(
        default="default",
        description="Default audio device for recording"
    )
    llmProvider: str = Field(
        default="LMStudio",
        description="Default LLM provider"
    )
    openRouterApiKey: str = Field(
        default="",
        description="API key for OpenRouter service"
    )
    openRouterLLM: str = Field(
        default="",
        description="Default OpenRouter model"
    )
    lmstudioEndpoint: str = Field(
        default="http://localhost:1234/v1",
        description="LM Studio API endpoint"
    )
    lmstudioModel: str = Field(
        default="default_model",
        description="Default LM Studio model"
    )
    lmstudioLogsModel: str = Field(
        default="phi-3-mini-4k",
        description="LM Studio model for processing logs"
    )
    lmstudioReportsModel: str = Field(
        default="gemma-7b",
        description="LM Studio model for generating reports"
    )
    categories: List[CategoryGroup] = Field(
        default_factory=lambda: [
            {"name": "Coding", "groups": ["ActivityReports project", "ColabsReview", "MultiAgent"]},
            {"name": "Training", "groups": ["NLP Course", "Deep Learning Specialization"]},
            {"name": "Research", "groups": ["Paper Reading: Transformer-XX", "Video: New Architecture"]},
            {"name": "Business", "groups": ["Project Bids", "Client Meetings"]},
            {"name": "Work&Finance", "groups": ["Unemployment", "Work-search", "Pensions-related"]}
        ],
        description="Categories and their groups for activity classification"
    )

    @field_validator('categories')
    @classmethod
    def validate_categories(cls, v: List[CategoryGroup]) -> List[CategoryGroup]:
        """Validate categories structure"""
        if not isinstance(v, list):
            raise ValueError("Categories must be a list")
        
        for cat in v:
            if not isinstance(cat, dict) or 'name' not in cat or 'groups' not in cat:
                raise ValueError("Each category must have 'name' and 'groups' keys")
            if not isinstance(cat['name'], str) or not cat['name'].strip():
                raise ValueError("Category name must be a non-empty string")
            if not isinstance(cat['groups'], list) or not all(isinstance(g, str) for g in cat['groups']):
                raise ValueError("Category groups must be a list of strings")
        
        return v

class Settings(Base):
    __tablename__ = "settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    notificationInterval: Mapped[int] = mapped_column(Integer, default=60)
    audioDevice: Mapped[str] = mapped_column(String, default="default")
    llmProvider: Mapped[str] = mapped_column(String, default="LMStudio")
    openRouterApiKey: Mapped[str] = mapped_column(String, default="")
    openRouterLLM: Mapped[str] = mapped_column(String, default="")
    lmstudioEndpoint: Mapped[str] = mapped_column(String, default='http://localhost:1234/v1')
    lmstudioModel: Mapped[str] = mapped_column(String, default='default_model')  # Backward compatibility
    lmstudioLogsModel: Mapped[str] = mapped_column(String, default='phi-3-mini-4k')
    lmstudioReportsModel: Mapped[str] = mapped_column(String, default='gemma-7b')
    categories: Mapped[str] = mapped_column(Text, default=json.dumps(SettingsModel.model_fields['categories'].default_factory()))

    def model_dump(self) -> dict:
        """Convert model to dictionary including parsed categories (Pydantic v2 compatible)"""
        return {
            "notificationInterval": int(self.notificationInterval),
            "audioDevice": str(self.audioDevice),
            "llmProvider": str(self.llmProvider),
            "openRouterApiKey": str(self.openRouterApiKey),
            "openRouterLLM": str(self.openRouterLLM),
            "lmstudioEndpoint": str(self.lmstudioEndpoint),
            "lmstudioModel": str(self.lmstudioModel),
            "lmstudioLogsModel": str(self.lmstudioLogsModel or self.lmstudioModel),
            "lmstudioReportsModel": str(self.lmstudioReportsModel or self.lmstudioModel),
            "categories": self.get_categories()
        }
        
    # Keep dict() as an alias for backward compatibility
    dict = model_dump

    def get_categories(self) -> List[CategoryGroup]:
        """Return the categories as a Python object."""
        try:
            if not self.categories:
                return SettingsModel.model_fields['categories'].default_factory()
            categories = json.loads(self.categories)
            # Validate categories using Pydantic model
            SettingsModel(categories=categories)
            return categories
        except Exception as e:
            logger.error(f"Error parsing categories: {e}")
            # Return default categories on error
            return SettingsModel.model_fields['categories'].default_factory()

    def set_categories(self, categories: List[CategoryGroup]) -> None:
        """Set the categories from a Python object."""
        try:
            # Validate categories using Pydantic model
            validated = SettingsModel(categories=categories)
            self.categories = json.dumps(validated.categories)
            logger.info("Categories updated successfully")
        except Exception as e:
            logger.error(f"Error setting categories: {e}")
            # Reset to default categories on error
            self.categories = json.dumps(SettingsModel.model_fields['categories'].default_factory())
            logger.info("Categories reset to default due to validation error")

    @property
    def notification_interval(self) -> int:
        """Get the notification interval in minutes."""
        return self.notificationInterval

    @notification_interval.setter
    def notification_interval(self, value: int) -> None:
        """Set the notification interval in minutes (1-1440)."""
        try:
            interval = int(value)
            if interval < 1 or interval > 1440:
                raise ValueError("Interval must be between 1 and 1440 minutes")
            logger.info(f"Setting notification interval to: {interval} minutes")
            self.notificationInterval = interval
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid notification interval: {value}. Using default (60 minutes)")
            self.notificationInterval = 60

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class ReportCache(Base):
    __tablename__ = "report_cache"
    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String, index=True)  # 'daily', 'weekly', 'monthly', etc.
    date = Column(String, index=True)  # ISO format date string
    report_data = Column(Text)  # JSON string of the report data
    created_at = Column(DateTime, default=datetime.utcnow)

    def get_report_data(self):
        """Return the report data as a Python object."""
        try:
            return json.loads(self.report_data) if self.report_data else {}
        except Exception as e:
            logger.error(f"Error parsing report data: {e}")
            return {}


# Ensure default settings exist
# Modify the initialization code
def init_default_settings(db: Session): # Takes a Session as an argument
    # db = SessionLocal() # Session is now passed in
    try:
        existing_settings = db.query(Settings).first()
        if not existing_settings:
            logger.info("No settings found, creating defaults in provided session.")
            default_settings = Settings() # Uses default values from model definition
            db.add(default_settings)
            db.commit()
            logger.info("Default settings committed.")
        else:
            logger.info(f"Found existing settings in provided session: {existing_settings.model_dump()}")
    except Exception as e:
        logger.error(f"Error initializing settings in provided session: {e}")
        db.rollback() # Rollback on error
    # finally:
        # db.close() # Caller manages session lifecycle

# Add database backup before any operations
def backup_database():
    """Create a timestamped backup of the database"""
    if os.path.exists(DB_PATH):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(BASE_DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"activity_logs.{timestamp}.db")
        try:
            import shutil
            shutil.copy2(DB_PATH, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")

# Add this right after imports
atexit.register(backup_database)

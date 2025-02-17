import os
import datetime
import json
import logging
import atexit
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect  # Add this import

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
def safe_init_database():
    """Initialize database without dropping existing tables"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    if not existing_tables:
        logger.info("No existing tables found, creating new database")
        Base.metadata.create_all(bind=engine)
    else:
        logger.info(f"Found existing tables: {existing_tables}")
        # Only create missing tables
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                logger.info(f"Creating missing table: {table.name}")
                table.create(bind=engine)

# Create a configured "SessionLocal" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models
Base = declarative_base()

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    group = Column(String, index=True)
    category = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    duration_minutes = Column(Integer)
    description = Column(String)

class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    notificationInterval = Column(Integer, default=60)
    audioDevice = Column(String, default="default")
    llmProvider = Column(String, default="LMStudio")
    openRouterApiKey = Column(String, default="")
    openRouterLLM = Column(String, default="")
    lmstudioEndpoint = Column(String, default='http://localhost:1234/v1')
    lmstudioModel = Column(String, default='default_model')
    categories = Column(Text, default=json.dumps([
        {
            "name": "Coding",
            "groups": ["ActivityReports project", "ColabsReview", "MultiAgent"]
        },
        {
            "name": "Training",
            "groups": ["NLP Course", "Deep Learning Specialization"]
        },
        {
            "name": "Research",
            "groups": ["Paper Reading: Transformer-XX", "Video: New Architecture"]
        },
        {
            "name": "Business",
            "groups": ["Project Bids", "Client Meetings"]
        },
        {
            "name": "Work&Finance",
            "groups": ["Unemployment", "Work-search", "Pensions-related"]
        }
    ]))

    def dict(self):
        """Convert model to dictionary including parsed categories"""
        return {
            "notificationInterval": int(self.notificationInterval),
            "audioDevice": str(self.audioDevice),
            "llmProvider": str(self.llmProvider),
            "openRouterApiKey": str(self.openRouterApiKey),
            "openRouterLLM": str(self.openRouterLLM),
            "lmstudioEndpoint": str(self.lmstudioEndpoint),
            "lmstudioModel": str(self.lmstudioModel),
            "categories": self.get_categories()
        }

    def get_categories(self):
        """Return the categories as a Python object."""
        try:
            return json.loads(self.categories) if self.categories else {}
        except Exception as e:
            logger.error(f"Error parsing categories: {e}")
            return {}

    def set_categories(self, categories):
        """Set the categories from a Python object."""
        logger.info(f"Setting categories to: {json.dumps(categories, indent=2)}")
        try:
            self.categories = json.dumps(categories)
        except Exception as e:
            logger.error(f"Error setting categories: {e}")
            self.categories = "{}"

    @property
    def notification_interval(self):
        return self.notificationInterval

    @notification_interval.setter
    def notification_interval(self, value):
        logger.info(f"Setting notification interval to: {value}")
        self.notificationInterval = int(value)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

# Initialize database and tables
safe_init_database()

# Ensure default settings exist
# Modify the initialization code
def init_default_settings():
    db = SessionLocal()
    try:
        existing_settings = db.query(Settings).first()
        if not existing_settings:
            logger.info("No settings found, creating defaults")
            default_settings = Settings()
            db.add(default_settings)
            db.commit()
        else:
            logger.info(f"Found existing settings: {existing_settings.dict()}")
    except Exception as e:
        logger.error(f"Error initializing settings: {e}")
    finally:
        db.close()

# Add database backup before any operations
def backup_database():
    """Create a timestamped backup of the database"""
    if os.path.exists(DB_PATH):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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

init_default_settings()
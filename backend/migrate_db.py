import os
import sqlite3
import logging
from models import SessionLocal, Settings, Base, engine, DB_PATH

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_settings():
    """Migrate database schema and update settings"""
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    logger.info("Ensured base tables exist")
    
    # First, try to add the column if it doesn't exist
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add all required columns if missing
        required_columns = {
            'lmstudioModel': 'TEXT DEFAULT "phi-4"',
            'llmProvider': 'TEXT DEFAULT "lmstudio"',
            'lmstudioEndpoint': 'TEXT DEFAULT "http://localhost:1234/v1"'
        }
        
        for column, definition in required_columns.items():
            if column not in columns:
                logger.info(f"Adding column: {column}")
                cursor.execute(f'ALTER TABLE settings ADD COLUMN {column} {definition}')
                conn.commit()
                logger.info(f"Added {column} successfully")
                
    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")
        return False
    finally:
        conn.close()

    # Now update settings with default values
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings:
            logger.info("Creating new settings...")
            settings = Settings(
                llmProvider="lmstudio",
                lmstudioEndpoint="http://localhost:1234/v1",
                lmstudioModel="phi-4"
            )
            db.add(settings)
        else:
            logger.info("Updating existing settings...")
            settings.lmstudioModel = "phi-4"
            settings.llmProvider = "lmstudio"
            settings.lmstudioEndpoint = "http://localhost:1234/v1"
        
        db.commit()
        
        # Verify the update
        settings = db.query(Settings).first()
        logger.info("Current settings:")
        logger.info(f"- LLM Provider: {settings.llmProvider}")
        logger.info(f"- LMStudio Endpoint: {settings.lmstudioEndpoint}")
        logger.info(f"- LMStudio Model: {settings.lmstudioModel}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = migrate_settings()
    if success:
        logger.info("Migration completed successfully")
    else:
        logger.error("Migration failed")
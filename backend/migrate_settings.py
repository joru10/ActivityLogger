import sqlite3
import logging
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the database path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "activity_logs.db")

def migrate_settings_table():
    """
    Add new columns to the settings table for LLM model selection.
    """
    logger.info(f"Migrating settings table in database: {DB_PATH}")
    
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if the columns already exist
        cursor.execute("PRAGMA table_info(settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add lmstudioLogsModel column if it doesn't exist
        if "lmstudioLogsModel" not in columns:
            logger.info("Adding lmstudioLogsModel column to settings table")
            cursor.execute('ALTER TABLE settings ADD COLUMN "lmstudioLogsModel" TEXT DEFAULT "phi-3-mini-4k"')
        else:
            logger.info("lmstudioLogsModel column already exists")
        
        # Add lmstudioReportsModel column if it doesn't exist
        if "lmstudioReportsModel" not in columns:
            logger.info("Adding lmstudioReportsModel column to settings table")
            cursor.execute('ALTER TABLE settings ADD COLUMN "lmstudioReportsModel" TEXT DEFAULT "gemma-7b"')
        else:
            logger.info("lmstudioReportsModel column already exists")
        
        # Commit the changes
        conn.commit()
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_settings_table()

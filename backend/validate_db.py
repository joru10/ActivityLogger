import os
import sqlite3
from models import DB_PATH, Base, engine

def validate_database():
    print(f"Validating database at: {DB_PATH}")
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print("Creating database and tables...")
        Base.metadata.create_all(bind=engine)
        return
    
    # Check tables
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Found tables: {[t[0] for t in tables]}")
    
    # Verify required tables exist
    required_tables = {'activity_logs', 'settings'}
    existing_tables = {t[0] for t in tables}
    
    if not required_tables.issubset(existing_tables):
        missing = required_tables - existing_tables
        print(f"Missing tables: {missing}")
        print("Creating missing tables...")
        Base.metadata.create_all(bind=engine)
    else:
        print("All required tables exist")
    
    conn.close()

if __name__ == "__main__":
    validate_database()
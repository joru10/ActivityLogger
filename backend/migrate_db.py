import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Define your database URL
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "activity_logs.db"
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
DATABASE_URL = f"sqlite:///{DB_PATH}"

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=create_engine(DATABASE_URL))

def migrate():
    with SessionLocal() as session:
        inspector = inspect(session.bind)
        if 'activity_logs' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('activity_logs')]
            if 'category' not in columns:
                with session.bind.connect() as conn:
                    conn.execute(text('ALTER TABLE activity_logs ADD COLUMN category VARCHAR;'))
                    print("Added 'category' column to 'activity_logs' table.")
            else:
                print("'category' column already exists in 'activity_logs' table.")
        else:
            print("Table 'activity_logs' does not exist.")

if __name__ == "__main__":
    migrate()
# models.py
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./activity_logs.db"  # The SQLite file will be created in the project root

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    group = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    duration_minutes = Column(Integer)
    description = Column(String)

# Create the table(s)
Base.metadata.create_all(bind=engine)
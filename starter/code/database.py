import os
import json
from sqlalchemy import create_engine, Column, String, Float, Boolean, Text, event
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./onboarding.db")

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30} if "sqlite" in DATABASE_URL else {}
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout = 30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class OnboardingRecord(Base):
    __tablename__ = "onboarding_records"

    id = Column(String, primary_key=True, index=True)
    status = Column(String, index=True)
    extracted_data = Column(Text)  # JSON string
    role_context = Column(Text)  # JSON string
    roadmap = Column(Text)
    notifications_sent = Column(Text)  # JSON string
    reviewer_name = Column(String, nullable=True)
    reviewer_notes = Column(String, nullable=True)
    created_at = Column(String)
    updated_at = Column(String)

class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(String)
    actor = Column(String)
    action = Column(String)
    record_id = Column(String, index=True)
    details = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    model_version = Column(String, nullable=True)
    override = Column(Boolean, default=False)

def init_db():
    Base.metadata.create_all(bind=engine)

import os
import json
from sqlalchemy import create_engine, Column, String, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./onboarding.db")

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
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

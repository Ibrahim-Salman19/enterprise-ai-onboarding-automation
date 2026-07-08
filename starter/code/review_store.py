"""
In-memory record store for onboarding records.

Provides thread-safe CRUD operations backed by a simple Python dictionary.
Designed for prototyping — swap with a database-backed implementation for
production use.
"""

import json
from typing import Optional
from database import SessionLocal, OnboardingRecord, engine, Base

def _to_dict(record: OnboardingRecord) -> dict:
    if not record:
        return None
    return {
        "record_id": record.id,
        "status": record.status,
        "extracted_data": json.loads(record.extracted_data) if record.extracted_data else {},
        "role_context": json.loads(record.role_context) if record.role_context else {},
        "roadmap": record.roadmap,
        "notifications_sent": json.loads(record.notifications_sent) if record.notifications_sent else {},
        "reviewer_name": record.reviewer_name,
        "reviewer_notes": record.reviewer_notes,
        "created_at": record.created_at,
        "updated_at": record.updated_at
    }

def save_record(record_id: str, record_data: dict) -> None:
    """
    Persist (insert or update) an onboarding record.
    """
    db = SessionLocal()
    try:
        record = db.query(OnboardingRecord).filter(OnboardingRecord.id == record_id).first()
        if not record:
            record = OnboardingRecord(id=record_id)
            db.add(record)
        
        record.status = record_data.get("status")
        record.extracted_data = json.dumps(record_data.get("extracted_data", {}))
        record.role_context = json.dumps(record_data.get("role_context", {}))
        record.roadmap = record_data.get("roadmap")
        record.notifications_sent = json.dumps(record_data.get("notifications_sent", {}))
        record.reviewer_name = record_data.get("reviewer_name")
        record.reviewer_notes = record_data.get("reviewer_notes")
        record.created_at = record_data.get("created_at")
        record.updated_at = record_data.get("updated_at")
        
        db.commit()
    finally:
        db.close()


def get_record(record_id: str) -> Optional[dict]:
    """
    Retrieve a single record by its ID.
    """
    db = SessionLocal()
    try:
        record = db.query(OnboardingRecord).filter(OnboardingRecord.id == record_id).first()
        return _to_dict(record)
    finally:
        db.close()


def list_records() -> list[dict]:
    """Return a list of all stored records (snapshot)."""
    db = SessionLocal()
    try:
        records = db.query(OnboardingRecord).all()
        return [_to_dict(r) for r in records]
    finally:
        db.close()


def list_pending() -> list[dict]:
    """Return only records whose status is ``pending_review``."""
    db = SessionLocal()
    try:
        records = db.query(OnboardingRecord).filter(OnboardingRecord.status == "pending_review").all()
        return [_to_dict(r) for r in records]
    finally:
        db.close()


def clear_store() -> None:
    """Remove all records. Primarily used by tests."""
    db = SessionLocal()
    try:
        db.query(OnboardingRecord).delete()
        db.commit()
    finally:
        db.close()

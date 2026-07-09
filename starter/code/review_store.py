"""
SQLite-backed onboarding record store via SQLAlchemy ORM.

Provides database CRUD operations for storing and managing employee
onboarding profiles.
"""

import json
import threading
from typing import Optional
from database import SessionLocal, OnboardingRecord, engine, Base

write_lock = threading.Lock()

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
            record.created_at = record_data.get("created_at")
            db.add(record)
        else:
            if not record.created_at and record_data.get("created_at"):
                record.created_at = record_data.get("created_at")
        
        record.status = record_data.get("status")
        record.extracted_data = json.dumps(record_data.get("extracted_data", {}))
        record.role_context = json.dumps(record_data.get("role_context", {}))
        record.roadmap = record_data.get("roadmap")
        record.notifications_sent = json.dumps(record_data.get("notifications_sent", {}))
        record.reviewer_name = record_data.get("reviewer_name")
        record.reviewer_notes = record_data.get("reviewer_notes")
        record.updated_at = record_data.get("updated_at")
        
        db.commit()
    except Exception:
        db.rollback()
        raise
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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_stats() -> dict:
    """Return aggregated statistics of the records."""
    all_records = list_records()
    stats = {
        "total": len(all_records),
        "pending_review": 0,
        "approved": 0,
        "rejected": 0,
        "auto_approved": 0,
        "offboarded": 0,
        "by_department": {}
    }
    
    for r in all_records:
        status = r.get("status", "unknown")
        if status in stats:
            stats[status] += 1
            
        dept = r.get("extracted_data", {}).get("department", "Unknown")
        if dept not in stats["by_department"]:
            stats["by_department"][dept] = 0
        stats["by_department"][dept] += 1
        
    return stats

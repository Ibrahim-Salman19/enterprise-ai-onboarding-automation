"""
Audit logging module for the onboarding automation system.

Every significant action (extraction, approval, rejection, notification) is
recorded with full traceability metadata including actor identity, confidence
scores, model version, and override flags.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from database import SessionLocal, AuditEntry

def append_audit(
    actor: str,
    action: str,
    record_id: str,
    details: Optional[str] = None,
    confidence: Optional[float] = None,
    model_version: Optional[str] = None,
    override: bool = False,
) -> dict:
    """
    Append an entry to the audit log.
    """
    db = SessionLocal()
    try:
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        entry = AuditEntry(
            id=entry_id,
            timestamp=timestamp,
            actor=actor,
            action=action,
            record_id=record_id,
            details=details,
            confidence=confidence,
            model_version=model_version,
            override=override
        )
        db.add(entry)
        db.commit()
        
        return {
            "id": entry_id,
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "record_id": record_id,
            "details": details,
            "confidence": confidence,
            "model_version": model_version,
            "override": override,
        }
    finally:
        db.close()


def get_audit_log() -> list[dict]:
    """Return a snapshot of the full audit log."""
    db = SessionLocal()
    try:
        entries = db.query(AuditEntry).order_by(AuditEntry.timestamp).all()
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "actor": e.actor,
                "action": e.action,
                "record_id": e.record_id,
                "details": e.details,
                "confidence": e.confidence,
                "model_version": e.model_version,
                "override": e.override,
            }
            for e in entries
        ]
    finally:
        db.close()


def clear_audit_log() -> None:
    """Remove all audit entries. Primarily used by tests."""
    db = SessionLocal()
    try:
        db.query(AuditEntry).delete()
        db.commit()
    finally:
        db.close()

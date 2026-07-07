"""
Audit logging module for the onboarding automation system.

Every significant action (extraction, approval, rejection, notification) is
recorded with full traceability metadata including actor identity, confidence
scores, model version, and override flags.
"""

import threading
from datetime import datetime, timezone
from typing import Optional

# ── Module-level state ──────────────────────────────────────────────────────
_audit_log: list[dict] = []
_lock = threading.Lock()


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

    Args:
        actor:          Who performed the action (e.g. "system", user email).
        action:         What happened (e.g. "intake_extracted", "approved").
        record_id:      The onboarding record this action relates to.
        details:        Free-text description or context.
        confidence:     LLM confidence score (0-1), if applicable.
        model_version:  Identifier of the LLM model used.
        override:       ``True`` when a human overrides an automated decision.

    Returns:
        The newly created audit entry dict.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "record_id": record_id,
        "details": details,
        "confidence": confidence,
        "model_version": model_version,
        "override": override,
    }
    with _lock:
        _audit_log.append(entry)
    return entry


def get_audit_log() -> list[dict]:
    """Return a snapshot of the full audit log."""
    with _lock:
        return list(_audit_log)


def clear_audit_log() -> None:
    """Remove all audit entries.  Primarily used by tests."""
    with _lock:
        _audit_log.clear()

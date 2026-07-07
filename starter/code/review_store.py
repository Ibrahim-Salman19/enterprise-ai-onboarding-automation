"""
In-memory record store for onboarding records.

Provides thread-safe CRUD operations backed by a simple Python dictionary.
Designed for prototyping — swap with a database-backed implementation for
production use.
"""

import threading
from typing import Optional

# ── Module-level state ──────────────────────────────────────────────────────
_store: dict[str, dict] = {}
_lock = threading.Lock()


def save_record(record_id: str, record_data: dict) -> None:
    """
    Persist (insert or update) an onboarding record.

    Args:
        record_id: Unique identifier for the record.
        record_data: Full record payload to store.
    """
    with _lock:
        _store[record_id] = record_data


def get_record(record_id: str) -> Optional[dict]:
    """
    Retrieve a single record by its ID.

    Returns:
        The record dict if found, otherwise ``None``.
    """
    with _lock:
        return _store.get(record_id)


def list_records() -> list[dict]:
    """Return a list of all stored records (snapshot)."""
    with _lock:
        return list(_store.values())


def list_pending() -> list[dict]:
    """Return only records whose status is ``pending_review``."""
    with _lock:
        return [r for r in _store.values() if r.get("status") == "pending_review"]


def clear_store() -> None:
    """Remove all records.  Primarily used by tests."""
    with _lock:
        _store.clear()

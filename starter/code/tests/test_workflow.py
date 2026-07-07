"""
Automated pytest suite for the onboarding automation FastAPI application.

Uses FastAPI TestClient and overrides the OpenAI LLM client dependency to run
fully offline, deterministic, and fast integration tests.
"""

import json
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from main import app, get_llm_client_dependency
import review_store
import audit_log


# ── LLM Client Mocking Setup ────────────────────────────────────────────────
class MockChatCompletions:
    """Mock for client.chat.completions object."""
    def __init__(self):
        # Default high-confidence extraction response
        self.default_extraction = {
            "name": "Ayesha Raza",
            "email": "ayesha.raza@gmail.com",
            "role": "Backend Engineer",
            "department": "Engineering",
            "manager": "Sarah Chen",
            "start_date": "2026-07-15",
            "confidence_score": 0.95,
            "missing_fields": []
        }
        
        # Default low-confidence extraction response
        self.low_confidence_extraction = {
            "name": "John Doe",
            "email": "invalid-email",
            "role": "Analyst",
            "department": "Unknown",
            "manager": "",
            "start_date": "bad-date",
            "confidence_score": 0.45,
            "missing_fields": ["email", "manager", "start_date"]
        }

        self.roadmap_response = (
            "# Welcome to the Team, Onboardee!\n\n"
            "## 30-Day Focus (Integration & Learning)\n- Learn systems.\n\n"
            "## 60-Day Focus\n- Small wins.\n\n"
            "## 90-Day Focus\n- Independence."
        )

    def create(self, **kwargs):
        """Mock the ChatCompletions.create method."""
        messages = kwargs.get("messages", [])
        
        # Identify whether this is an extraction or roadmap completion
        is_extraction = False
        system_msg = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
            if "extract" in msg.get("content", "").lower() or "verify" in msg.get("content", "").lower():
                is_extraction = True

        # Extract user input message text
        user_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")

        # Compute output content
        if is_extraction or "onboarding data extraction" in system_msg.lower():
            # Trigger low-confidence mock if specific flags are present in user text
            if "anomaly" in user_msg.lower() or "bad data" in user_msg.lower() or "invalid" in user_msg.lower():
                content = json.dumps(self.low_confidence_extraction)
            else:
                content = json.dumps(self.default_extraction)
        else:
            content = self.roadmap_response

        # Build Mock API response structure
        mock_choice = MagicMock()
        mock_choice.message.content = content
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response


class MockOpenAIClient:
    """Mock for OpenAI client class."""
    def __init__(self):
        self.chat = MagicMock()
        self.chat.completions = MockChatCompletions()


# ── Pytest Fixtures ─────────────────────────────────────────────────────────
@pytest.fixture
def mock_client():
    """Provides a fresh instance of the Mock LLM Client."""
    return MockOpenAIClient()


@pytest.fixture
def client(mock_client):
    """Provides a TestClient with overridden LLM dependency."""
    # Reset internal memory state between runs
    review_store.clear_store()
    audit_log.clear_audit_log()

    # Apply FastAPI dependency override
    def override_dependency():
        return mock_client

    app.dependency_overrides[get_llm_client_dependency] = override_dependency
    with TestClient(app) as c:
        yield c
    # Clean up overrides
    app.dependency_overrides.clear()


# ── Test Cases ──────────────────────────────────────────────────────────────
def test_health_check(client):
    """Health endpoint returns 200 and references configured model name."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "model_name" in data


def test_intake_high_confidence(client):
    """High-confidence inputs bypass manual queue and are automatically approved."""
    payload = {
        "raw_text": "Ayesha Raza, ayesha.raza@gmail.com, Backend Engineer, Engineering, Islamabad, manager Sarah Chen, starts 2026-07-15"
    }
    response = client.post("/intake", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Assert state routing logic
    assert data["status"] == "auto_approved"
    assert "record_id" in data
    assert data["extracted_data"]["name"] == "Ayesha Raza"
    assert "roadmap" in data
    assert "# Welcome to the Team" in data["roadmap"]
    assert "notifications_sent" in data
    assert "slack" in data["notifications_sent"]


def test_intake_low_confidence(client):
    """Low-confidence inputs must trigger a manual review routing flag."""
    payload = {
        "raw_text": "Some bad data with anomalies like missing emails and broken syntax"
    }
    response = client.post("/intake", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Assert routing logic
    assert data["status"] == "pending_review"
    assert "record_id" in data
    assert data["roadmap"] == ""  # Roadmap not generated yet
    assert data["notifications_sent"] == {}  # No onboarding provisioning sent yet


def test_intake_empty_input(client):
    """Submitting empty string raw_text returns a validation 422 HTTP error."""
    response = client.post("/intake", json={"raw_text": ""})
    assert response.status_code == 422
    assert "raw_text cannot be empty" in response.json()["detail"]


def test_intake_whitespace_only(client):
    """Submitting whitespace-only raw_text returns a validation 422 HTTP error."""
    response = client.post("/intake", json={"raw_text": "   \n   "})
    assert response.status_code == 422
    assert "raw_text cannot be empty" in response.json()["detail"]


def test_approve_flow(client):
    """Reviewing and approving a pending record transitions status and generates roadmap."""
    # 1. Trigger low confidence record creation
    r1 = client.post("/intake", json={"raw_text": "intake anomaly detected"})
    assert r1.status_code == 200
    record_id = r1.json()["record_id"]

    # 2. POST to approve endpoint
    approval_payload = {
        "decision": "approve",
        "approved_by": "HR Director",
        "notes": "Verified details with candidate manually."
    }
    r2 = client.post(f"/approve/{record_id}", json=approval_payload)
    assert r2.status_code == 200
    data = r2.json()

    # 3. Verify final state and audit log update
    assert data["status"] == "approved"
    assert data["reviewer_name"] == "HR Director"
    assert "# Welcome to the Team" in data["roadmap"]
    assert "slack" in data["notifications_sent"]

    # Check audit log trail
    audit_response = client.get("/audit")
    assert audit_response.status_code == 200
    audit_entries = audit_response.json()
    # Should have two entries: intake queue + manual approval override
    assert len(audit_entries) == 2
    assert audit_entries[0]["action"] == "intake_queued_review"
    assert audit_entries[1]["action"] == "manual_approved"
    assert audit_entries[1]["override"] is True  # Override flag set to true for HITL actions
    assert audit_entries[1]["actor"] == "HR Director"


def test_reject_flow(client):
    """Reviewing and rejecting a pending record transitions status to rejected."""
    # 1. Queue record
    r1 = client.post("/intake", json={"raw_text": "intake anomaly detected"})
    record_id = r1.json()["record_id"]

    # 2. Reject candidate
    reject_payload = {
        "decision": "reject",
        "approved_by": "HR Recruiter",
        "notes": "Failed verification."
    }
    r2 = client.post(f"/approve/{record_id}", json=reject_payload)
    assert r2.status_code == 200
    data = r2.json()

    assert data["status"] == "rejected"
    assert data["roadmap"] == ""
    assert data["notifications_sent"] == {}

    # Audit log check
    audit_entries = client.get("/audit").json()
    assert audit_entries[-1]["action"] == "manual_rejected"
    assert audit_entries[-1]["override"] is True


def test_approve_not_found(client):
    """Approving a nonexistent record ID returns a 404 HTTP Error."""
    payload = {"decision": "approve", "approved_by": "System Admin", "notes": ""}
    response = client.post("/approve/nonexistent-uuid", json=payload)
    assert response.status_code == 404


def test_approve_conflict_state(client):
    """Attempting to approve an already auto-approved record returns a 409 Conflict Error."""
    # 1. Intake auto-approved record
    payload = {
        "raw_text": "Ayesha Raza, ayesha.raza@gmail.com, Backend Engineer, Engineering, Islamabad, manager Sarah Chen, starts 2026-07-15"
    }
    r1 = client.post("/intake", json=payload)
    record_id = r1.json()["record_id"]

    # 2. Attempt to override
    approval_payload = {"decision": "approve", "approved_by": "HR", "notes": "Double check"}
    r2 = client.post(f"/approve/{record_id}", json=approval_payload)
    assert r2.status_code == 409
    assert "expected 'pending_review'" in r2.json()["detail"]


def test_list_records(client):
    """Records list endpoint returns all stored records correctly."""
    # Add one auto-approved
    client.post("/intake", json={"raw_text": "Ayesha Raza, ayesha.raza@gmail.com"})
    # Add one review-queued
    client.post("/intake", json={"raw_text": "intake anomaly detected"})

    response = client.get("/records")
    assert response.status_code == 200
    records = response.json()
    assert len(records) == 2

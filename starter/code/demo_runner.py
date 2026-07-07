"""
Demo Runner for AI Onboarding Automation system.

Simulates a real-world user workflow (intake, routing, manual review, auditing)
by using the FastAPI TestClient and overriding the LLM provider dependency to run
100% offline without requiring a real Groq API key.
"""

import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Import app components
from main import app, get_llm_client_dependency
import review_store
import audit_log


# ── Mock LLM Client Setup ───────────────────────────────────────────────────
class MockChatCompletions:
    def __init__(self):
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
            "## 30-Day Focus (Integration & Learning)\n"
            "- Set up GitHub, AWS Console, and local dev environments.\n"
            "- Complete Code Review Standards module.\n\n"
            "## 60-Day Focus (Collaboration & Small Wins)\n"
            "- Shadow process sessions and pick up initial starter tickets.\n\n"
            "## 90-Day Focus (Independence & Contribution)\n"
            "- Assume full ownership of assigned backend microservices."
        )

    def create(self, **kwargs):
        messages = kwargs.get("messages", [])
        is_extraction = False
        for msg in messages:
            if "extract" in msg.get("content", "").lower() or "verify" in msg.get("content", "").lower():
                is_extraction = True

        user_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")

        if is_extraction:
            if "bad" in user_msg.lower() or "broken" in user_msg.lower() or "anomaly" in user_msg.lower():
                content = json.dumps(self.low_confidence_extraction)
            else:
                content = json.dumps(self.default_extraction)
        else:
            content = self.roadmap_response

        mock_choice = MagicMock()
        mock_choice.message.content = content
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response


class MockOpenAIClient:
    def __init__(self):
        self.chat = MagicMock()
        self.chat.completions = MockChatCompletions()


# Apply dependency override
def override_dependency():
    return MockOpenAIClient()


app.dependency_overrides[get_llm_client_dependency] = override_dependency
client = TestClient(app)

# Reset stores
review_store.clear_store()
audit_log.clear_audit_log()


def run_demo():
    print("=" * 80)
    print("                 AI ONBOARDING AUTOMATION API DEMO WORKFLOW")
    print("=" * 80)
    print()

    # ── 1. Health Check ──────────────────────────────────────────────────────
    print("STEP 1: Checking System Health...")
    r_health = client.get("/health")
    print(f"Status Code: {r_health.status_code}")
    print(json.dumps(r_health.json(), indent=2))
    print("-" * 80)

    # ── 2. High-Confidence Auto-Approval Intake ──────────────────────────────
    print("\nSTEP 2: Processing High-Confidence Candidate (Auto-Approval Path)...")
    payload_high = {
        "raw_text": "Ayesha Raza, ayesha.raza@gmail.com, Backend Engineer, Engineering, starts 2026-07-15, manager Sarah Chen"
    }
    r_intake1 = client.post("/intake", json=payload_high)
    print(f"Status Code: {r_intake1.status_code}")
    res_intake1 = r_intake1.json()
    print(f"Candidate Name: {res_intake1['extracted_data']['name']}")
    print(f"Assigned Status: {res_intake1['status']}")
    print("\nSynthesized Roadmap Generated:")
    print(res_intake1["roadmap"])
    print("\nProvisioning Notifications:")
    print(json.dumps(res_intake1["notifications_sent"], indent=2))
    print("-" * 80)

    # ── 3. Low-Confidence Intake (Queued for Manual Review) ─────────────────
    print("\nSTEP 3: Processing Low-Confidence Candidate (Manual Review Path)...")
    payload_low = {
        "raw_text": "Intake anomaly: John Doe with missing manager details and broken formatting..."
    }
    r_intake2 = client.post("/intake", json=payload_low)
    print(f"Status Code: {r_intake2.status_code}")
    res_intake2 = r_intake2.json()
    record_id_low = res_intake2["record_id"]
    print(f"Candidate Name: {res_intake2['extracted_data']['name'] or 'John Doe (Extracted Name Missing)'}")
    print(f"Assigned Status: {res_intake2['status']}")
    print(f"Record ID Generated: {record_id_low}")
    print(f"Roadmap Present?: {'Yes' if res_intake2['roadmap'] else 'No (Roadmap empty while pending)'}")
    print("-" * 80)

    # ── 4. Human-in-the-Loop Review & Approval ───────────────────────────────
    print(f"\nSTEP 4: Reviewing and Approving Record ID: {record_id_low}...")
    approval_payload = {
        "decision": "approve",
        "approved_by": "HR Director (Ibrahim)",
        "notes": "Spoke to candidate, verified start date and email manually."
    }
    r_approve = client.post(f"/approve/{record_id_low}", json=approval_payload)
    print(f"Status Code: {r_approve.status_code}")
    res_approve = r_approve.json()
    print(f"Updated Status: {res_approve['status']}")
    print(f"Reviewer Name: {res_approve['reviewer_name']}")
    print(f"Reviewer Notes: {res_approve['reviewer_notes']}")
    print("\nSynthesized Roadmap Generated after Human Approval:")
    print(res_approve["roadmap"])
    print("-" * 80)

    # ── 5. Auditing Trail View ───────────────────────────────────────────────
    print("\nSTEP 5: Retrieving chronological Audit Log Trail...")
    r_audit = client.get("/audit")
    print(f"Status Code: {r_audit.status_code}")
    audit_entries = r_audit.json()
    for idx, entry in enumerate(audit_entries, 1):
        print(f"\nEntry #{idx}:")
        print(f"  Timestamp:     {entry['timestamp']}")
        print(f"  Actor:         {entry['actor']}")
        print(f"  Action:        {entry['action']}")
        print(f"  Record ID:     {entry['record_id']}")
        print(f"  Details:       {entry['details']}")
        print(f"  Confidence:    {entry['confidence']}")
        print(f"  Model:         {entry['model_version']}")
        print(f"  Override Flag: {entry['override']}")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()

"""
Role context provider for the onboarding automation system.

Supplies department-specific onboarding metadata (manager, systems access,
training modules, buddy program) used to personalise the 30-60-90 day plan.
"""

from typing import Any

# ── Department → Role Context Lookup Table ──────────────────────────────────
_ROLE_CONTEXTS: dict[str, dict[str, Any]] = {
    "Engineering": {
        "manager_name": "Sarah Chen",
        "team_size": 12,
        "required_systems": [
            "GitHub Enterprise",
            "Jira",
            "AWS Console",
            "Confluence",
            "Slack Engineering Channels",
        ],
        "training_modules": [
            "Code Review Standards",
            "CI/CD Pipeline Overview",
            "Security & Compliance Basics",
            "Architecture Decision Records",
        ],
        "buddy_program": True,
    },
    "Marketing": {
        "manager_name": "James Rodriguez",
        "team_size": 8,
        "required_systems": [
            "HubSpot",
            "Google Analytics",
            "Figma",
            "Hootsuite",
            "Slack Marketing Channels",
        ],
        "training_modules": [
            "Brand Guidelines",
            "Content Strategy Framework",
            "Campaign Workflow",
            "Analytics & Reporting",
        ],
        "buddy_program": True,
    },
    "Finance": {
        "manager_name": "Priya Patel",
        "team_size": 6,
        "required_systems": [
            "SAP",
            "NetSuite",
            "Tableau",
            "Concur",
            "Slack Finance Channels",
        ],
        "training_modules": [
            "Financial Controls & SOX Compliance",
            "Budget Management Process",
            "Expense Policy Overview",
            "Quarter-End Close Procedures",
        ],
        "buddy_program": False,
    },
    "Human Resources": {
        "manager_name": "Michael Thompson",
        "team_size": 5,
        "required_systems": [
            "Workday",
            "BambooHR",
            "LinkedIn Recruiter",
            "DocuSign",
            "Slack HR Channels",
        ],
        "training_modules": [
            "Employment Law Fundamentals",
            "Diversity & Inclusion Training",
            "Benefits Administration",
            "Performance Review Framework",
        ],
        "buddy_program": True,
    },
}

# Sensible fallback for departments not in the lookup table
_DEFAULT_CONTEXT: dict[str, Any] = {
    "manager_name": "To Be Assigned",
    "team_size": 0,
    "required_systems": [
        "Google Workspace",
        "Slack",
        "Confluence",
    ],
    "training_modules": [
        "Company Orientation",
        "IT Security Awareness",
        "Code of Conduct",
    ],
    "buddy_program": True,
}


def get_role_context(department: str, job_title: str | None = None) -> dict[str, Any]:
    """
    Return department-specific onboarding context.

    Args:
        department: Department name (case-insensitive lookup).
        job_title:  Currently unused but available for future specialisation.

    Returns:
        Dict with keys: ``manager_name``, ``team_size``, ``required_systems``,
        ``training_modules``, ``buddy_program``.
    """
    # Normalise the department name for a case-insensitive, whitespace-tolerant match
    normalised = department.strip().title() if department else ""
    context = _ROLE_CONTEXTS.get(normalised, _DEFAULT_CONTEXT).copy()
    context["department"] = normalised or "Unknown"
    context["job_title"] = job_title or "Not Specified"
    return context

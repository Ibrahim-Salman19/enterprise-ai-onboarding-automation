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
        "manager_slack_handle": "@sarah.chen",
        "it_channel": "#it-provisioning",
        "announcements_channel": "#new-joiners",
        "manager_email": "sarah.chen@company.com",
        "default_buddy_pool": ["Alex Dev", "Jamie Coder"],
        "hardware_provisioning": "MacBook Pro M3 Max 32GB"
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
        "manager_slack_handle": "@james.r",
        "it_channel": "#it-provisioning",
        "announcements_channel": "#new-joiners",
        "manager_email": "james.rodriguez@company.com",
        "default_buddy_pool": ["Casey Marketer", "Sam Writer"],
        "hardware_provisioning": "MacBook Air M3 16GB"
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
        "manager_slack_handle": "@priya.p",
        "it_channel": "#it-provisioning",
        "announcements_channel": "#new-joiners",
        "manager_email": "priya.patel@company.com",
        "default_buddy_pool": [],
        "hardware_provisioning": "ThinkPad T14 Gen 4"
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
        "manager_slack_handle": "@michael.t",
        "it_channel": "#it-provisioning",
        "announcements_channel": "#new-joiners",
        "manager_email": "michael.thompson@company.com",
        "default_buddy_pool": ["Taylor HR", "Jordan Ops"],
        "hardware_provisioning": "ThinkPad T14 Gen 4"
    },
    "Sales": {
        "manager_name": "Marcus Vance",
        "team_size": 15,
        "required_systems": [
            "Salesforce",
            "LinkedIn Sales Navigator",
            "Gong.io",
            "Slack Sales Channels",
            "ZoomInfo",
        ],
        "training_modules": [
            "Sales Playbook & Pitching",
            "Product Demonstration Training",
            "CRM Best Practices",
            "Negotiation Techniques",
        ],
        "buddy_program": True,
        "manager_slack_handle": "@marcus.v",
        "it_channel": "#it-provisioning",
        "announcements_channel": "#new-joiners",
        "manager_email": "marcus.vance@company.com",
        "default_buddy_pool": ["Taylor Closer", "Jordan Seller"],
        "hardware_provisioning": "ThinkPad T14 Gen 4"
    },
    "Legal": {
        "manager_name": "Elena Rostova",
        "team_size": 4,
        "required_systems": [
            "DocuSign",
            "Ironclad CLM",
            "LexisNexis",
            "Slack Legal Channels",
        ],
        "training_modules": [
            "Contract Guidelines & Templates",
            "Corporate Governance Overview",
            "Intellectual Property Policy",
            "Data Privacy & GDPR Basics",
        ],
        "buddy_program": False,
        "manager_slack_handle": "@elena.r",
        "it_channel": "#it-provisioning",
        "announcements_channel": "#new-joiners",
        "manager_email": "elena.rostova@company.com",
        "default_buddy_pool": [],
        "hardware_provisioning": "MacBook Air M3 16GB"
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
    "manager_slack_handle": "@manager",
    "it_channel": "#it-provisioning",
    "announcements_channel": "#new-joiners",
    "manager_email": "manager@company.com",
    "default_buddy_pool": ["Default Buddy"],
    "hardware_provisioning": "Standard Laptop Provisioning"
}


# Department alias mapping to normalize common synonyms/abbreviations to official keys
_DEPARTMENT_ALIASES: dict[str, str] = {
    "Hr": "Human Resources",
    "Hris": "Human Resources",
    "Humanresource": "Human Resources",
    "Humanresources": "Human Resources",
    "Eng": "Engineering",
    "Software Engineering": "Engineering",
    "Dev": "Engineering",
    "Development": "Engineering",
    "Mktg": "Marketing",
    "Fin": "Finance",
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
    # Safe type check and conversion to string
    if not isinstance(department, str):
        dept_str = str(department) if department is not None else ""
    else:
        dept_str = department

    # Normalise the department name for a case-insensitive, whitespace-tolerant match
    normalised = dept_str.strip().title() if dept_str else ""
    
    # Resolve aliases to standard department names
    if normalised in _DEPARTMENT_ALIASES:
        normalised = _DEPARTMENT_ALIASES[normalised]

    context = _ROLE_CONTEXTS.get(normalised, _DEFAULT_CONTEXT).copy()
    context["department"] = normalised or "Unknown"
    context["job_title"] = job_title or "Not Specified"
    return context

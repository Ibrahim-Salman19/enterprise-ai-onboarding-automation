"""
Validation and routing logic for the onboarding automation system.

Performs schema-level check validations (length, email regex, date format)
and computes routing decisions (auto_approve vs manual_review) based on validation
pass state and LLM confidence thresholds.
"""

import re
from datetime import datetime

# Simple RFC 5322 compatible email regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_extracted_data(data: dict) -> tuple[bool, list[str]]:
    """
    Validate the dictionary of extracted fields.

    Args:
        data: Dict containing extracted employee details.

    Returns:
        A tuple of (is_valid, issues_list).
    """
    issues = []

    # 1. Required field checks
    required_fields = ["name", "email", "role", "department", "start_date"]
    for field in required_fields:
        val = data.get(field)
        if not val or not str(val).strip():
            issues.append(f"Missing required field: {field}")

    # 2. Name validation (minimum length 2)
    name = data.get("name", "")
    if name and len(name.strip()) < 2:
        issues.append("Name must be at least 2 characters.")

    # 3. Email format verification
    email = data.get("email", "")
    if email and not EMAIL_REGEX.match(email.strip()):
        issues.append(f"Invalid email format: '{email}'")

    # 4. Start date format (YYYY-MM-DD)
    start_date = data.get("start_date", "")
    if start_date:
        try:
            datetime.strptime(start_date.strip(), "%Y-%m-%d")
        except ValueError:
            issues.append(f"Invalid start_date format '{start_date}'; must be YYYY-MM-DD")

    return (len(issues) == 0), issues


def route_decision(data: dict, confidence_threshold: float = 0.80) -> str:
    """
    Determine if a record can be automatically approved or needs manual review.

    Args:
        data:                 Dict containing extracted employee details.
        confidence_threshold: Configured score threshold for auto-approval.

    Returns:
        "auto_approve" or "manual_review".
    """
    # Run validation checks
    is_valid, issues = validate_extracted_data(data)
    if not is_valid:
        return "manual_review"

    # Check for missing fields list
    missing_fields = data.get("missing_fields", [])
    if missing_fields:
        return "manual_review"

    # Check LLM extraction confidence score
    confidence = data.get("confidence_score", 0.0)
    if confidence < confidence_threshold:
        return "manual_review"

    return "auto_approve"

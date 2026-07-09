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


def check_prompt_injection(text: str) -> bool:
    """
    Check if the input text contains potential prompt injection patterns.
    Returns True if potential injection is detected.
    """
    if not text:
        return False
    
    # Common prompt injection patterns (case-insensitive)
    patterns = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?instructions\s+above",
        r"system\s+prompt",
        r"you\s+are\s+now\s+a",
        r"new\s+instruction",
        r"override\s+the\s+system",
        r"instead\s+of\s+extracting",
        r"disregard\s+the\s+above",
        r"do\s+not\s+follow",
        r"forget\s+what\s+you",
        r"return\s+name\s+as\s+hacked",
    ]
    
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return True
            
    return False


def validate_extracted_data(data: dict) -> tuple[bool, list[str]]:
    """
    Validate the dictionary of extracted fields.

    Args:
        data: Dict containing extracted employee details.

    Returns:
        A tuple of (is_valid, issues_list).
    """
    issues = []

    # Clean string inputs in-place to ensure database gets sanitized values
    # Also strip null bytes to prevent injection/database issues
    for k, v in list(data.items()):
        if isinstance(v, str):
            data[k] = v.replace("\x00", "").strip()

    # 1. Required field checks
    required_fields = ["name", "email", "role", "department", "start_date"]
    for field in required_fields:
        val = data.get(field)
        if val is None or val == "":
            issues.append(f"Missing required field: {field}")
        elif not isinstance(val, str):
            issues.append(f"Invalid type for field: {field}")

    # 2. Name validation (minimum length 2, maximum length 100)
    name = data.get("name")
    if name and isinstance(name, str):
        if len(name) < 2:
            issues.append("Name must be at least 2 characters.")
        elif len(name) > 100:
            issues.append("Name must not exceed 100 characters.")

    # 3. Email format verification (maximum length 254)
    email = data.get("email")
    if email and isinstance(email, str):
        if len(email) > 254:
            issues.append("Email must not exceed 254 characters.")
        elif not EMAIL_REGEX.match(email):
            issues.append(f"Invalid email format: '{email}'")

    # 4. Start date format (YYYY-MM-DD)
    start_date = data.get("start_date")
    if start_date and isinstance(start_date, str):
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            issues.append(f"Invalid start_date format '{start_date}'; must be YYYY-MM-DD")

    return (len(issues) == 0), issues


def route_decision(data: dict, confidence_threshold: float = 0.80) -> str:
    """
    Determine if a record can be automatically approved or needs manual review.

    Args:
        data:                 Dict containing extracted employee details.
        confidence_threshold: Configured score threshold for auto-approval.

    Returns:
        "auto_approved" or "pending_review".
    """
    # Run validation checks
    is_valid, issues = validate_extracted_data(data)
    if not is_valid:
        return "pending_review"

    # Check for missing fields list
    missing_fields = data.get("missing_fields", [])
    if missing_fields:
        return "pending_review"

    # Check LLM extraction confidence score
    confidence = data.get("confidence_score")
    try:
        confidence = float(confidence) if confidence is not None else 0.0
    except (TypeError, ValueError):
        confidence = 0.0

    if confidence < confidence_threshold:
        return "pending_review"

    return "auto_approved"

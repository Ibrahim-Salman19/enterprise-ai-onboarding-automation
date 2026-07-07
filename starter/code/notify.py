"""
Mock notification service for the onboarding automation system.

All functions simulate real integrations (Slack, email, calendar) by logging
clearly prefixed ``[MOCK]`` messages.  Replace with real SDK calls for
production deployment.
"""

import logging

logger = logging.getLogger(__name__)


def send_slack_notification(record_data: dict) -> str:
    """
    Send a mock Slack notification about the new hire.

    Args:
        record_data: Onboarding record containing at least ``full_name``.

    Returns:
        Human-readable confirmation string.
    """
    name = record_data.get("full_name", "Unknown")
    message = f"[MOCK] Slack notification sent for {name}"
    logger.info(message)
    print(message)
    return message


def send_welcome_email(record_data: dict) -> str:
    """
    Send a mock welcome email to the new hire.

    Args:
        record_data: Onboarding record containing at least ``personal_email``.

    Returns:
        Human-readable confirmation string.
    """
    email = record_data.get("personal_email", record_data.get("company_email", "unknown@example.com"))
    message = f"[MOCK] Welcome email sent to {email}"
    logger.info(message)
    print(message)
    return message


def send_calendar_events(record_data: dict) -> str:
    """
    Schedule mock calendar events (orientation, 1:1s) for the new hire.

    Args:
        record_data: Onboarding record containing at least ``full_name``.

    Returns:
        Human-readable confirmation string.
    """
    name = record_data.get("full_name", "Unknown")
    message = f"[MOCK] Calendar events scheduled for {name}"
    logger.info(message)
    print(message)
    return message


def send_all_notifications(record_data: dict) -> dict:
    """
    Dispatch all mock notifications in one call.

    Returns:
        Summary dict with keys ``slack``, ``email``, ``calendar``.
    """
    return {
        "slack": send_slack_notification(record_data),
        "email": send_welcome_email(record_data),
        "calendar": send_calendar_events(record_data),
    }

"""
Notification service for the onboarding automation system.

Uses real integrations (Slack via Webhook, Email via Resend) if keys are provided.
Falls back to logging [MOCK] messages if keys are missing or API calls fail.
"""

import logging
import requests
import resend
from config import SLACK_WEBHOOK_URL, RESEND_API_KEY

logger = logging.getLogger(__name__)


def _candidate_name(record_data: dict) -> str:
    """Best-effort candidate name from an extraction/record dict."""
    return (record_data.get("name") or record_data.get("full_name") or "Unknown").strip() or "Unknown"


def _candidate_email(record_data: dict) -> str:
    """Best-effort candidate email from an extraction/record dict."""
    return (
        record_data.get("email")
        or record_data.get("personal_email")
        or record_data.get("company_email")
        or "unknown@example.com"
    ).strip() or "unknown@example.com"


def send_slack_notification(record_data: dict) -> str:
    """
    Send a Slack notification about the new hire.
    """
    name = _candidate_name(record_data)
    role = record_data.get("role", "New Hire")
    department = record_data.get("department", "their team")
    
    if SLACK_WEBHOOK_URL:
        try:
            payload = {
                "text": f"🎉 Welcome {name} to {department} as our new {role}! 🚀"
            }
            response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
            response.raise_for_status()
            message = f"Slack notification sent for {name} via webhook"
            logger.info(message)
            return message
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            
    # Fallback to mock
    message = f"[MOCK] Slack notification sent for {name}"
    logger.info(message)
    print(message)
    return message


def send_welcome_email(record_data: dict) -> str:
    """
    Send a welcome email to the new hire via Resend.
    """
    email = _candidate_email(record_data)
    name = _candidate_name(record_data)
    
    if RESEND_API_KEY and email != "unknown@example.com":
        resend.api_key = RESEND_API_KEY
        try:
            # Using a default testing sender domain from Resend or you can configure a real one
            params = {
                "from": "onboarding@resend.dev",
                "to": [email],
                "subject": f"Welcome to the Team, {name}!",
                "html": f"<strong>Welcome {name}!</strong> We are excited to have you on board. Your onboarding roadmap is attached to your employee profile."
            }
            email_response = resend.Emails.send(params)
            message = f"Welcome email sent to {email} via Resend (ID: {email_response.get('id', 'unknown')})"
            logger.info(message)
            return message
        except Exception as e:
            logger.error(f"Failed to send welcome email via Resend: {e}")
            
    # Fallback to mock
    message = f"[MOCK] Welcome email sent to {email}"
    logger.info(message)
    print(message)
    return message


def send_calendar_events(record_data: dict) -> str:
    """
    Schedule mock calendar events (orientation, 1:1s) for the new hire.
    """
    name = _candidate_name(record_data)
    message = f"[MOCK] Calendar events scheduled for {name}"
    logger.info(message)
    print(message)
    return message


def send_all_notifications(record_data: dict) -> dict:
    """
    Dispatch all notifications in one call.
    """
    return {
        "slack": send_slack_notification(record_data),
        "email": send_welcome_email(record_data),
        "calendar": send_calendar_events(record_data),
    }


"""
Notification service for the onboarding automation system.

Uses real integrations (Slack via Webhook, Email via Resend) if keys are provided.
Falls back to logging [MOCK] messages if keys are missing or API calls fail.
"""

import logging
import requests
import resend
import re
import os
import html
from datetime import datetime
from config import SLACK_WEBHOOK_URL, RESEND_API_KEY, IT_EMAIL, HR_EMAIL, FROM_EMAIL

logger = logging.getLogger(__name__)

STAGING_MODE = os.environ.get("STAGING_MODE", "false").lower() == "true"
STAGING_EMAIL = "staging-test@company.com"
STAGING_SLACK_CHANNEL = "#staging-alerts"

def _candidate_name(record_data: dict) -> str:
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"]
    return (record_data.get("name") or record_data.get("full_name") or "Unknown").strip() or "Unknown"

def _candidate_email(record_data: dict) -> str:
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"]
    return (
        record_data.get("email")
        or record_data.get("personal_email")
        or record_data.get("company_email")
        or "unknown@example.com"
    ).strip() or "unknown@example.com"

def _candidate_role(record_data: dict) -> str:
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"]
    return record_data.get("role", "New Hire")

def _candidate_dept(record_data: dict) -> str:
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"]
    return record_data.get("department", "their team")

def _candidate_start_date(record_data: dict) -> str:
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"]
    return record_data.get("start_date", "TBD")

def _candidate_conf(record_data: dict) -> float:
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"]
    return record_data.get("confidence_score", 0.0)

def _send_slack_block_kit(blocks: list, fallback_text: str, channel: str = "") -> str:
    if STAGING_MODE:
        channel = STAGING_SLACK_CHANNEL
        fallback_text = f"[STAGING] {fallback_text}"
        
    if SLACK_WEBHOOK_URL:
        try:
            payload = {"text": fallback_text, "blocks": blocks}
            if channel:
                payload["channel"] = channel
            response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
            response.raise_for_status()
            message = f"Slack notification sent via webhook to {channel}"
            logger.info(message)
            return message
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            
    message = f"[MOCK SLACK] {fallback_text}"
    logger.info(message)
    print(message)
    return message


def _send_resend_email(to_email: str, subject: str, html: str) -> str:
    if STAGING_MODE:
        to_email = STAGING_EMAIL
        subject = f"[STAGING] {subject}"

    if RESEND_API_KEY and to_email and to_email != "unknown@example.com":
        resend.api_key = RESEND_API_KEY
        try:
            params = {
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html
            }
            email_response = resend.Emails.send(params)
            message = f"Email sent to {to_email} via Resend (ID: {email_response.get('id', 'unknown')})"
            logger.info(message)
            return message
        except Exception as e:
            logger.error(f"Failed to send email via Resend: {e}")
            
    message = f"[MOCK EMAIL] To: {to_email} | Subj: {subject}"
    logger.info(message)
    print(message)
    return message


def md_to_html(md_text: str) -> str:
    if not md_text:
        return ""
    # Safe escape
    h = md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Inline formatting (bold and code)
    h = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h)
    h = re.sub(r"`([^`]+)`", r"<code>\1</code>", h)

    # Process blocks
    blocks = h.split("\n\n")
    html_blocks = []
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        # Check for Headers
        if block.startswith("### "):
            html_blocks.append(f"<h3>{block[4:]}</h3>")
        elif block.startswith("## "):
            html_blocks.append(f"<h2>{block[3:]}</h2>")
        elif block.startswith("# "):
            html_blocks.append(f"<h1>{block[2:]}</h1>")
        # Check for list items
        elif block.startswith("- ") or block.startswith("* "):
            lines = block.split("\n")
            list_items = []
            for line in lines:
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    list_items.append(f"<li>{line[2:]}</li>")
                elif line:
                    list_items.append(line)
            html_blocks.append(f"<ul>{''.join(list_items)}</ul>")
        else:
            # Paragraph with line breaks
            para = block.replace("\n", "<br>")
            html_blocks.append(f"<p>{para}</p>")
            
    return "\n".join(html_blocks)


# --- Slack Messages ---

def send_hr_intake_card(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    dept = _candidate_dept(record)
    start_date = _candidate_start_date(record)
    conf = _candidate_conf(record)
    status = record.get("status", "unknown")
    
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🆕 NEW ONBOARDING SUBMISSION"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*👤 {name}*\n💼 {role} · {dept}\n📅 Start Date: {start_date}\n🤖 AI Confidence: {conf:.2f}\n✅ Status: {status.upper()}"}
        }
    ]
    return _send_slack_block_kit(blocks, f"New Intake: {name} ({status})")

def send_manager_dm(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    start_date = _candidate_start_date(record)
    ctx = record.get("role_context", {})
    manager_handle = ctx.get("manager_slack_handle", "@manager")
    systems = ", ".join(ctx.get("required_systems", []))
    
    text = f"Hi {manager_handle}! 👋\n\n{name} has been approved and joins as {role} on {start_date}.\n\n📋 YOUR PRE-BOARDING CHECKLIST:\n☐ Submit laptop/equipment request via IT portal\n☐ Add to team Slack channels\n☐ Schedule Day 1 welcome 1:1\n☐ Assign an onboarding buddy\n☐ Send the team wiki\n\n🔧 Systems to provision: {systems}\n\n📄 Full 30/60/90-day roadmap generated in HR Console."
    
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    return _send_slack_block_kit(blocks, f"Action Required for new hire {name}", channel=manager_handle)

def send_it_provisioning_request(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    dept = _candidate_dept(record)
    start_date = _candidate_start_date(record)
    email = _candidate_email(record)
    ctx = record.get("role_context", {})
    it_channel = ctx.get("it_channel", "#it-provisioning")
    hardware = ctx.get("hardware_provisioning", "Standard Laptop Provisioning")
    systems = "\n".join([f"• {s}" for s in ctx.get("required_systems", [])])
    
    text = f"*🔧 IT PROVISIONING REQUEST*\nNew Hire: {name}\nRole: {role} | Dept: {dept}\nStart Date: {start_date}\n\n*💻 HARDWARE:*\n• {hardware}\n\n*📦 SYSTEMS TO PROVISION:*\n{systems}\n\n📧 New hire email: {email}"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    return _send_slack_block_kit(blocks, f"IT Provisioning: {name}", channel=it_channel)

def send_new_joiners_announcement(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    dept = _candidate_dept(record)
    start_date = _candidate_start_date(record)
    ctx = record.get("role_context", {})
    channel = ctx.get("announcements_channel", "#new-joiners")
    manager = ctx.get("manager_name", "their manager")
    
    text = f"👋 Please welcome {name} to the team!\n\n{name} joins {dept} as {role}, reporting to {manager}. They start {start_date}.\n\nSay hello and give a warm welcome! 🎉"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    return _send_slack_block_kit(blocks, f"Welcome {name}!", channel=channel)

# --- Email Messages ---

def send_confirmation_email(record: dict) -> str:
    name = _candidate_name(record)
    email = _candidate_email(record)
    
    escaped_name = html.escape(name)
    html_content = f"<p>Hi {escaped_name},</p><p>We've received your onboarding profile!</p><p>Our AI is reviewing your details — HR will follow up within 1 business day.</p><p>What to expect next:</p><ul><li>HR Review</li><li>Welcome email with your roadmap</li><li>IT Setup</li></ul><p>Thanks,<br>HR Team</p>"
    return _send_resend_email(email, f"✅ We've received your onboarding profile, {name}!", html_content)

def send_welcome_email(record: dict) -> str:
    name = _candidate_name(record)
    email = _candidate_email(record)
    roadmap = record.get("roadmap", "")
    roadmap_html = md_to_html(roadmap) if roadmap else "<p>Your roadmap is pending.</p>"
    
    escaped_name = html.escape(name)
    html_content = f"<h2>Welcome to the team, {escaped_name}! 🎉</h2><p>We are excited to have you on board.</p><h3>Your 30/60/90 Day Roadmap</h3>{roadmap_html}<p>Please reach out if you have any questions before your first day!</p>"
    return _send_resend_email(email, f"Welcome to the team, {name}! 🎉 Your first 90 days inside", html_content)

def send_manager_email(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    start_date = _candidate_start_date(record)
    ctx = record.get("role_context", {})
    manager_email = ctx.get("manager_email", HR_EMAIL)
    buddies = ", ".join(ctx.get("default_buddy_pool", []))
    
    escaped_name = html.escape(name)
    escaped_role = html.escape(role)
    escaped_start_date = html.escape(start_date)
    html_content = f"<p>Hi,</p><p>Action Required: {escaped_name} joins your team as {escaped_role} on {escaped_start_date}.</p><p>Please complete your pre-boarding checklist, including assigning a buddy (suggested pool: {buddies}).</p><p>View their full profile and roadmap in the HR Console.</p>"
    return _send_resend_email(manager_email, f"Action Required: {name} joins your team on {start_date}", html_content)

def send_it_email(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    start_date = _candidate_start_date(record)
    ctx = record.get("role_context", {})
    systems = "</li><li>".join(ctx.get("required_systems", []))
    
    escaped_name = html.escape(name)
    escaped_role = html.escape(role)
    escaped_start_date = html.escape(start_date)
    html_content = f"<p>IT Action Required:</p><p>New Hire: {escaped_name} ({escaped_role})</p><p>Start Date: {escaped_start_date}</p><p>Systems to provision:</p><ul><li>{systems}</li></ul>"
    return _send_resend_email(IT_EMAIL, f"IT Action Required: {name} starts {start_date} — Systems to provision", html_content)

def send_offboarding_alert(record: dict) -> str:
    name = _candidate_name(record)
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔴 *OFFBOARDING TRIGGERED*\nRevoke all system access immediately for: {name}"
            }
        }
    ]
    return _send_slack_block_kit(blocks, "Offboarding Triggered", channel="#it-provisioning")

def send_all_notifications(record: dict, stage: str = "intake") -> dict:
    """
    Dispatch all notifications for a given stage.
    stage: 'intake' or 'approved'
    """
    sent = {}
    if stage == "intake":
        sent["slack_hr"] = send_hr_intake_card(record)
        sent["email_conf"] = send_confirmation_email(record)
        # Add a mock calendar for backward compatibility with old tests if needed
        sent["calendar"] = f"[MOCK] Calendar events scheduled for {_candidate_name(record)}"
        sent["slack"] = sent["slack_hr"] # fallback for old tests checking 'slack'
        sent["email"] = sent["email_conf"]  # fallback for old tests checking 'email'
    elif stage == "approved":
        sent["slack_manager"] = send_manager_dm(record)
        sent["slack_it"] = send_it_provisioning_request(record)
        sent["slack_announce"] = send_new_joiners_announcement(record)
        sent["email_welcome"] = send_welcome_email(record)
        sent["email_manager"] = send_manager_email(record)
        sent["email_it"] = send_it_email(record)
        sent["calendar"] = f"[MOCK] Calendar events scheduled for {_candidate_name(record)}"
        sent["slack"] = sent["slack_announce"] # fallback for old tests
        sent["email"] = sent["email_welcome"]  # fallback for old tests
    return sent

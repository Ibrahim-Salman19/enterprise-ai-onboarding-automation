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
    if not record_data:
        return "Unknown"
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"] or {}
    if not isinstance(record_data, dict):
        return "Unknown"
    return (record_data.get("name") or record_data.get("full_name") or "Unknown").strip() or "Unknown"

def _candidate_email(record_data: dict) -> str:
    if not record_data:
        return "unknown@example.com"
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"] or {}
    if not isinstance(record_data, dict):
        return "unknown@example.com"
    return (
        record_data.get("email")
        or record_data.get("personal_email")
        or record_data.get("company_email")
        or "unknown@example.com"
    ).strip() or "unknown@example.com"

def _candidate_role(record_data: dict) -> str:
    if not record_data:
        return "New Hire"
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"] or {}
    if not isinstance(record_data, dict):
        return "New Hire"
    return (record_data.get("role") or "New Hire").strip() or "New Hire"

def _candidate_dept(record_data: dict) -> str:
    if not record_data:
        return "their team"
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"] or {}
    if not isinstance(record_data, dict):
        return "their team"
    return (record_data.get("department") or "their team").strip() or "their team"

def _candidate_start_date(record_data: dict) -> str:
    if not record_data:
        return "TBD"
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"] or {}
    if not isinstance(record_data, dict):
        return "TBD"
    return (record_data.get("start_date") or "TBD").strip() or "TBD"

def _candidate_conf(record_data: dict) -> float:
    if not record_data:
        return 0.0
    if "extracted_data" in record_data:
        record_data = record_data["extracted_data"] or {}
    if not isinstance(record_data, dict):
        return 0.0
    val = record_data.get("confidence_score")
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0

import json

def _redact_pii_for_staging(text: str, record: dict) -> str:
    if not STAGING_MODE or not record:
        return text
    name = _candidate_name(record)
    email = _candidate_email(record)
    
    if name and name not in ("Unknown candidate", "New Hire", "Unknown"):
        text = text.replace(name, "[REDACTED NAME]")
    if email and email != "unknown@example.com":
        text = text.replace(email, "[REDACTED EMAIL]")
        
    text = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[REDACTED EMAIL]", text)
    return text

def _redact_pii_blocks(blocks: list, record: dict) -> list:
    if not STAGING_MODE or not record:
        return blocks
    try:
        blocks_str = json.dumps(blocks)
        redacted_str = _redact_pii_for_staging(blocks_str, record)
        return json.loads(redacted_str)
    except Exception:
        return blocks

def _send_slack_block_kit(blocks: list, fallback_text: str, channel: str = "", record: dict = None) -> str:
    if STAGING_MODE:
        channel = STAGING_SLACK_CHANNEL
        fallback_text = f"[STAGING] {fallback_text}"
        if record:
            fallback_text = _redact_pii_for_staging(fallback_text, record)
            blocks = _redact_pii_blocks(blocks, record)
        
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
            err_msg = f"[ERROR] Failed to send Slack notification: {e}"
            logger.error(err_msg, exc_info=True)
            return err_msg
            
    message = f"[MOCK SLACK] {fallback_text}"
    logger.info(message)
    print(message)
    return message


def _send_resend_email(to_email: str, subject: str, html: str) -> str:
    if STAGING_MODE:
        to_email = STAGING_EMAIL
        subject = f"[STAGING] {subject}"

    if RESEND_API_KEY and to_email and to_email != "unknown@example.com":
        try:
            headers = {
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html
            }
            response = requests.post(
                "https://api.resend.com/emails",
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            res_data = response.json()
            message = f"Email sent to {to_email} via Resend (ID: {res_data.get('id', 'unknown')})"
            logger.info(message)
            return message
        except Exception as e:
            err_msg = f"[ERROR] Failed to send email via Resend: {e}"
            logger.error(err_msg, exc_info=True)
            return err_msg
            
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
    status = (record or {}).get("status") or "unknown"
    
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
    return _send_slack_block_kit(blocks, f"New Intake: {name} ({status})", record=record)

def send_manager_dm(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    start_date = _candidate_start_date(record)
    ctx = (record or {}).get("role_context") or {}
    manager_handle = ctx.get("manager_slack_handle") or "@manager"
    systems = ", ".join(ctx.get("required_systems") or [])
    
    text = f"Hi {manager_handle}! 👋\n\n{name} has been approved and joins as {role} on {start_date}.\n\n📋 YOUR PRE-BOARDING CHECKLIST:\n☐ Submit laptop/equipment request via IT portal\n☐ Add to team Slack channels\n☐ Schedule Day 1 welcome 1:1\n☐ Assign an onboarding buddy\n☐ Send the team wiki\n\n🔧 Systems to provision: {systems}\n\n📄 Full 30/60/90-day roadmap generated in HR Console."
    
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    return _send_slack_block_kit(blocks, f"Action Required for new hire {name}", channel=manager_handle, record=record)

def send_it_provisioning_request(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    dept = _candidate_dept(record)
    start_date = _candidate_start_date(record)
    email = _candidate_email(record)
    ctx = (record or {}).get("role_context") or {}
    it_channel = ctx.get("it_channel") or "#it-provisioning"
    hardware = ctx.get("hardware_provisioning") or "Standard Laptop Provisioning"
    systems = "\n".join([f"• {s}" for s in (ctx.get("required_systems") or [])])
    
    text = f"*🔧 IT PROVISIONING REQUEST*\nNew Hire: {name}\nRole: {role} | Dept: {dept}\nStart Date: {start_date}\n\n*💻 HARDWARE:*\n• {hardware}\n\n*📦 SYSTEMS TO PROVISION:*\n{systems}\n\n📧 New hire email: {email}"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    return _send_slack_block_kit(blocks, f"IT Provisioning: {name}", channel=it_channel, record=record)

def send_new_joiners_announcement(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    dept = _candidate_dept(record)
    start_date = _candidate_start_date(record)
    ctx = (record or {}).get("role_context") or {}
    channel = ctx.get("announcements_channel") or "#new-joiners"
    manager = ctx.get("manager_name") or "their manager"
    
    text = f"👋 Please welcome {name} to the team!\n\n{name} joins {dept} as {role}, reporting to {manager}. They start {start_date}.\n\nSay hello and give a warm welcome! 🎉"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    return _send_slack_block_kit(blocks, f"Welcome {name}!", channel=channel, record=record)

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
    roadmap = (record or {}).get("roadmap", "")
    roadmap_html = md_to_html(roadmap) if roadmap else "<p>Your roadmap is pending.</p>"
    
    escaped_name = html.escape(name)
    html_content = f"<h2>Welcome to the team, {escaped_name}! 🎉</h2><p>We are excited to have you on board.</p><h3>Your 30/60/90 Day Roadmap</h3>{roadmap_html}<p>Please reach out if you have any questions before your first day!</p>"
    return _send_resend_email(email, f"Welcome to the team, {name}! 🎉 Your first 90 days inside", html_content)

def send_manager_email(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    start_date = _candidate_start_date(record)
    ctx = (record or {}).get("role_context") or {}
    manager_email = ctx.get("manager_email") or HR_EMAIL
    buddies = ", ".join(ctx.get("default_buddy_pool") or [])
    
    escaped_name = html.escape(name)
    escaped_role = html.escape(role)
    escaped_start_date = html.escape(start_date)
    html_content = f"<p>Hi,</p><p>Action Required: {escaped_name} joins your team as {escaped_role} on {escaped_start_date}.</p><p>Please complete your pre-boarding checklist, including assigning a buddy (suggested pool: {buddies}).</p><p>View their full profile and roadmap in the HR Console.</p>"
    return _send_resend_email(manager_email, f"Action Required: {name} joins your team on {start_date}", html_content)

def send_it_email(record: dict) -> str:
    name = _candidate_name(record)
    role = _candidate_role(record)
    start_date = _candidate_start_date(record)
    ctx = (record or {}).get("role_context") or {}
    systems = "</li><li>".join(ctx.get("required_systems") or [])
    
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
    return _send_slack_block_kit(blocks, "Offboarding Triggered", channel="#it-provisioning", record=record)

import concurrent.futures

def send_all_notifications(record: dict, stage: str = "intake") -> dict:
    """
    Dispatch all notifications for a given stage.
    stage: 'intake' or 'approved'
    """
    sent = {}
    
    tasks = []
    if stage == "intake":
        tasks = [
            ("slack_hr", send_hr_intake_card, (record,)),
            ("email_conf", send_confirmation_email, (record,)),
        ]
        sent["calendar"] = f"[MOCK] Calendar events scheduled for {_candidate_name(record)}"
    elif stage == "approved":
        tasks = [
            ("slack_manager", send_manager_dm, (record,)),
            ("slack_it", send_it_provisioning_request, (record,)),
            ("slack_announce", send_new_joiners_announcement, (record,)),
            ("email_welcome", send_welcome_email, (record,)),
            ("email_manager", send_manager_email, (record,)),
            ("email_it", send_it_email, (record,)),
        ]
        sent["calendar"] = f"[MOCK] Calendar events scheduled for {_candidate_name(record)}"

    if tasks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            future_to_key = {
                executor.submit(func, *args): key
                for key, func, args in tasks
            }
            # Wait for all tasks with a timeout of 12 seconds
            concurrent.futures.wait(future_to_key.keys(), timeout=12)
            
            for future, key in future_to_key.items():
                try:
                    if future.done():
                        sent[key] = future.result()
                    else:
                        # Task did not finish in time
                        sent[key] = f"[ERROR] Timeout sending notification {key}"
                        logger.error(f"Timeout sending notification {key}")
                except Exception as e:
                    logger.error(f"Error sending notification '{key}': {e}", exc_info=True)
                    sent[key] = f"[ERROR] Failed to send {key}: {str(e)}"

    if stage == "intake":
        sent["slack"] = sent.get("slack_hr")
        sent["email"] = sent.get("email_conf")
    elif stage == "approved":
        sent["slack"] = sent.get("slack_announce")
        sent["email"] = sent.get("email_welcome")
        
    return sent

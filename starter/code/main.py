"""
Main FastAPI Application for the AI-powered onboarding automation system.

Exposes REST API endpoints to trigger document intake processing, handle manual
approvals, query historical records, and inspect system audit logs.
"""

import uuid
import io
import csv
import os
import secrets
import time
from collections import defaultdict
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI

import config
import review_store
import audit_log
import notify
import role_context
import extractor
import validator
import roadmap
import auth
from database import init_db

from contextlib import asynccontextmanager

import sys

# Simple in-memory rate limiting dictionaries
login_attempts = defaultdict(list)
intake_attempts = defaultdict(list)
chat_attempts = defaultdict(list)
webhook_attempts = defaultdict(list)

def check_rate_limit(attempts_dict: dict, ip: str, limit: int, period: int = 60) -> bool:
    now = time.time()
    attempts = [t for t in attempts_dict[ip] if now - t < period]
    attempts_dict[ip] = attempts
    if len(attempts) >= limit:
        return False
    attempts_dict[ip].append(now)
    return True

def check_login_rate_limit(ip: str) -> bool:
    return check_rate_limit(login_attempts, ip, 5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Enforce production security checks (fail-fast)
    is_test_or_demo = "pytest" in sys.modules or any("demo_runner" in arg for arg in sys.argv)
    if not is_test_or_demo:
        if config.ADMIN_PIN == "1234":
            raise RuntimeError("SECURITY RISK: Cannot start application in production with default ADMIN_PIN='1234'. Please set ADMIN_PIN in your environment.")
        if len(config.ADMIN_PIN) < 4:
            raise RuntimeError("SECURITY RISK: ADMIN_PIN must be at least 4 characters long.")
        if not config.WEBHOOK_SECRET:
            raise RuntimeError("SECURITY RISK: Cannot start application in production without WEBHOOK_SECRET. Please set WEBHOOK_SECRET in your environment.")
    yield

app = FastAPI(
    title="AI Onboarding Automation API",
    description="Backend API for automated document extraction, validation routing, and personalized onboarding roadmap synthesis.",
    version="1.0.0",
    lifespan=lifespan
)
# Configure CORS Middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self';"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ── Schemas ─────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    pin: str

class IntakeRequest(BaseModel):
    raw_text: str = Field(..., description="Raw text from candidate intake form or resume scan.")
    document_uploaded: bool = False

class ChatRequest(BaseModel):
    question: str

class HRISWebhookPayload(BaseModel):
    candidate_id: str
    name: str
    email: str
    role: str
    department: str
    start_date: str
    event_type: str = "offer_accepted"

class ApprovalRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$", description="Human decision: 'approve' or 'reject'.")
    approved_by: str = Field(..., min_length=1, description="Name or identifier of the reviewer.")
    notes: str = Field("", description="Optional notes from the reviewer.")


# ── Dependencies ────────────────────────────────────────────────────────────
def get_llm_client_dependency() -> OpenAI:
    """FastAPI Dependency providing the LLM API client."""
    return extractor.get_llm_client()


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def home():
    """Serve the HR Console web UI (single-page app in templates/index.html)."""
    ui_path = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(ui_path.read_text(encoding="utf-8"))

@app.get("/onboarding", response_class=HTMLResponse)
def onboarding_portal():
    """Serve the Employee-facing onboarding portal."""
    ui_path = Path(__file__).parent / "templates" / "intake.html"
    return HTMLResponse(ui_path.read_text(encoding="utf-8"))


@app.get("/health")
def health_check():
    """System health check and configuration summary."""
    return {
        "status": "healthy",
        "model_name": config.MODEL_NAME,
        "confidence_threshold": config.CONFIDENCE_THRESHOLD
    }


@app.post("/auth/login")
def login(req: LoginRequest, request: Request):
    """Authenticate HR admin using PIN."""
    client_host = request.client.host if request.client else "unknown"
    if not check_login_rate_limit(client_host):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")

    if not secrets.compare_digest(req.pin, config.ADMIN_PIN):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    access_token = auth.create_access_token(data={"role": "admin"})
    return {"access_token": access_token, "token_type": "bearer"}


def _process_intake_logic(
    raw_text: str,
    client: OpenAI,
    document_uploaded: bool,
    actor: str = "system"
) -> dict:
    raw_text_clean = raw_text.strip()
    if not raw_text_clean:
        raise HTTPException(
            status_code=422,
            detail="raw_text cannot be empty or whitespace-only"
        )

    record_id = str(uuid.uuid4())
    
    if document_uploaded:
        raw_text_clean += "\n[OCR System: ID Document Verified]"
        audit_log.append_audit(
            actor=actor,
            action="document_verified",
            record_id=record_id,
            details="ID document uploaded and simulated OCR verified.",
            confidence=1.0,
            model_version=config.MODEL_NAME,
            override=False
        )

    # 1. Run LLM Field Extraction
    extracted = extractor.extract_fields(raw_text_clean, client=client)

    # 2. Check for duplicate intake by email (Idempotency Check)
    email = extracted.get("email")
    if email and email != "unknown@example.com":
        existing = review_store.list_records()
        for r in existing:
            ext = r.get("extracted_data") or {}
            if ext.get("email") == email and r.get("status") != "offboarded":
                audit_log.append_audit(
                    actor=actor,
                    action="intake_duplicate_ignored",
                    record_id=r["record_id"],
                    details=f"Duplicate intake submission for email '{email}' ignored (idempotency check).",
                    confidence=extracted.get("confidence_score"),
                    model_version=config.MODEL_NAME,
                    override=False
                )
                return r

    # 3. Perform Routing Decision
    route = validator.route_decision(extracted, confidence_threshold=config.CONFIDENCE_THRESHOLD)

    if route == "auto_approved":
        # 3a. Merge Role & Department context
        context = role_context.get_role_context(
            department=extracted.get("department"),
            job_title=extracted.get("role")
        )
        
        # 3b. Synthesize personalized onboarding plan
        plan = roadmap.generate_onboarding_plan(extracted, context, client=client)
        
        # Assemble final record data
        record = {
            "record_id": record_id,
            "status": "auto_approved",
            "extracted_data": extracted,
            "role_context": context,
            "roadmap": plan,
            "reviewer_notes": "Automatically approved by system.",
            "reviewer_name": "system",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Fire notifications with Continue on Fail
        notifs = {}
        try:
            notifs.update(notify.send_all_notifications(record, "intake"))
        except Exception as e:
            print(f"Flaky Intake Notification Interruption: {e}")
            
        try:
            notifs.update(notify.send_all_notifications(record, "approved"))
        except Exception as e:
            print(f"Flaky Approved Notification Interruption: {e}")
            
        record["notifications_sent"] = notifs
        
        review_store.save_record(record_id, record)
        
        # Audit Log
        audit_log.append_audit(
            actor=actor,
            action="intake_auto_approved",
            record_id=record_id,
            details=f"Auto-approved employee: {extracted.get('name')}",
            confidence=extracted.get("confidence_score"),
            model_version=config.MODEL_NAME,
            override=False
        )
    else:
        # 3c. Save for manual review
        record = {
            "record_id": record_id,
            "status": "pending_review",
            "extracted_data": extracted,
            "role_context": {},
            "roadmap": "",
            "reviewer_notes": "",
            "reviewer_name": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Save before notifications to ensure idempotency / checkpoint
        review_store.save_record(record_id, record)
        
        try:
            record["notifications_sent"] = notify.send_all_notifications(record, "intake")
            review_store.save_record(record_id, record)
        except Exception as e:
            print(f"Flaky Notification Interruption: {e}")
        
        # Audit Log
        is_valid, validation_errors = validator.validate_extracted_data(extracted)
        details = "Manual review triggered. Issues: " + ", ".join(validation_errors) if validation_errors else "Confidence below threshold."
        audit_log.append_audit(
            actor=actor,
            action="intake_queued_review",
            record_id=record_id,
            details=details,
            confidence=extracted.get("confidence_score"),
            model_version=config.MODEL_NAME,
            override=False
        )

    return record


@app.post("/intake")
def process_intake(
    req: IntakeRequest,
    request: Request,
    client: OpenAI = Depends(get_llm_client_dependency)
):
    """
    Ingest raw candidate text, perform LLM extraction, validate, and route
    to either auto-approval or manual HR review.
    """
    client_host = request.client.host if request.client else "unknown"
    if not check_rate_limit(intake_attempts, client_host, 10):
        raise HTTPException(status_code=429, detail="Too many intake requests. Please try again later.")
    return _process_intake_logic(req.raw_text, client, req.document_uploaded, actor="employee_portal")


@app.post("/webhooks/hris")
def process_hris_webhook(
    payload: HRISWebhookPayload,
    request: Request,
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    client: OpenAI = Depends(get_llm_client_dependency)
):
    """
    Zero-Touch Onboarding Ingestion Endpoint.
    Triggered when HRIS (e.g., Workday, BambooHR) marks a candidate as 'Hired'.
    """
    client_host = request.client.host if request.client else "unknown"
    if not check_rate_limit(webhook_attempts, client_host, 20):
        raise HTTPException(status_code=429, detail="Too many webhook requests. Please try again later.")

    if not config.WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Webhook integration is disabled because no secret is configured.")
    if not x_webhook_secret or not secrets.compare_digest(x_webhook_secret, config.WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    if payload.event_type != "offer_accepted":
        return {"status": "ignored", "reason": "Not an offer_accepted event"}
        
    raw_text = f"Name: {payload.name}\nEmail: {payload.email}\nRole: {payload.role}\nDepartment: {payload.department}\nStart Date: {payload.start_date}\n[Source: HRIS Webhook Automation]"
    
    return _process_intake_logic(raw_text, client, document_uploaded=False, actor="hris_webhook")


@app.post("/approve/{record_id}")
def approve_record(
    record_id: str,
    req: ApprovalRequest,
    client: OpenAI = Depends(get_llm_client_dependency),
    admin: str = Depends(auth.get_current_admin)
):
    """
    Handle a human-in-the-loop decision (approve or reject) for a pending candidate.
    If approved, merges role context and synthesizes their personalized onboarding plan.
    """
    with review_store.write_lock:
        record = review_store.get_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Onboarding record '{record_id}' not found.")

        if record.get("status") != "pending_review":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot approve/reject record. Current status is '{record.get('status')}', expected 'pending_review'."
            )

        decision = req.decision
        reviewer = req.approved_by
        notes = req.notes

        extracted = record["extracted_data"]

        if decision == "approve":
            # Merge department lookup metadata
            context = role_context.get_role_context(
                department=extracted.get("department"),
                job_title=extracted.get("role")
            )
            # Synthesize personalized onboarding plan
            plan = roadmap.generate_onboarding_plan(extracted, context, client=client)

            record.update({
                "status": "approved",
                "role_context": context,
                "roadmap": plan,
                "reviewer_notes": notes,
                "reviewer_name": reviewer,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            # Save before notifications to ensure idempotency / checkpoint
            review_store.save_record(record_id, record)
            
            notifs = record.get("notifications_sent", {})
            try:
                notifs.update(notify.send_all_notifications(record, "approved"))
            except Exception as e:
                print(f"Flaky Notification Interruption: {e}")
                
            record["notifications_sent"] = notifs
            review_store.save_record(record_id, record)

            # Audit Log (with override=True)
            audit_log.append_audit(
                actor=reviewer,
                action="manual_approved",
                record_id=record_id,
                details=f"Record approved. Notes: {notes}",
                confidence=extracted.get("confidence_score"),
                model_version=config.MODEL_NAME,
                override=True
            )
            
            # Schedule Pulse Surveys
            audit_log.append_audit(
                actor="system",
                action="pulse_survey_scheduled",
                record_id=record_id,
                details="30-Day and 60-Day Pulse Surveys queued for delivery.",
                confidence=1.0,
                model_version=config.MODEL_NAME,
                override=False
            )
        else:
            record.update({
                "status": "rejected",
                "reviewer_notes": notes,
                "reviewer_name": reviewer,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            
            review_store.save_record(record_id, record)

            # Audit Log (with override=True)
            audit_log.append_audit(
                actor=reviewer,
                action="manual_rejected",
                record_id=record_id,
                details=f"Rejected by reviewer with notes: '{notes}'",
                confidence=extracted.get("confidence_score"),
                model_version=config.MODEL_NAME,
                override=True
            )

        return record


@app.get("/records")
def get_all_records(admin: str = Depends(auth.get_current_admin)):
    """Retrieve all stored onboarding profiles."""
    return review_store.list_records()


@app.get("/records/{record_id}")
def get_single_record(record_id: str, admin: str = Depends(auth.get_current_admin)):
    """Retrieve a single onboarding profile by its ID."""
    record = review_store.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record

@app.get("/stats")
def get_dashboard_stats(admin: str = Depends(auth.get_current_admin)):
    """Retrieve aggregated stats for the HR dashboard."""
    return review_store.get_stats()

@app.post("/chat/faq")
def chat_faq(
    req: ChatRequest,
    request: Request,
    client: OpenAI = Depends(get_llm_client_dependency)
):
    """AI FAQ Chatbot endpoint for new hires."""
    client_host = request.client.host if request.client else "unknown"
    if not check_rate_limit(chat_attempts, client_host, 10):
        raise HTTPException(status_code=429, detail="Too many chat requests. Please try again later.")
    system_prompt = "You are an HR assistant for the company. Answer policy questions based on standard corporate policies concisely."
    try:
        response = client.chat.completions.create(
            model=config.MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": req.question}
            ],
            max_tokens=150,
            temperature=0.3
        )
        answer = response.choices[0].message.content.strip()
        return {"answer": answer}
    except Exception as e:
        return {"answer": f"I'm currently unable to answer questions. Please contact HR."}

@app.post("/offboard/{record_id}")
def offboard_employee(
    record_id: str,
    actor: Optional[str] = None,
    admin: str = Depends(auth.get_current_admin)
):
    """Automate the offboarding and de-provisioning workflow."""
    with review_store.write_lock:
        actor_name = actor if actor else admin
        record = review_store.get_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        
        if record.get("status") == "offboarded":
            raise HTTPException(status_code=409, detail="Record is already offboarded.")
        
        current_status = record.get("status")
        if current_status not in ("approved", "auto_approved"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot offboard record with current status '{current_status}'. Only 'approved' or 'auto_approved' records can be offboarded."
            )
        
        res = notify.send_offboarding_alert(record)
        if res and res.startswith("[ERROR]"):
            try:
                audit_log.append_audit(
                    actor=actor_name,
                    action="offboarding_failed",
                    record_id=record_id,
                    details=f"De-provisioning notification failed: {res}",
                    confidence=1.0,
                    model_version=config.MODEL_NAME,
                    override=True
                )
            except Exception as ae:
                print(f"Audit log writing failed during offboard failure logging: {ae}")
            raise HTTPException(
                status_code=502,
                detail=f"De-provisioning alert failed. Offboarding aborted: {res}"
            )
            
        record["status"] = "offboarded"
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        review_store.save_record(record_id, record)
        
        try:
            audit_log.append_audit(
                actor=actor_name,
                action="offboarding_initiated",
                record_id=record_id,
                details="Automated de-provisioning and offboarding workflow triggered.",
                confidence=1.0,
                model_version=config.MODEL_NAME,
                override=True
            )
        except Exception as e:
            print(f"Audit log writing failed: {e}")
        return {"status": "offboarded", "record_id": record_id}


@app.get("/audit")
def get_audit_log_entries(admin: str = Depends(auth.get_current_admin)):
    """Retrieve the full chronological audit trail of all ingestion events and overrides."""
    return audit_log.get_audit_log()

def sanitize_csv_cell(val) -> str:
    if val is None:
        return ""
    val_str = str(val)
    val_stripped = val_str.lstrip()
    if val_stripped and val_stripped[0] in ('=', '+', '-', '@', '|', '%', '\t', '\r'):
        return f"'{val_str}"
    return val_str


@app.get("/export/audit")
def export_audit_log(admin: str = Depends(auth.get_current_admin)):
    """Export the full audit log as a CSV for compliance."""
    entries = audit_log.get_audit_log()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Actor", "Action", "Record ID", "Details", "Confidence", "Model Version", "Override"])
    for entry in entries:
        writer.writerow([
            sanitize_csv_cell(entry.get("timestamp")),
            sanitize_csv_cell(entry.get("actor")),
            sanitize_csv_cell(entry.get("action")),
            sanitize_csv_cell(entry.get("record_id")),
            sanitize_csv_cell(entry.get("details")),
            entry.get("confidence"),
            sanitize_csv_cell(entry.get("model_version")),
            entry.get("override")
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_trail.csv"}
    )

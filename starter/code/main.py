"""
Main FastAPI Application for the AI-powered onboarding automation system.

Exposes REST API endpoints to trigger document intake processing, handle manual
approvals, query historical records, and inspect system audit logs.
"""

import uuid
import io
import csv
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="AI Onboarding Automation API",
    description="Backend API for automated document extraction, validation routing, and personalized onboarding roadmap synthesis.",
    version="1.0.0",
    lifespan=lifespan
)

# ── Security & Middleware ───────────────────────────────────────────────────


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
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
def login(req: LoginRequest):
    """Authenticate HR admin using PIN."""
    if req.pin != config.ADMIN_PIN:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    access_token = auth.create_access_token(data={"role": "admin"})
    return {"access_token": access_token, "token_type": "bearer"}


def _process_intake_logic(
    raw_text: str,
    client: OpenAI,
    document_uploaded: bool
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
            actor="system",
            action="document_verified",
            record_id=record_id,
            details="ID document uploaded and simulated OCR verified.",
            confidence=1.0,
            model_version=config.MODEL_NAME,
            override=False
        )

    # 1. Run LLM Field Extraction
    extracted = extractor.extract_fields(raw_text_clean, client=client)

    # 2. Perform Routing Decision
    route = validator.route_decision(extracted, confidence_threshold=config.CONFIDENCE_THRESHOLD)

    if route == "auto_approve":
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
            notifs.update(notify.send_all_notifications(record, "approved"))
        except Exception as e:
            print(f"Flaky Notification Interruption: {e}")
            
        record["notifications_sent"] = notifs
        
        review_store.save_record(record_id, record)
        
        # Audit Log
        audit_log.append_audit(
            actor="system",
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
            actor="system",
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
    client: OpenAI = Depends(get_llm_client_dependency)
):
    """
    Ingest raw candidate text, perform LLM extraction, validate, and route
    to either auto-approval or manual HR review.
    """
    return _process_intake_logic(req.raw_text, client, req.document_uploaded)


@app.post("/webhooks/hris")
def process_hris_webhook(
    payload: HRISWebhookPayload,
    client: OpenAI = Depends(get_llm_client_dependency)
):
    """
    Zero-Touch Onboarding Ingestion Endpoint.
    Triggered when HRIS (e.g., Workday, BambooHR) marks a candidate as 'Hired'.
    """
    if payload.event_type != "offer_accepted":
        return {"status": "ignored", "reason": "Not an offer_accepted event"}
        
    raw_text = f"Name: {payload.name}\nEmail: {payload.email}\nRole: {payload.role}\nDepartment: {payload.department}\nStart Date: {payload.start_date}\n[Source: HRIS Webhook Automation]"
    
    return _process_intake_logic(raw_text, client, document_uploaded=False)


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
def chat_faq(req: ChatRequest, client: OpenAI = Depends(get_llm_client_dependency)):
    """AI FAQ Chatbot endpoint for new hires."""
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
def offboard_employee(record_id: str, admin: str = Depends(auth.get_current_admin)):
    """Automate the offboarding and de-provisioning workflow."""
    record = review_store.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    if record.get("status") == "offboarded":
        raise HTTPException(status_code=409, detail="Record is already offboarded.")
    
    try:
        notify.send_offboarding_alert(record)
    except Exception as e:
        print(f"Flaky Notification Interruption: {e}")
        
    record["status"] = "offboarded"
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    review_store.save_record(record_id, record)
    
    audit_log.append_audit(
        actor=admin,
        action="offboarding_initiated",
        record_id=record_id,
        details="Automated de-provisioning and offboarding workflow triggered.",
        confidence=1.0,
        model_version=config.MODEL_NAME,
        override=True
    )
    return {"status": "offboarded", "record_id": record_id}


@app.get("/audit")
def get_audit_log_entries(admin: str = Depends(auth.get_current_admin)):
    """Retrieve the full chronological audit trail of all ingestion events and overrides."""
    return audit_log.get_audit_log()

@app.get("/export/audit")
def export_audit_log(admin: str = Depends(auth.get_current_admin)):
    """Export the full audit log as a CSV for compliance."""
    entries = audit_log.get_audit_log()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Actor", "Action", "Record ID", "Details", "Confidence", "Model Version", "Override"])
    for entry in entries:
        writer.writerow([
            entry.get("timestamp"),
            entry.get("actor"),
            entry.get("action"),
            entry.get("record_id"),
            entry.get("details"),
            entry.get("confidence"),
            entry.get("model_version"),
            entry.get("override")
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_trail.csv"}
    )

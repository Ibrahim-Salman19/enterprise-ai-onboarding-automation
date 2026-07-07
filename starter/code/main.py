"""
Main FastAPI Application for the AI-powered onboarding automation system.

Exposes REST API endpoints to trigger document intake processing, handle manual
approvals, query historical records, and inspect system audit logs.
"""

import uuid
from fastapi import FastAPI, HTTPException, Depends
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

app = FastAPI(
    title="AI Onboarding Automation API",
    description="Backend API for automated document extraction, validation routing, and personalized onboarding roadmap synthesis.",
    version="1.0.0"
)


# ── Schemas ─────────────────────────────────────────────────────────────────
class IntakeRequest(BaseModel):
    raw_text: str = Field(..., description="Raw text from candidate intake form or resume scan.")


class ApprovalRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$", description="Human decision: 'approve' or 'reject'.")
    approved_by: str = Field(..., min_length=1, description="Name or identifier of the reviewer.")
    notes: str = Field("", description="Optional notes from the reviewer.")


# ── Dependencies ────────────────────────────────────────────────────────────
def get_llm_client_dependency() -> OpenAI:
    """FastAPI Dependency providing the LLM API client."""
    return extractor.get_llm_client()


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """System health check and configuration summary."""
    return {
        "status": "healthy",
        "model_name": config.MODEL_NAME,
        "confidence_threshold": config.CONFIDENCE_THRESHOLD
    }


@app.post("/intake")
def process_intake(
    req: IntakeRequest,
    client: OpenAI = Depends(get_llm_client_dependency)
):
    """
    Ingest raw candidate text, perform LLM extraction, validate, and route
    to either auto-approval or manual HR review.
    """
    raw_text = req.raw_text.strip()
    if not raw_text:
        raise HTTPException(
            status_code=422,
            detail="raw_text cannot be empty or whitespace-only"
        )

    record_id = str(uuid.uuid4())

    # 1. Run LLM Field Extraction
    extracted = extractor.extract_fields(raw_text, client=client)

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
            "notifications_sent": notify.send_all_notifications(extracted),
            "reviewer_notes": "Automatically approved by system.",
            "reviewer_name": "system"
        }
        
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
            "notifications_sent": {},
            "reviewer_notes": "",
            "reviewer_name": ""
        }
        
        review_store.save_record(record_id, record)
        
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


@app.post("/approve/{record_id}")
def approve_record(
    record_id: str,
    req: ApprovalRequest,
    client: OpenAI = Depends(get_llm_client_dependency)
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
            "notifications_sent": notify.send_all_notifications(extracted),
            "reviewer_notes": notes,
            "reviewer_name": reviewer
        })
        
        review_store.save_record(record_id, record)

        # Audit Log (with override=True)
        audit_log.append_audit(
            actor=reviewer,
            action="manual_approved",
            record_id=record_id,
            details=f"Approved by reviewer with notes: '{notes}'",
            confidence=extracted.get("confidence_score"),
            model_version=config.MODEL_NAME,
            override=True
        )
    else:
        record.update({
            "status": "rejected",
            "reviewer_notes": notes,
            "reviewer_name": reviewer
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
def get_all_records():
    """Retrieve all stored onboarding profiles."""
    return review_store.list_records()


@app.get("/records/{record_id}")
def get_single_record(record_id: str):
    """Retrieve a single onboarding profile by its ID."""
    record = review_store.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Onboarding record not found.")
    return record


@app.get("/audit")
def get_audit_log_entries():
    """Retrieve the full chronological audit trail of all ingestion events and overrides."""
    return audit_log.get_audit_log()

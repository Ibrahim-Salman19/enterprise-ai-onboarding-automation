# Candidate Submission Template

## Candidate Information
- Full Name: Hafiz Muhammad Ibrahim Salman
- Email: ibrahim.pk848@gmail.com
- LinkedIn or Portfolio: https://linkedin.com/in/ibrahim-salman
- Submission Date: July 7, 2026

## Overview
This solution presents the complete architectural design and workflow prototype for an enterprise-grade AI Onboarding Automation system. Built on a hybrid architecture, it combines a self-hosted **n8n v2.x** orchestration engine (acting as the transactional runtime) with a commercial core HRIS (acting as the secure database of record). The system automates document intake extraction, applies deterministic data sanitization code, handles low-confidence executions via non-blocking human-in-the-loop (HITL) approval gates, and dynamically synthesizes personalized, role-specific onboarding roadmaps.

---

## Task 1: AI-Powered Automation Design

### Workflow Logic
The onboarding lifecycle is decomposed into six main stages:
1.  **Intake Trigger:** Webhook receives new hire payloads (forms, scans of ID/contracts) from the intake portal.
2.  **AI Document Extraction:** LangChain and GPT-4o analyze unstructured document strings, extracting candidate profile details.
3.  **Sanitization & Validation:** A JavaScript node parses extraction results, checks constraints (minimum name length, email formatting), and flags records where the confidence score is $< 0.85$ (`route_manual: true`).
4.  **Routing Split:** Automated branch routes high-confidence records directly to directory lookup. Low-confidence extractions are sent to an interactive Slack channel for review, pausing the parent workflow at a `Wait` node.
5.  **Data Enrichment:** Integrates new-hire fields with the central employee profile using Airtable lookups.
6.  **Roadmap Synthesis & Provisioning:** Synthesizes a role-based onboarding roadmap in markdown format, triggers automated notifications, creates Google Calendar events, and sends welcome packets via Gmail SMTP.

For more details, see: [starter/design-solution.md](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/design-solution.md#L12-L68)

### Where AI Is Used
AI is applied strategically where static, rule-based logic fails:
*   **Classification & OCR:** Multimodal visual LLMs (GPT-4o or Gemini Flash) process skewed or low-res document scans, performing optical character recognition and field classification without layout templates.
*   **Input Normalization:** Zero-shot semantic mapping translates inconsistent entries (e.g., job titles like "Sftwr Dev" or "SWE-II") to standardized employee records.
*   **Roadmap Personalization:** Context-aware prompt completions synthesize structured markdown plans tailored to candidate experience and team needs.
*   **Communication Drafting:** Generates personalized check-in messages, welcome emails, and manager handoff notifications.

For more details, see: [starter/design-solution.md](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/design-solution.md#L70-L113)

### Prompt Engineering
The system utilizes two highly optimized prompt templates:
1.  **Document Intake Extraction Prompt:** Enforces strict flat JSON schemas, self-assessed confidence scores, and missing-field outputs.
2.  **Roadmap Synthesis Prompt:** Synthesizes structured markdown containing welcome sections, 30/60/90-day targets, and key team contacts.

For the exact prompts and schema configurations, see: [starter/prompts/prompts.md](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/prompts/prompts.md)

### Data Flow and Integrations
*   **Intake Interface:** Portal webhook triggers the onboarding sequence.
*   **Orchestration Engine:** Self-hosted n8n coordinates LLMs, databases, and APIs.
*   **Database of Record (Airtable / HRIS):** Searches, maps, and writes candidate data.
*   **Slack App Integration:** Dispatches interactive Block Kit messages with approval/rejection webhooks.
*   **Gmail & Google Calendar:** Delivers personalized welcome mail packets and registers sync schedules.

For more details, see: [starter/design-solution.md](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/design-solution.md#L182-L198)

### Business Impact
*   **Efficiency:** compresses HR administration time from **10 hours to under 2 hours** per hire, and IT setup to **under 30 minutes**.
*   **Accuracy:** Replaces manual I-9 verification (which averages a 76% error rate) with structured validation pipelines, protecting the firm from statutory paperwork penalties.
*   **TCO Optimization:** The custom self-hosted n8n Community build yields a **3-year financial savings of $79,889.50 USD** over commercial PEPM alternatives.
*   **New Hire Experience:** Custom onboarding plans accelerate new hire ramp-to-productivity by **34%** and lift first-year retention by **82%**.

For more details, see: [starter/design-solution.md](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/design-solution.md#L200-L230)

---

## Task 2: Implementation Demo

### Demo Type
*   **Python FastAPI Service Prototype:** Complete web service managing intake, routing, manual review callbacks, mock notifications, and audit logging.
*   **n8n Workflow Export JSON:** Complete node-by-node pipeline configuration.
*   **JavaScript Sanitizer Script:** Robust data sanitization logic.
*   **Slack Block Kit UI JSON:** Interactive approval interface template.

### Files Included
1.  [starter/design-solution.md](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/design-solution.md) - Technical design documentation.
2.  [starter/prompts/prompts.md](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/prompts/prompts.md) - Prompt engineering specifications.
3.  [starter/diagrams/flow.md](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/diagrams/flow.md) - Mermaid workflow flowchart.
4.  [starter/workflows/onboarding-workflow.json](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/workflows/onboarding-workflow.json) - n8n workflow configuration.
5.  [starter/code/main.py](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/code/main.py) - FastAPI routes and setup.
6.  [starter/code/extractor.py](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/code/extractor.py) - LLM field extraction with Groq.
7.  [starter/code/validator.py](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/code/validator.py) - Verification and routing logic.
8.  [starter/code/roadmap.py](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/code/roadmap.py) - Onboarding plan generator.
9.  [starter/code/audit_log.py](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/code/audit_log.py) - Audit trail database.
10. [starter/code/tests/test_workflow.py](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/code/tests/test_workflow.py) - Full integration test suite.

### Flow of Data
*   **Intake Payload:** Webhook trigger passes raw intake text/metadata to the `/intake` FastAPI route.
*   **Sanitization & Validation:** Code checks field lengths, standard email regex, and LLM self-assessed extraction confidence.
*   **Routing Decision:** High-confidence records are auto-approved and route directly to enrichment. Low-confidence records are saved as `pending_review`.
*   **Human Approval Loop:** HR reviews pending cases via Slack or API, triggering POST `/approve/{id}` or `/reject/{id}` to proceed.
*   **Enrichment & Push:** System joins departmental role context, requests LLM to synthesize a personalized markdown onboarding roadmap, dispatches Slack alerts, and triggers mock welcome email/calendar syncs.
*   **Chronological Auditing:** All actions are tracked in a write-once audit log recording timestamps, actors, model versions, confidence scores, and manual override flags.

### Pain Points Solved
*   **Eliminates Data Inconsistency:** State serialization halts execution during manual approvals, ensuring downstream provisioning nodes never run with partial or broken profiles.
*   **SaaS Licensing Inflation:** Decouples licensing costs from headcount growth by deploying a self-hosted engine.
*   **Mitigates Attrition & Delays:** Delivers personalized roadmaps on day one, avoiding onboarding delays due to manual coordinator bottlenecks.

---

## Assumptions
*   **ZDR Availability:** Assumes the enterprise LLM API contract includes Zero Data Retention (ZDR) clauses to prevent the logging of employee PII.
*   **Hosting Stack:** The n8n engine is deployed on a self-hosted, private VPS (e.g., AWS ECS) using a secure PostgreSQL backend.
*   **Airtable Structure:** The central database table contains corporate emails mapped to unique record IDs.

---

## Setup Instructions

### 1. Running the FastAPI Prototype & Tests
To run the python backend prototype locally:
1.  **Install dependencies:**
    ```bash
    cd starter/code
    pip install -r requirements.txt
    ```
2.  **Configure environment:**
    Copy `.env.example` to `.env` and set your `GROQ_API_KEY`.
3.  **Run backend server:**
    ```bash
    uvicorn main:app --reload
    ```
4.  **Execute automated test suite:**
    ```bash
    pytest -v
    ```

### 2. Deploying the n8n Orchestrator Workflow
To deploy and test the onboarding orchestrator workflow:
1.  **Initialize Directory:** Create target paths and configure security permissions (`chown -R 1000:1000 /opt/n8n-onboarding`).
2.  **Spin up Containers:** Populate a `.env` file with database credentials and run `docker compose up -d` using the Compose configuration detailed in the design document.
3.  **Import Workflow:** Import [starter/workflows/onboarding-workflow.json](file:///mnt/c/Users/hafiz/Task1_interview/enterprise-ai-onboarding-automation/starter/workflows/onboarding-workflow.json) directly into the n8n canvas.

---

## Optional Notes
The solution is designed with strict compliance guardrails (including the CCPA proxy exclusion rule and Illinois IHRA 4-year audit retention logging), making it highly suitable for multi-jurisdictional enterprise onboarding.

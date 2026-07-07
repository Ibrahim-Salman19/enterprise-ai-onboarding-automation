# AI Onboarding Automation Workflow Diagram

The following Mermaid diagram illustrates the end-to-end event-driven flow of the onboarding orchestrator. It outlines the intake trigger, automated field extraction, validation routing split, and the non-blocking Human-in-the-Loop (HITL) review loop.

```mermaid
flowchart TD
    %% Styling Nodes
    classDef trigger fill:#1b2a47,stroke:#264f87,stroke-width:1.5px,color:#89ddff;
    classDef ai fill:#2a1b47,stroke:#5c2d91,stroke-width:1.5px,color:#c792ea;
    classDef logic fill:#1b3d2b,stroke:#2d7d46,stroke-width:1.5px,color:#c3e88d;
    classDef system fill:#1e1e24,stroke:#3a3a4a,stroke-width:1px,color:#d4d4d8;
    classDef ext fill:#422a1d,stroke:#a15c38,stroke-width:1.5px,color:#ffcb6b;
    classDef state fill:#3d1b32,stroke:#7d2d64,stroke-width:1.5px,color:#f07178;

    A[Intake Webhook Trigger]:::trigger --> B[AI Document Extractor<br/>Llama 3.3 70B on Groq]:::ai
    B --> C[Run Javascript Code Sanitizer<br/>Regex & Field Length Checks]:::logic
    C --> D{Confidence & Validity Check:<br/>score >= 0.80 & no issues?}:::logic
    
    %% Automatic Pathway
    D -- Yes [auto_approve] --> E[Fetch & Merge Role Context<br/>Lookup Table]:::logic
    E --> F[Synthesize Personalized Roadmap<br/>LLM Prompt Completion]:::ai
    F --> G[Update Database Record<br/>Airtable Status: Active]:::ext
    G --> H[Dispatch Slack Channel Alert]:::ext
    G --> I[Send Welcome Gmail Webhook]:::ext
    G --> J[Schedule Orientation Syncs]:::ext
    
    %% Manual Queue Pathway (HITL)
    D -- No [manual_review] --> K[Mark Status: pending_review]:::state
    K --> L[Post Interactive Slack Message<br/>Block Kit with resumeUrl]:::ext
    L --> M[Wait Node: Pause Execution<br/>Serialize State to Postgres]:::state
    
    %% Slack Callback Resumption
    N[Slack Button Click: Approve/Reject]:::trigger --> O[Lightweight Callback Receiver]:::trigger
    O --> P[Return Immediate HTTP 200]:::logic
    P --> Q[Decode Payload & Send POST<br/>to resumeUrl]:::logic
    Q --> M
    
    M --> R{Review Decision?}:::logic
    R -- Approve --> E
    R -- Reject --> S[Mark Status: rejected]:::state
    S --> T[Log Manual Overrides]:::state
    
    %% Global Auditing
    G --> U[Append Encrypted WORM Audit Log]:::state
    T --> U
```

### Architectural Highlights

1. **Non-Blocking Approvals (Flat Webhook Orchestration):** Using an n8n `Wait` node or API-based state storage avoids active memory consumption while waiting for human reviews. State is serialized to a database, freeing up execution threads.
2. **Deterministic Validation:** LLM extraction is paired with local code-based regex validations (for email addresses) and length checks (for names), ensuring that low-quality extractions are caught before database writes.
3. **Decoupled Client Dependencies:** The backend prototype leverages dependency injection for LLM APIs, enabling mocking for offline testing and preventing runtime vendor lock-in.

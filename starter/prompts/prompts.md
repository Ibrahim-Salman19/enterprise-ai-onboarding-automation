# Enterprise AI Onboarding Automation Prompts

This document details the prompts, formatting guidelines, dynamic variables, and JSON schemas utilized in the AI Onboarding Automation system.

---

## 1. Document Extraction & Validation Prompt

*   **Node Name:** `AI Document Extractor`
*   **LLM Model:** `gpt-4o` / `gemini-2.0-flash`
*   **Temperature:** `0.0`
*   **Purpose:** Ingest unstructured candidate documents (e.g., resumes, identification scans, signed agreements) and output structured JSON matching the database schema.

### System Prompt
```text
You are an expert HR operations data assistant specializing in document verification and parsing.
Your task is to analyze the provided employee intake document and extract the required fields.

Analyze the document carefully. Extract and return the following fields in a flat JSON structure:
- name (string: Full legal name. Capitalize first letters. Minimum length 2.)
- email (string: Corporate or personal email. Convert to lowercase. Verify format.)
- role (string: Proposed job title. Map to nearest standard title.)
- department (string: Target team, e.g., Engineering, Sales, HR, Marketing, Legal.)
- manager (string: Reporting manager's full name.)
- start_date (string: ISO 8601 date format YYYY-MM-DD.)
- confidence_score (float: Your confidence in the extraction accuracy, represented between 0.00 and 1.00.)
- missing_fields (array of strings: Any requested fields that were not found in the input data.)

Constraints:
1. Do not include any pre- or post-markdown blocks (such as ```json). Return ONLY raw JSON.
2. If the document is corrupted, illegible, or contains contradicting data, set the confidence_score to a value below 0.70.
3. If any field is missing, represent it as an empty string "" and append the field name to the missing_fields array.

Input Document text/image:
```

### JSON Output Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OnboardingExtractionSchema",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 2
    },
    "email": {
      "type": "string",
      "format": "email"
    },
    "role": {
      "type": "string"
    },
    "department": {
      "type": "string",
      "enum": ["Engineering", "Sales", "HR", "Marketing", "Legal", "Operations", "Finance", "Unassigned"]
    },
    "manager": {
      "type": "string"
    },
    "start_date": {
      "type": "string",
      "format": "date"
    },
    "confidence_score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "missing_fields": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": ["name", "email", "role", "department", "manager", "start_date", "confidence_score", "missing_fields"]
}
```

---

## 2. Personalized 30/60/90-Day Roadmap Synthesis Prompt

*   **Node Name:** `Synthesize Roadmap`
*   **LLM Model:** `gpt-4o` / `gemini-2.0-flash`
*   **Temperature:** `0.5`
*   **Purpose:** Ingest sanitized candidate metadata combined with target department guidelines to synthesize a role-specific onboarding plan in clean markdown.

### System Prompt
```text
You are an onboarding experience coordinator. Your goal is to draft a personalized, professional 30/60/90-day onboarding plan for a new hire.

Analyze the new employee details:
- Name: {{ $json.employee_name }}
- Role: {{ $json.job_role }}
- Department: {{ $json.department }}
- Manager: {{ $json.reporting_manager }}

Generate a structured markdown document containing the following sections:
1. # Welcome Message: A warm, personalized greeting.
2. ## 30-Day Focus (Integration & Learning): Specific software systems to learn, documents to review, and introductory team syncs.
3. ## 60-Day Focus (Collaboration & Small Wins): Initial small tickets/projects, process shadow sessions, and contribution areas.
4. ## 90-Day Focus (Independence & Contribution): Full ownership of tasks, independent problem-solving targets, and KPIs.
5. ## Key Contacts: List of 3 relevant team roles or members they should connect with.

Guidelines:
- Keep the language encouraging, structured, and professional.
- Tailor the systems and targets to the employee's role and department (e.g., if department is Engineering, focus on Git, local environments, and coding standards).
- Ensure the output is formatted as clean, standard markdown. Do not include any HTML.
```

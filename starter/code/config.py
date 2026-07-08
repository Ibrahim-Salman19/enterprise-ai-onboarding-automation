"""
Configuration module for the AI-powered onboarding automation system.

Loads all application settings from environment variables with sensible defaults.
Uses python-dotenv to support .env files for local development.
"""

import os
from dotenv import load_dotenv

# Load .env file if present (no-op in production where env vars are set directly)
load_dotenv()

# ── Groq / LLM Settings ─────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
# Default to a current, stable Groq production model.
# Note: `llama-3.3-70b-versatile` was deprecated by Groq on 2026-06-17; `openai/gpt-oss-120b`
# is an actively supported production model that also exposes native `structured_outputs`,
# which makes deterministic JSON extraction more reliable.
MODEL_NAME: str = os.getenv("MODEL_NAME", "openai/gpt-oss-120b")
# Reasoning models (gpt-oss family) emit hidden reasoning tokens before the visible answer,
# so the completion budget must be large enough to cover both. Reserved for use in
# extractor.py / roadmap.py when calling the API.
MODEL_MAX_TOKENS: int = int(os.getenv("MODEL_MAX_TOKENS", "1024"))

# ── Business-Rule Thresholds ────────────────────────────────────────────────
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.80"))

# ── Integrations ────────────────────────────────────────────────────────────
SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

# ── Security & Auth ─────────────────────────────────────────────────────────
ADMIN_PIN: str = os.getenv("ADMIN_PIN", "1234")
JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-jwt-key-2026")

# ── Notifications & IT ──────────────────────────────────────────────────────
IT_EMAIL: str = os.getenv("IT_EMAIL", "it@company.com")
HR_EMAIL: str = os.getenv("HR_EMAIL", "hr@company.com")

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
MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen/qwen3.6-27b")

# ── Business-Rule Thresholds ────────────────────────────────────────────────
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.80"))

"""
config.py — Centralised configuration and constants

All guardrail constants, intent sets, and shared configuration
are defined here and imported by agents, guardrails, and the pipeline.
"""

# ─────────────────────────────────────────────────────────────
# INTENT CLASSIFICATION SETS
# ─────────────────────────────────────────────────────────────

# Intents that always require human verification before resolution
CRITICAL_INTENTS = {
    "prescription_change",
    "emergency_symptom",
    "critical_lab_result",
    "medication_interaction",
    "mental_health_crisis",
}

# Intents the AI must never resolve autonomously (always escalate)
ALWAYS_ESCALATE_INTENTS = {
    "mental_health_crisis",
    "emergency_symptom",
    "suicide_risk",
    "severe_allergic_reaction",
}


# ─────────────────────────────────────────────────────────────
# BANNED RESPONSE PATTERNS
# ─────────────────────────────────────────────────────────────

BANNED_PATTERNS = [
    "you should take",
    "increase your dose",
    "stop taking",
    "this means you have",
    "you are diagnosed",
    "i recommend this medication",
]


# ─────────────────────────────────────────────────────────────
# APPROVED DISCLAIMER
# ─────────────────────────────────────────────────────────────

APPROVED_DISCLAIMER = (
    "This information is for general guidance only. "
    "Please consult your healthcare provider for medical decisions."
)

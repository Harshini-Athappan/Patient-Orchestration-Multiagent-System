"""
guardrails/guardrails.py — Centralised guardrail definitions and enforcement

All guardrails are:
  1. Defined here as constants and functions
  2. Imported by every agent
  3. Audited on every execution

Healthcare guardrails enforced:
  G1 — No medical advice beyond approved guidelines
  G2 — No cross-session patient data sharing
  G3 — Critical queries require verification before resolution
  G4 — Prescription changes always need physician approval
  G5 — Emergency intents always escalate to human
  G6 — Response guardrail scan before every send
"""

from typing import List, Tuple
import re


# ─────────────────────────────────────────────────────────────
# G1 — BANNED MEDICAL ADVICE PATTERNS
# ─────────────────────────────────────────────────────────────

BANNED_PATTERNS: List[str] = [
    r"you should take",
    r"increase your (dose|dosage|medication)",
    r"decrease your (dose|dosage|medication)",
    r"stop taking",
    r"(you|this) (means you have|indicates you have|suggests you have)",
    r"you are diagnosed",
    r"i recommend (this medication|taking)",
    r"you (have|likely have|probably have) (cancer|diabetes|hypertension|disease)",
    r"this (result|test) confirms",
    r"no need to see (a doctor|your doctor|the doctor)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BANNED_PATTERNS]

APPROVED_DISCLAIMER = (
    "This information is for general guidance only and does not constitute "
    "medical advice. Please consult your healthcare provider for any medical decisions."
)


def scan_for_violations(text: str) -> List[str]:
    """Returns list of matched banned patterns found in text."""
    return [p.pattern for p in COMPILED_PATTERNS if p.search(text)]


def inject_disclaimer(text: str) -> str:
    """Appends the approved medical disclaimer if not already present."""
    if APPROVED_DISCLAIMER[:30] not in text:
        return text + f"\n\n{APPROVED_DISCLAIMER}"
    return text


# ─────────────────────────────────────────────────────────────
# G2 — SESSION ISOLATION
# ─────────────────────────────────────────────────────────────

def assert_session_isolation(state: dict) -> Tuple[bool, str]:
    """
    Verifies no patient data is leaking from a previous session.
    In production: also checks memory stores and caches.
    """
    required_fresh_fields = [
        "appointment_result", "prescription_result",
        "report_result", "insurance_result", "escalation_result"
    ]
    for field in required_fresh_fields:
        if state.get(field) is not None:
            # These should be None at session start
            return False, f"Session isolation violation: {field} is not None at start"
    return True, "Session isolation verified"


# ─────────────────────────────────────────────────────────────
# G3 — CRITICAL QUERY VERIFICATION REQUIREMENTS
# ─────────────────────────────────────────────────────────────

CRITICAL_INTENTS = {
    "prescription_change",
    "emergency_symptom",
    "critical_lab_result",
    "medication_interaction",
    "mental_health_crisis",
    "suicide_risk",
    "severe_allergic_reaction",
}

ALWAYS_ESCALATE_INTENTS = {
    "mental_health_crisis",
    "emergency_symptom",
    "suicide_risk",
    "severe_allergic_reaction",
}


def is_critical(intent: str) -> bool:
    return intent in CRITICAL_INTENTS


def must_escalate(intent: str) -> bool:
    return intent in ALWAYS_ESCALATE_INTENTS


# ─────────────────────────────────────────────────────────────
# G4 — PRESCRIPTION CHANGE HARD STOP
# ─────────────────────────────────────────────────────────────

PRESCRIPTION_READONLY_ACTIONS = {"refill_status", "pickup_info", "pharmacy_info"}
PRESCRIPTION_PHYSICIAN_REQUIRED = {"change_dose", "new_medication", "stop_medication", "switch_medication"}


def prescription_action_allowed(action: str) -> Tuple[bool, str]:
    if action in PRESCRIPTION_PHYSICIAN_REQUIRED:
        return False, f"Action '{action}' requires physician approval — escalating"
    if action in PRESCRIPTION_READONLY_ACTIONS:
        return True, "Read-only prescription action permitted"
    return False, f"Unknown action '{action}' — defaulting to escalation"


# ─────────────────────────────────────────────────────────────
# G5 — EMERGENCY RESPONSE INSTRUCTIONS
# ─────────────────────────────────────────────────────────────

EMERGENCY_INSTRUCTIONS = (
    "If you are experiencing a life-threatening emergency, "
    "please call 108 (India) or your local emergency services immediately. "
    "Do not wait for a callback."
)

MENTAL_HEALTH_RESOURCES = (
    "If you are in crisis, please call iCall: 9152987821 or "
    "Vandrevala Foundation: 1860-2662-345 (24/7, free). "
    "A counsellor is available to speak with you right now."
)


def get_emergency_message(intent: str) -> str:
    if intent == "mental_health_crisis":
        return MENTAL_HEALTH_RESOURCES
    return EMERGENCY_INSTRUCTIONS


# ─────────────────────────────────────────────────────────────
# G6 — FINAL RESPONSE GATE
# ─────────────────────────────────────────────────────────────

SAFE_FALLBACK_RESPONSE = (
    "We were unable to process your request automatically. "
    "A member of our clinical team will contact you shortly. "
    "If this is an emergency, please call 108 immediately."
)


def validate_response(response: str) -> Tuple[bool, str, List[str]]:
    """
    Final gate: validates a response before sending to patient.
    Returns (is_safe, cleaned_response, violations_found).
    """
    violations = scan_for_violations(response)
    if violations:
        return False, SAFE_FALLBACK_RESPONSE, violations
    return True, response, []

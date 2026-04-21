"""
agents/intent_classifier.py — Supervisor Orchestrator (LLM-based)

Uses Groq (Llama 3) to classify patient queries into structured intents.
Falls back to keyword matching if the LLM is unavailable.

Supervisor role: analyze the query → choose the right downstream agent.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from state.patient_state import PatientState
from config import CRITICAL_INTENTS, ALWAYS_ESCALATE_INTENTS
from utils.audit import log_event
from utils.exceptions import AgentExecutionError
from utils.logger import get_logger
from agents.prompts import SUPERVISOR_PROMPT
from utils.memory_utils import format_history

logger = get_logger("intent_classifier")

# ─────────────────────────────────────────────────────────────
# KEYWORD FALLBACK (used when LLM is unavailable or key not set)
# ─────────────────────────────────────────────────────────────

def _keyword_classify(query: str) -> tuple[str, float]:
    """Deterministic keyword fallback — no LLM needed."""
    q = query.lower()
    if any(k in q for k in ["appointment", "schedule", "book", "cancel", "reschedule"]):
        return "appointment", 0.88
    if any(k in q for k in ["change my prescription", "switch medication", "stop taking", "stop medication", "stop my"]):
        return "prescription_change", 0.90
    if any(k in q for k in ["prescription", "refill", "medication", "drug", "dose"]):
        return "prescription_validation", 0.85
    if any(k in q for k in ["lab", "result", "report", "blood test", "scan", "mri", "x-ray"]):
        return "lab_report", 0.82
    if any(k in q for k in ["insurance", "claim", "coverage", "reimbursement", "billing"]):
        return "insurance_claim", 0.84
    if any(k in q for k in ["chest pain", "can't breathe", "emergency", "unconscious", "collapse"]):
        return "emergency_symptom", 0.97
    if any(k in q for k in ["suicid", "self harm", "crisis", "depress", "hopeless", "end my life"]):
        return "mental_health_crisis", 0.95
    return "general_inquiry", 0.60


# ─────────────────────────────────────────────────────────────
# LLM CLASSIFIER (Groq Supervisor)
# ─────────────────────────────────────────────────────────────

def _llm_classify(query: str, **kwargs) -> tuple[str, float, str]:
    """
    Uses Groq (Llama 3) as the Supervisor Orchestrator.
    Returns (intent, confidence, reasoning).
    Raises AgentExecutionError on failure.
    """
    from utils.llm_client import get_llm

    llm = get_llm(temperature=0.0)

    messages = [
        SystemMessage(content=SUPERVISOR_PROMPT.format(
            long_term_context=kwargs.get("long_term_context", "No prior history."),
            history=kwargs.get("history", "No recent messages.")
        )),
        HumanMessage(content=f"Patient Query: {query}"),
    ]

    response = llm.invoke(messages)
    raw_content = response.content.strip()

    # Strip markdown code block if present
    if raw_content.startswith("```"):
        raw_content = raw_content.split("```")[1]
        if raw_content.startswith("json"):
            raw_content = raw_content[4:]

    parsed = json.loads(raw_content)

    intent = parsed["intent"]
    confidence = float(parsed.get("confidence", 0.80))
    reasoning = parsed.get("reasoning", "LLM classified.")

    # Validate the intent is one we know
    valid_intents = {
        "appointment", "prescription_validation", "prescription_change",
        "lab_report", "insurance_claim", "emergency_symptom",
        "mental_health_crisis", "general_inquiry"
    }
    if intent not in valid_intents:
        logger.warning(f"LLM returned unknown intent: '{intent}'. Falling back to general_inquiry.")
        intent = "general_inquiry"
        confidence = 0.50

    return intent, confidence, reasoning


# ─────────────────────────────────────────────────────────────
# MAIN CLASSIFIER NODE
# ─────────────────────────────────────────────────────────────

def intent_classifier(state: PatientState) -> PatientState:
    """
    Supervisor Orchestrator: classifies the patient query via Groq LLM.
    Falls back to keyword matching if LLM key is not configured.
    """
    query = state["raw_query"]
    reasoning = "Keyword-based fallback classification."

    try:
        hist_str = format_history(state.get("history", []))
        lt_str = state.get("long_term_context", "No prior history.")
        
        intent, confidence, reasoning = _llm_classify(query, history=hist_str, long_term_context=lt_str)
        logger.info(f"LLM classified intent='{intent}' confidence={confidence}")
    except EnvironmentError:
        logger.warning("GROQ_API_KEY not set — using keyword fallback classifier.")
        intent, confidence = _keyword_classify(query)
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}. Using keyword fallback.")
        intent, confidence = _keyword_classify(query)
    except Exception as e:
        logger.error(f"LLM classifier error: {e}. Using keyword fallback.")
        intent, confidence = _keyword_classify(query)

    state["intent"] = intent
    state["intent_confidence"] = confidence
    state["requires_verification"] = intent in CRITICAL_INTENTS
    state["verified"] = False
    state["escalated_to_human"] = False
    state["compliance_violation"] = False

    state = log_event(state, "IntentClassifier", "intent_classified", {
        "intent": intent,
        "confidence": confidence,
        "requires_verification": state["requires_verification"],
        "always_escalate": intent in ALWAYS_ESCALATE_INTENTS,
        "reasoning": reasoning,
    })
    return state


# ─────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────

def route_intent(state: PatientState) -> str:
    """
    Orchestrator decides which agent handles the request.
    Always-escalate intents go directly to human escalation.
    """
    intent = state["intent"]

    if intent in ALWAYS_ESCALATE_INTENTS:
        return "human_escalation"
    if intent in ("appointment",):
        return "appointment"
    if intent in ("prescription_validation", "prescription_change"):
        return "prescription"
    if intent == "lab_report":
        return "lab_report"
    if intent == "insurance_claim":
        return "insurance"
    return "human_escalation"  # Default: unknown → human

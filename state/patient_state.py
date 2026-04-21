"""
state/patient_state.py — Shared session state definition

PatientState is the single TypedDict that flows through every node
in the LangGraph pipeline.  Cleared after every session.
"""

from typing import TypedDict, Optional, List
import uuid


class PatientState(TypedDict):
    # Session identifiers
    session_id: str
    patient_id: str                         # Anonymised handle

    # Incoming query
    raw_query: str
    intent: Optional[str]                   # Classified intent
    intent_confidence: Optional[float]

    # Agent outputs
    appointment_result: Optional[dict]
    prescription_result: Optional[dict]
    report_result: Optional[dict]
    insurance_result: Optional[dict]
    escalation_result: Optional[dict]

    # Control flags
    requires_verification: bool             # Critical query flag
    verified: bool                          # Verification passed
    escalated_to_human: bool
    compliance_violation: bool

    # Final response
    final_response: Optional[str]
    response_source: Optional[str]          # Which agent answered

    # Conversation Memory
    history: List[dict]                     # Recent messages (Short-term)
    long_term_context: Optional[str]        # Summarized past interactions (Long-term)
    
    # Audit trail (per-session only — NOT persisted cross-session)
    audit_log: List[dict]
    error: Optional[str]


def create_initial_state(patient_id: str, query: str) -> PatientState:
    """Factory: creates a fresh, isolated state for each session."""
    state: PatientState = {
        "session_id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "raw_query": query,
        "intent": None,
        "intent_confidence": None,
        "appointment_result": None,
        "prescription_result": None,
        "report_result": None,
        "insurance_result": None,
        "escalation_result": None,
        "requires_verification": False,
        "verified": False,
        "escalated_to_human": False,
        "compliance_violation": False,
        "final_response": None,
        "response_source": None,
        "history": [],
        "long_term_context": None,
        "audit_log": [],
        "error": None,
    }
    validate_initial_state(state)
    return state

def validate_initial_state(state: PatientState):
    """Validate that the initial state is correctly formed before processing."""
    from utils.exceptions import InputValidationError
    if not state.get("session_id"):
        raise InputValidationError("Session ID is missing from state.")
    if not state.get("patient_id") or len(state["patient_id"]) < 1:
        raise InputValidationError("Patient ID is missing or empty.")
    if not state.get("raw_query") or len(state["raw_query"].strip()) < 3:
        raise InputValidationError("Query is missing or too short.")
    if state.get("appointment_result") is not None:
        raise InputValidationError("State leakage detected: agent result present at session start.")

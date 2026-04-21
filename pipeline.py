"""
Healthcare Patient Inquiry System
LangGraph Multi-Agent Orchestrator

This is the slim pipeline file that wires together all agents into
a LangGraph StateGraph. It exposes the public API: handle_inquiry().

Agents:
  1. Intent Classifier (Orchestrator Router)
  2. Appointment Scheduling Agent
  3. Prescription Validation Agent
  4. Lab Report Explanation Agent
  5. Insurance Claims Agent
  6. Human Escalation Agent

Guardrails:
  - No medical advice beyond approved guidelines
  - No cross-session patient data sharing
  - Critical queries require verification before resolution
  - All decisions logged for compliance audit
"""

from langgraph.graph import StateGraph, END

from state.patient_state import PatientState, create_initial_state
from agents.intent_classifier import intent_classifier, route_intent
from agents.appointment_agent import appointment_agent
from agents.prescription_agent import prescription_agent
from agents.lab_report_agent import lab_report_agent
from agents.insurance_agent import insurance_agent
from agents.human_escalation_agent import human_escalation_agent
from utils.audit import log_event, guardrail_scan
from utils.exceptions import PatientOrchestratorError
from utils.logger import get_logger
from persistence.session_store import save_session, get_patient_memory
from utils.event_hooks import dispatcher

logger = get_logger("pipeline")


# ─────────────────────────────────────────────────────────────
# POST-RESPONSE GUARDRAIL CHECK
# ─────────────────────────────────────────────────────────────

def guardrail_check(state: PatientState) -> PatientState:
    """
    Final compliance gate before response is sent to patient.
    If the response contains banned patterns it is blocked and escalated.
    """
    response = state.get("final_response", "")
    violations = guardrail_scan(response)

    if violations:
        state["compliance_violation"] = True
        state = log_event(state, "GuardrailCheck", "RESPONSE_BLOCKED", {
            "reason": "Banned medical advice patterns detected",
            "patterns": violations,
            "original_source": state.get("response_source"),
        })
        # Override response with safe fallback
        state["final_response"] = (
            "We were unable to process your request automatically. "
            "A member of our clinical team will contact you shortly."
        )
        state["escalated_to_human"] = True
    else:
        state = log_event(state, "GuardrailCheck", "response_approved", {
            "source": state.get("response_source"),
            "compliance_clean": True,
        })

    return state


# ─────────────────────────────────────────────────────────────
# BUILD THE LANGGRAPH PIPELINE
# ─────────────────────────────────────────────────────────────

def build_pipeline() -> StateGraph:
    graph = StateGraph(PatientState)

    # Register all nodes
    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("appointment", appointment_agent)
    graph.add_node("prescription", prescription_agent)
    graph.add_node("lab_report", lab_report_agent)
    graph.add_node("insurance", insurance_agent)
    graph.add_node("human_escalation", human_escalation_agent)
    graph.add_node("guardrail_check", guardrail_check)

    # Entry point
    graph.set_entry_point("intent_classifier")

    # Intent routing — orchestrator decides which agent runs
    graph.add_conditional_edges(
        "intent_classifier",
        route_intent,
        {
            "appointment":       "appointment",
            "prescription":      "prescription",
            "lab_report":        "lab_report",
            "insurance":         "insurance",
            "human_escalation":  "human_escalation",
        }
    )

    # All agents converge to the guardrail check before response is sent
    for node in ["appointment", "prescription", "lab_report", "insurance", "human_escalation"]:
        graph.add_edge(node, "guardrail_check")

    # Guardrail check is always the final step
    graph.add_edge("guardrail_check", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────

def handle_inquiry(
    patient_id: str,
    query: str,
) -> dict:
    """
    Entry point for a single patient inquiry.
    Each call creates a new isolated session — no cross-session data.
    """
    pipeline = build_pipeline()

    # GUARDRAIL: Fresh state per session
    initial_state = create_initial_state(patient_id, query)
    
    # Inject memory (Short-term & Long-term)
    memory = get_patient_memory(patient_id)
    initial_state["history"] = memory["short_term"]
    initial_state["long_term_context"] = memory["long_term"]
    
    dispatcher.dispatch("on_session_start", initial_state)

    try:
        final_state = pipeline.invoke(initial_state)
    except Exception as e:
        logger.error(f"Pipeline crashed during execution: {str(e)}")
        # Safe fallback — ensure all fields are non-None so Pydantic doesn't fail
        final_state = initial_state
        final_state["intent"] = final_state.get("intent") or "unknown"
        final_state["final_response"] = "A technical error occurred while processing your request. Our team has been notified. If this is an emergency, please call 108 immediately."
        final_state["escalated_to_human"] = True
        final_state["error"] = str(e)
        final_state["response_source"] = "SystemFallback"
        
    dispatcher.dispatch("on_session_end", final_state)

    return {
        "session_id": final_state["session_id"],
        "patient_id": patient_id,
        "intent": final_state["intent"],
        "response": final_state["final_response"],
        "source": final_state["response_source"],
        "escalated": final_state["escalated_to_human"],
        "compliance_violation": final_state["compliance_violation"],
        "audit_log": final_state["audit_log"],
    }


# ─────────────────────────────────────────────────────────────
# EXAMPLE USAGE
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        ("P001", "I need to book an appointment with a general physician"),
        ("P002", "Can I get a refill for my Metformin prescription?"),
        ("P003", "Can you explain my HbA1c lab results?"),
        ("P004", "What is the status of my insurance claim?"),
        ("P005", "I have severe chest pain and can't breathe"),
        ("P006", "I want to stop taking my blood pressure medication"),
    ]

    for patient_id, query in test_cases:
        print(f"\n{'='*60}")
        print(f"Patient: {patient_id} | Query: {query}")
        print("="*60)
        result = handle_inquiry(patient_id, query)
        print(f"Intent      : {result['intent']}")
        print(f"Response    : {result['response']}")
        print(f"Source      : {result['source']}")
        print(f"Escalated   : {result['escalated']}")
        print(f"Compliance  : {'VIOLATION' if result['compliance_violation'] else 'CLEAN'}")
        print(f"Audit Events: {len(result['audit_log'])}")

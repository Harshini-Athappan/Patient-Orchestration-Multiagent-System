"""
agents/prescription_agent.py — Prescription Validation Agent (Groq LLM)

Uses Groq to generate safe prescription status responses.
Prescription changes are ALWAYS escalated to human — never handled by the LLM.
"""

from langchain_core.messages import SystemMessage, HumanMessage

from state.patient_state import PatientState
from config import APPROVED_DISCLAIMER
from utils.audit import log_event, guardrail_scan
from utils.exceptions import AgentExecutionError
from utils.logger import get_logger
from agents.prompts import PRESCRIPTION_AGENT_PROMPT
from utils.memory_utils import format_history

logger = get_logger("prescription_agent")


def prescription_agent(state: PatientState) -> PatientState:
    """
    Handles prescription refill / status check requests.
    Prescription changes are ALWAYS escalated to a physician (never LLM-handled).
    """
    from agents.human_escalation_agent import human_escalation_agent

    try:
        intent = state["intent"]

        # HARD GUARDRAIL: Prescription changes must ALWAYS go to human
        if intent == "prescription_change":
            state = log_event(state, "PrescriptionAgent", "escalation_triggered", {
                "reason": "Prescription change request — requires physician approval",
                "guardrail": "PRESCRIPTION_CHANGE_ESCALATION"
            })
            return human_escalation_agent(state, reason="Prescription change requires physician review")

        # Refill context (in production: fetched from Pharmacy API)
        result = {
            "status": "approved",
            "medication": "Metformin 500mg",
            "refill_ready": True,
            "pickup_date": "2025-05-08",
            "pharmacy": "Apollo Pharmacy, Main Branch",
            "refills_remaining": 2,
        }

        context = (
            f"Patient query: {state['raw_query']}\n\n"
            f"Prescription Details (fetched from system):\n"
            f"- Medication: {result['medication']}\n"
            f"- Status: {result['status'].upper()}\n"
            f"- Pickup Date: {result['pickup_date']}\n"
            f"- Pharmacy: {result['pharmacy']}\n"
            f"- Refills Remaining: {result['refills_remaining']}\n\n"
            f"Communicate this clearly. Always include the disclaimer: {APPROVED_DISCLAIMER}"
        )

        hist_str = format_history(state.get("history", []))
        lt_str = state.get("long_term_context", "No prior history.")
        response = _llm_response(context, PRESCRIPTION_AGENT_PROMPT, "PrescriptionAgent", history=hist_str, long_term_context=lt_str)

    except AgentExecutionError:
        raise
    except Exception as e:
        logger.error(f"PrescriptionAgent failed: {str(e)}", exc_info=True)
        raise AgentExecutionError(f"Failed to process prescription: {str(e)}")

    violations = guardrail_scan(response)
    if violations:
        state["compliance_violation"] = True
        state = log_event(state, "PrescriptionAgent", "COMPLIANCE_VIOLATION", {
            "banned_patterns_found": violations
        })

    state["prescription_result"] = result
    state["final_response"] = response
    state["response_source"] = "PrescriptionAgent"

    state = log_event(state, "PrescriptionAgent", "prescription_status_returned", {
        "medication": result["medication"],
        "status": result["status"],
        "dosage_changed": False,
        "disclaimer_included": True,
        "compliance_violation": state["compliance_violation"],
    })
    return state


def _llm_response(context: str, system_prompt: str, agent_name: str, **kwargs) -> str:
    """Call Groq LLM with fallback."""
    try:
        from utils.llm_client import get_llm
        llm = get_llm(temperature=0.1)
        messages = [
            SystemMessage(content=system_prompt.format(
                history=kwargs.get("history", "No recent messages."),
                long_term_context=kwargs.get("long_term_context", "No prior history.")
            )),
            HumanMessage(content=context),
        ]
        result = llm.invoke(messages)
        return result.content.strip()
    except EnvironmentError:
        logger.warning(f"{agent_name}: GROQ_API_KEY not set — using template response.")
        return (
            f"Your refill for Metformin 500mg has been approved and will be ready "
            f"on 2025-05-08 at Apollo Pharmacy, Main Branch. "
            f"Refills remaining: 2. {APPROVED_DISCLAIMER}"
        )
    except Exception as e:
        logger.error(f"{agent_name} LLM call failed: {e}", exc_info=True)
        raise AgentExecutionError(f"LLM response generation failed: {e}")

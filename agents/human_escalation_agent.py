"""
agents/human_escalation_agent.py — Human Escalation Agent (Groq LLM)

Always-available fallback. Triggered by:
  - Emergency / mental health crisis intents
  - Critical lab values
  - Prescription change requests
  - Low-confidence classification
  - Compliance violation detected
  - Any unresolved critical query

Uses Groq LLM to generate an empathetic, context-aware escalation message.
"""

import uuid
from langchain_core.messages import SystemMessage, HumanMessage

from state.patient_state import PatientState
from config import ALWAYS_ESCALATE_INTENTS
from utils.audit import log_event
from utils.exceptions import AgentExecutionError
from utils.logger import get_logger
from agents.prompts import ESCALATION_AGENT_PROMPT
from utils.memory_utils import format_history

logger = get_logger("human_escalation_agent")


def human_escalation_agent(
    state: PatientState,
    reason: str = "Escalated by orchestrator"
) -> PatientState:
    """
    Escalates the query to a human clinical staff member.
    Creates a support ticket and uses Groq LLM for an empathetic response.
    """
    try:
        ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        priority = "URGENT" if state["intent"] in ALWAYS_ESCALATE_INTENTS else "HIGH"
        callback = "Within 15 minutes" if priority == "URGENT" else "Within 2 hours"

        escalation_record = {
            "ticket_id": ticket_id,
            "priority": priority,
            "reason": reason,
            "intent": state["intent"],
            "assigned_to": "On-call Clinical Staff",
            "estimated_callback": callback,
        }

        # Build LLM context
        emergency_note = ""
        if state["intent"] == "emergency_symptom":
            emergency_note = "This is a physical emergency. Include: 'Call 108 immediately.'"
        elif state["intent"] == "mental_health_crisis":
            emergency_note = "This is a mental health crisis. Include iCall helpline: 9152987821."

        context = (
            f"Patient query: {state['raw_query']}\n"
            f"Intent: {state['intent']}\n"
            f"Ticket ID: {ticket_id}\n"
            f"Priority: {priority}\n"
            f"Expected callback: {callback}\n"
            f"Reason for escalation: {reason}\n"
            f"{emergency_note}\n\n"
            f"Write an empathetic, calming message acknowledging the patient's concern "
            f"and confirming a human specialist will contact them."
        )

        hist_str = format_history(state.get("history", []))
        lt_str = state.get("long_term_context", "No prior history.")
        response = _llm_response(context, ESCALATION_AGENT_PROMPT, "HumanEscalationAgent", priority, ticket_id, callback, state, history=hist_str, long_term_context=lt_str)

    except AgentExecutionError:
        raise
    except Exception as e:
        logger.error(f"HumanEscalationAgent failed: {str(e)}", exc_info=True)
        raise AgentExecutionError(f"Failed to escalate: {str(e)}")

    state["escalation_result"] = escalation_record
    state["final_response"] = response
    state["response_source"] = "HumanEscalationAgent"
    state["escalated_to_human"] = True

    state = log_event(state, "HumanEscalationAgent", "escalation_created", {
        "ticket_id": ticket_id,
        "priority": priority,
        "reason": reason,
        "intent": state["intent"],
        "on_call_notified": True,
    })
    return state


def _llm_response(context: str, system_prompt: str, agent_name: str,
                  priority: str, ticket_id: str, callback: str, state: dict, **kwargs) -> str:
    """Call Groq LLM with fallback template for escalation."""
    try:
        from utils.llm_client import get_llm
        llm = get_llm(temperature=0.3)
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
        emergency = ""
        if state["intent"] == "emergency_symptom":
            emergency = " If this is a life-threatening emergency, please call 108 immediately."
        elif state["intent"] == "mental_health_crisis":
            emergency = " If you are in immediate danger, please call iCall at 9152987821."
        return (
            f"Your request has been escalated to our clinical team (Ticket: {ticket_id}). "
            f"Priority: {priority}. A specialist will contact you {callback}.{emergency}"
        )
    except Exception as e:
        logger.error(f"{agent_name} LLM call failed: {e}", exc_info=True)
        raise AgentExecutionError(f"LLM response generation failed: {e}")

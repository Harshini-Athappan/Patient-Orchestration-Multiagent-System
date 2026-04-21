"""
agents/appointment_agent.py — Appointment Scheduling Agent (Groq LLM)

Uses Groq to generate natural, context-aware scheduling responses
grounded by the APPOINTMENT_AGENT_PROMPT guardrails.
"""

import uuid
from langchain_core.messages import SystemMessage, HumanMessage

from state.patient_state import PatientState
from utils.audit import log_event, guardrail_scan
from utils.exceptions import AgentExecutionError
from utils.logger import get_logger
from agents.prompts import APPOINTMENT_AGENT_PROMPT
from utils.memory_utils import format_history

logger = get_logger("appointment_agent")


def appointment_agent(state: PatientState) -> PatientState:
    """
    Handles appointment booking, rescheduling, and cancellation.
    Uses Groq LLM to generate the patient response with prompt-enforced guardrails.
    """
    try:
        query = state["raw_query"]

        # Build the appointment context (in production: fetched from EHR/Calendar API)
        confirmation_id = f"APT-{uuid.uuid4().hex[:8].upper()}"
        slot = "2025-05-10 10:30 AM"
        department = "General Practice"
        instructions = "Please arrive 10 minutes early with your insurance card."

        result = {
            "action": "appointment_scheduled",
            "slot": slot,
            "department": department,
            "confirmation_id": confirmation_id,
            "instructions": instructions,
        }

        # Build context for the LLM
        context = (
            f"Patient query: {query}\n\n"
            f"Appointment Details (already confirmed in system):\n"
            f"- Slot: {slot}\n"
            f"- Department: {department}\n"
            f"- Confirmation ID: {confirmation_id}\n"
            f"- Instructions: {instructions}\n\n"
            f"Communicate these details to the patient clearly and empathetically."
        )

        hist_str = format_history(state.get("history", []))
        lt_str = state.get("long_term_context", "No prior history.")
        response = _llm_response(context, APPOINTMENT_AGENT_PROMPT, "AppointmentAgent", history=hist_str, long_term_context=lt_str)

    except AgentExecutionError:
        raise
    except Exception as e:
        logger.error(f"AppointmentAgent failed: {str(e)}", exc_info=True)
        raise AgentExecutionError(f"Failed to process appointment: {str(e)}")

    # Guardrail scan on generated response
    violations = guardrail_scan(response)
    if violations:
        state["compliance_violation"] = True
        state = log_event(state, "AppointmentAgent", "COMPLIANCE_VIOLATION", {
            "banned_patterns_found": violations
        })

    state["appointment_result"] = result
    state["final_response"] = response
    state["response_source"] = "AppointmentAgent"

    state = log_event(state, "AppointmentAgent", "appointment_confirmed", {
        "confirmation_id": result["confirmation_id"],
        "slot": result["slot"],
        "medical_advice_given": False,
        "compliance_violation": state["compliance_violation"],
    })
    return state


def _llm_response(context: str, system_prompt: str, agent_name: str, **kwargs) -> str:
    """Call Groq LLM. Falls back to a structured template if key not set."""
    try:
        from utils.llm_client import get_llm
        llm = get_llm(temperature=0.2)
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
        # Extract confirmation from context for template fallback
        lines = {line.split(":")[0].strip(): line.split(":", 1)[1].strip()
                 for line in context.split("\n") if ":" in line}
        slot = lines.get("- Slot", "scheduled time")
        dept = lines.get("- Department", "the clinic")
        cid = lines.get("- Confirmation ID", "N/A")
        instr = lines.get("- Instructions", "Please arrive on time.")
        return (
            f"Your appointment has been scheduled for {slot} at {dept}. "
            f"Confirmation ID: {cid}. {instr}"
        )
    except Exception as e:
        logger.error(f"{agent_name} LLM call failed: {e}", exc_info=True)
        raise AgentExecutionError(f"LLM response generation failed: {e}")

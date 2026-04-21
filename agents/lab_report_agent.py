"""
agents/lab_report_agent.py — Lab Report Explanation Agent (Groq LLM)

Uses Groq to explain lab results in plain language.
Strict prompt prevents any diagnosis or medical advice.
"""

from langchain_core.messages import SystemMessage, HumanMessage

from state.patient_state import PatientState
from config import APPROVED_DISCLAIMER
from utils.audit import log_event, guardrail_scan
from utils.exceptions import AgentExecutionError
from utils.logger import get_logger
from agents.prompts import LAB_REPORT_AGENT_PROMPT
from utils.memory_utils import format_history

logger = get_logger("lab_report_agent")


def lab_report_agent(state: PatientState) -> PatientState:
    """
    Explains lab results in plain language via Groq LLM.
    Critical lab values are escalated immediately.
    """
    from agents.human_escalation_agent import human_escalation_agent

    try:
        # Stub: in production this fetches from EHR/lab system API
        lab_data = {
            "test": "HbA1c",
            "value": 7.8,
            "unit": "%",
            "normal_range": "4.0 – 5.6",
            "flag": "HIGH",
            "critical": False,  # True would trigger immediate escalation
        }

        # GUARDRAIL: Critical lab value → escalate immediately, never LLM-handled
        if lab_data.get("critical"):
            state = log_event(state, "LabReportAgent", "critical_value_escalation", {
                "test": lab_data["test"],
                "value": lab_data["value"],
                "guardrail": "CRITICAL_LAB_ESCALATION"
            })
            return human_escalation_agent(
                state, reason=f"Critical lab value detected: {lab_data['test']} = {lab_data['value']}"
            )

        context = (
            f"Patient query: {state['raw_query']}\n\n"
            f"Lab Result Details:\n"
            f"- Test: {lab_data['test']}\n"
            f"- Result: {lab_data['value']} {lab_data['unit']}\n"
            f"- Normal Range: {lab_data['normal_range']}\n"
            f"- Flag: {lab_data['flag']}\n\n"
            f"Explain this to the patient in plain language. "
            f"Do NOT diagnose. Always say their doctor will explain the implications. "
            f"Always include this disclaimer: {APPROVED_DISCLAIMER}"
        )

        hist_str = format_history(state.get("history", []))
        lt_str = state.get("long_term_context", "No prior history.")
        response = _llm_response(context, LAB_REPORT_AGENT_PROMPT, "LabReportAgent", history=hist_str, long_term_context=lt_str)

    except AgentExecutionError:
        raise
    except Exception as e:
        logger.error(f"LabReportAgent failed: {str(e)}", exc_info=True)
        raise AgentExecutionError(f"Failed to process lab report: {str(e)}")

    violations = guardrail_scan(response)
    if violations:
        state["compliance_violation"] = True
        state = log_event(state, "LabReportAgent", "COMPLIANCE_VIOLATION", {
            "banned_patterns_found": violations
        })

    state["report_result"] = lab_data
    state["final_response"] = response
    state["response_source"] = "LabReportAgent"

    state = log_event(state, "LabReportAgent", "report_explained", {
        "test": lab_data["test"],
        "flag": lab_data["flag"],
        "critical": lab_data["critical"],
        "diagnosis_given": False,
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
            f"Your HbA1c result is 7.8% (normal range: 4.0 – 5.6%), flagged as HIGH. "
            f"Your doctor will explain what this means for your specific care plan at your next visit. "
            f"{APPROVED_DISCLAIMER}"
        )
    except Exception as e:
        logger.error(f"{agent_name} LLM call failed: {e}", exc_info=True)
        raise AgentExecutionError(f"LLM response generation failed: {e}")

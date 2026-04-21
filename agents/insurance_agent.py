"""
agents/insurance_agent.py — Insurance Claims Agent (Groq LLM)

Uses Groq to generate clear, factual claim status responses.
No financial commitments or legal advice permitted.
"""

import uuid
from langchain_core.messages import SystemMessage, HumanMessage

from state.patient_state import PatientState
from utils.audit import log_event, guardrail_scan
from utils.exceptions import AgentExecutionError
from utils.logger import get_logger
from agents.prompts import INSURANCE_AGENT_PROMPT
from utils.memory_utils import format_history

logger = get_logger("insurance_agent")


def insurance_agent(state: PatientState) -> PatientState:
    """
    Retrieves insurance claim status and generates a response via Groq LLM.
    """
    try:
        # Stub: in production calls Insurance Clearinghouse API
        result = {
            "claim_id": "CLM-99281-A",
            "status": "Processing",
            "date_submitted": "2024-10-15",
            "provider": "City General Hospital",
            "estimated_resolution": "2024-11-05",
        }

        context = (
            f"Patient query: {state['raw_query']}\n\n"
            f"Insurance Claim Details:\n"
            f"- Claim ID: {result['claim_id']}\n"
            f"- Provider: {result['provider']}\n"
            f"- Status: {result['status']}\n"
            f"- Date Submitted: {result['date_submitted']}\n"
            f"- Estimated Resolution: {result['estimated_resolution']}\n\n"
            f"Provide this information clearly. Make no financial guarantees."
        )

        hist_str = format_history(state.get("history", []))
        lt_str = state.get("long_term_context", "No prior history.")
        response = _llm_response(context, INSURANCE_AGENT_PROMPT, "InsuranceAgent", history=hist_str, long_term_context=lt_str)

    except AgentExecutionError:
        raise
    except Exception as e:
        logger.error(f"InsuranceAgent failed: {str(e)}", exc_info=True)
        raise AgentExecutionError(f"Failed to process insurance claim: {str(e)}")

    violations = guardrail_scan(response)
    if violations:
        state["compliance_violation"] = True

    state["insurance_result"] = result
    state["final_response"] = response
    state["response_source"] = "InsuranceAgent"

    state = log_event(state, "InsuranceAgent", "claim_status_retrieved", {
        "claim_id": result["claim_id"],
        "status": result["status"],
        "financial_commitment_made": False,
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
            "Your insurance claim CLM-99281-A from City General Hospital is currently processing. "
            "It was submitted on 2024-10-15 and is estimated to be resolved by 2024-11-05. "
            "For detailed coverage queries, please contact your insurance provider directly."
        )
    except Exception as e:
        logger.error(f"{agent_name} LLM call failed: {e}", exc_info=True)
        raise AgentExecutionError(f"LLM response generation failed: {e}")

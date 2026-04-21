"""
api.py — FastAPI REST API for the Healthcare Patient Inquiry System

Endpoints:
  POST /inquiry              → Full pipeline (classify → route → agent → guardrail)
  POST /classify             → Intent classification only
  POST /appointment          → Appointment agent directly
  POST /prescription         → Prescription agent directly
  POST /lab-report           → Lab report agent directly
  POST /insurance            → Insurance agent directly
  POST /escalate             → Human escalation agent directly
  GET  /health               → Health check
  GET  /dashboard            → Monitoring dashboard
  GET  /compliance-drift     → Compliance drift report
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, constr, field_validator
from typing import Optional, List, Any
import time
import uuid

from pipeline import handle_inquiry, build_pipeline, guardrail_check
from state.patient_state import PatientState, create_initial_state
from agents.intent_classifier import intent_classifier, route_intent
from agents.appointment_agent import appointment_agent
from agents.prescription_agent import prescription_agent
from agents.lab_report_agent import lab_report_agent
from agents.insurance_agent import insurance_agent
from agents.human_escalation_agent import human_escalation_agent
from monitoring.monitor import record_session, get_dashboard, detect_compliance_drift
from persistence.session_store import save_session, get_session, list_sessions
from utils.logger import get_logger

logger = get_logger("api")


# ─────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Patient Orchestrator API",
    description="Multi-Agent Healthcare Patient Inquiry System with Guardrails",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_logger(request: Request, call_next):
    req_id = str(uuid.uuid4())
    logger.info(f"Incoming Request: {request.method} {request.url.path} (ID: {req_id})")
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Response: {response.status_code} (ID: {req_id}, Time: {process_time:.4f}s)")
        return response
    except Exception as e:
        logger.error(f"Unhandled Server Error (ID: {req_id}): {str(e)}", exc_info=True)
        raise


# ─────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────────────────────

class InquiryRequest(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9-]+$", description="Anonymised patient identifier")
    query: str = Field(..., min_length=3, max_length=2000, description="Patient's natural language query")

    @field_validator('query')
    def query_must_not_be_blank(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be blank or just whitespace.")
        return v.strip()

class InquiryResponse(BaseModel):
    session_id: str
    patient_id: str
    intent: str
    response: str
    source: str
    escalated: bool
    compliance_violation: bool
    audit_log: List[dict]
    response_time_sec: float

class ClassifyResponse(BaseModel):
    intent: str
    confidence: float
    requires_verification: bool
    always_escalate: bool
    route_to: str

class HealthResponse(BaseModel):
    status: str
    version: str
    agents_available: List[str]


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Full Pipeline
# ─────────────────────────────────────────────────────────────

@app.post("/inquiry", response_model=InquiryResponse, tags=["Pipeline"])
def run_inquiry(req: InquiryRequest):
    """
    Run the full multi-agent pipeline:
    Query → Intent Classification → Agent Routing → Agent Execution → Guardrail Check → Response
    """
    start = time.time()
    result = handle_inquiry(req.patient_id, req.query)
    elapsed = round(time.time() - start, 3)

    # Record to monitoring
    record_session(
        session_id=result["session_id"],
        intent=result["intent"],
        response_time_sec=elapsed,
        escalated=result["escalated"],
        compliance_violation=result["compliance_violation"],
        audit_log=result["audit_log"],
    )

    # Persist to DB
    save_session(result, elapsed)

    return InquiryResponse(
        session_id=result["session_id"],
        patient_id=result["patient_id"],
        intent=result["intent"],
        response=result["response"],
        source=result["source"],
        escalated=result["escalated"],
        compliance_violation=result["compliance_violation"],
        audit_log=result["audit_log"],
        response_time_sec=elapsed,
    )


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Intent Classification Only
# ─────────────────────────────────────────────────────────────

@app.post("/classify", response_model=ClassifyResponse, tags=["Agents"])
def classify_intent(req: InquiryRequest):
    """Classify the intent of a patient query without executing an agent."""
    state = create_initial_state(req.patient_id, req.query)
    state = intent_classifier(state)
    route = route_intent(state)

    return ClassifyResponse(
        intent=state["intent"],
        confidence=state["intent_confidence"],
        requires_verification=state["requires_verification"],
        always_escalate=state["intent"] in {
            "mental_health_crisis", "emergency_symptom",
            "suicide_risk", "severe_allergic_reaction"
        },
        route_to=route,
    )


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Individual Agents
# ─────────────────────────────────────────────────────────────

@app.post("/appointment", tags=["Agents"])
def run_appointment(req: InquiryRequest):
    """Run the Appointment Scheduling Agent directly."""
    state = create_initial_state(req.patient_id, req.query)
    state["intent"] = "appointment"
    state = appointment_agent(state)
    state = guardrail_check(state)
    return _format_agent_response(state)


@app.post("/prescription", tags=["Agents"])
def run_prescription(req: InquiryRequest):
    """Run the Prescription Validation Agent directly."""
    state = create_initial_state(req.patient_id, req.query)
    state["intent"] = "prescription_validation"
    state = prescription_agent(state)
    state = guardrail_check(state)
    return _format_agent_response(state)


@app.post("/lab-report", tags=["Agents"])
def run_lab_report(req: InquiryRequest):
    """Run the Lab Report Explanation Agent directly."""
    state = create_initial_state(req.patient_id, req.query)
    state["intent"] = "lab_report"
    state = lab_report_agent(state)
    state = guardrail_check(state)
    return _format_agent_response(state)


@app.post("/insurance", tags=["Agents"])
def run_insurance(req: InquiryRequest):
    """Run the Insurance Claims Agent directly."""
    state = create_initial_state(req.patient_id, req.query)
    state["intent"] = "insurance_claim"
    state = insurance_agent(state)
    state = guardrail_check(state)
    return _format_agent_response(state)


@app.post("/escalate", tags=["Agents"])
def run_escalation(req: InquiryRequest):
    """Run the Human Escalation Agent directly."""
    state = create_initial_state(req.patient_id, req.query)
    state["intent"] = "general_inquiry"
    state = human_escalation_agent(state, reason="Manual escalation via API")
    state = guardrail_check(state)
    return _format_agent_response(state)


def _format_agent_response(state: dict) -> dict:
    """Helper to format a consistent agent response."""
    return {
        "session_id": state["session_id"],
        "response": state["final_response"],
        "source": state["response_source"],
        "escalated": state["escalated_to_human"],
        "compliance_violation": state["compliance_violation"],
        "audit_log": state["audit_log"],
    }


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Monitoring
# ─────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        agents_available=[
            "IntentClassifier",
            "AppointmentAgent",
            "PrescriptionAgent",
            "LabReportAgent",
            "InsuranceAgent",
            "HumanEscalationAgent",
        ],
    )


@app.get("/dashboard", tags=["Monitoring"])
def monitoring_dashboard():
    """Get the monitoring dashboard summary."""
    return get_dashboard()


@app.get("/compliance-drift", tags=["Monitoring"])
def compliance_drift(window: int = 500):
    """Check for compliance drift over the last N sessions."""
    return detect_compliance_drift(window)


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Persistence
# ─────────────────────────────────────────────────────────────

@app.get("/sessions", tags=["Persistence"])
def get_sessions(limit: int = 50, offset: int = 0):
    """List recent patient query sessions from the database."""
    return list_sessions(limit, offset)


@app.get("/sessions/{session_id}", tags=["Persistence"])
def get_session_by_id(session_id: str):
    """Retrieve details of a specific session, including its audit trail."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

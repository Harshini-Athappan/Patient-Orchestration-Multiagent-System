# Patient Orchestrator Agents
**A resilient, LLM-powered multi-agent healthcare orchestrator with persistent conversation memory and safety guardrails.**

A **multi-agent healthcare patient inquiry system** built with [LangGraph](https://github.com/langchain-ai/langgraph). The orchestrator classifies patient queries and routes them to specialised agents, with comprehensive guardrails, persistent memory, and LLM-powered orchestration.

## Architecture

```
Patient Query
     │
     ▼
┌─────────────────────┐
│  Intent Classifier   │   ← Orchestrator Router
│  (Node 0)           │
└────────┬────────────┘
         │
    ┌────┴────┬──────────┬──────────┬──────────────┐
    ▼         ▼          ▼          ▼              ▼
┌────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
│Appoint-│ │Prescrip- │ │Lab     │ │Insurance │ │Human         │
│ment    │ │tion      │ │Report  │ │Claims    │ │Escalation    │
│Agent   │ │Agent     │ │Agent   │ │Agent     │ │Agent         │
└───┬────┘ └────┬─────┘ └───┬────┘ └────┬─────┘ └──────┬───────┘
    │           │            │           │              │
    └───────────┴────────────┴───────────┴──────────────┘
                             │
                             ▼
                   ┌──────────────────┐
                   │ Guardrail Check  │   ← Final compliance gate
                   └────────┬─────────┘
                            ▼
                      Patient Response
```

## Agents

| # | Agent | Responsibility |
|---|-------|---------------|
| 0 | **Intent Classifier** | **Supervisor Orchestrator** (LLM) — routes to correct agent |
| 1 | **Appointment Agent** | Booking, rescheduling, cancellation |
| 2 | **Prescription Agent** | Refill status, pickup info (never dosage changes) |
| 3 | **Lab Report Agent** | Plain-language lab result explanations |
| 4 | **Insurance Agent** | Claim status, coverage queries |
| 5 | **Human Escalation** | Emergency fallback — tickets, on-call notification |

## 🧠 Memory System

The orchestrator implements a dual-layer memory system backed by SQLite:

1.  **Short-Term Memory (Contextual)**:
    -   Automatically retrieves the last 10 messages of the conversation for the specific patient.
    -   Allows agents to understand follow-up questions and maintain context across turns.
2.  **Long-Term Memory (Historical)**:
    -   Provides a summary of all past interactions (e.g., "Patient has previously booked 2 appointments").
    -   Helps the Supervisor Orchestrator make better routing decisions based on patient history.


## Guardrails

- **G1** — No medical advice beyond approved guidelines
- **G2** — No cross-session patient data sharing
- **G3** — Critical queries require verification before resolution
- **G4** — Prescription changes always need physician approval
- **G5** — Emergency intents always escalate to human
- **G6** — Response guardrail scan before every send

## Project Structure

```
Patient_Orchestrator_Agents/
├── config.py                  # Centralised constants
├── pipeline.py                # LangGraph orchestrator + public API
├── state/
│   └── patient_state.py       # PatientState TypedDict
├── agents/
│   ├── intent_classifier.py   # Intent classification + routing
│   ├── appointment_agent.py
│   ├── prescription_agent.py
│   ├── lab_report_agent.py
│   ├── insurance_agent.py
│   └── human_escalation_agent.py
├── guardrails/
│   └── guardrails.py          # All guardrail definitions
├── monitoring/
│   └── monitor.py             # Metrics, alerts, compliance drift
├── utils/
│   └── audit.py               # Audit logger
├── tests/
│   └── test_pipeline.py       # Unit + integration tests
├── requirements.txt
└── .env.example
```

## Setup & Quick Start

### 1. Configure Environment
Create a `.env` file from `.env.example`:
```bash
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the System (Unified Launcher)
This command handles port conflicts, starts the FastAPI backend, and launches the Streamlit UI:
```bash
python run.py
```
- **UI**: http://localhost:8502
- **API**: http://localhost:8004
- **Docs**: http://localhost:8004/docs

### 4. Run Tests
```bash
# Core pipeline tests
pytest tests/test_pipeline.py -v

# Memory turn-based test
python test_memory.py
```

## License

Internal use only.

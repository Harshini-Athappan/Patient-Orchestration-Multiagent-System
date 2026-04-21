"""
app.py — Streamlit UI for the Healthcare Patient Orchestrator

Features:
  - Interactive patient query input
  - Real-time agent flow visualisation
  - Step-by-step pipeline trace
  - Monitoring dashboard
  - Guardrail test panel
"""

import streamlit as st
import requests
import json
import time

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8004"

AGENT_ICONS = {
    "IntentClassifier": "🧠",
    "AppointmentAgent": "📅",
    "PrescriptionAgent": "💊",
    "LabReportAgent": "🔬",
    "InsuranceAgent": "🏥",
    "HumanEscalationAgent": "🚨",
    "GuardrailCheck": "🛡️",
}

AGENT_COLORS = {
    "IntentClassifier": "#6366f1",
    "AppointmentAgent": "#22c55e",
    "PrescriptionAgent": "#f59e0b",
    "LabReportAgent": "#3b82f6",
    "InsuranceAgent": "#8b5cf6",
    "HumanEscalationAgent": "#ef4444",
    "GuardrailCheck": "#14b8a6",
}

INTENT_DESCRIPTIONS = {
    "appointment": "Scheduling, rescheduling, or cancelling appointments",
    "prescription_validation": "Prescription refill status and pickup info",
    "prescription_change": "Medication changes — requires physician approval",
    "lab_report": "Explaining lab test results in plain language",
    "insurance_claim": "Insurance claim status and coverage queries",
    "emergency_symptom": "Life-threatening emergency — immediate escalation",
    "mental_health_crisis": "Mental health crisis — immediate escalation",
    "general_inquiry": "General question — routed to human support",
}

SAMPLE_QUERIES = [
    "I need to book an appointment with a general physician",
    "Can I get a refill for my Metformin prescription?",
    "Can you explain my HbA1c lab results?",
    "What is the status of my insurance claim?",
    "I have severe chest pain and can't breathe",
    "I want to stop taking my blood pressure medication",
    "I feel very depressed and in crisis",
]


# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Patient Orchestrator",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
    }
    .main-header h1 {
        color: #f8fafc;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: #94a3b8;
        font-size: 1rem;
        margin: 0.5rem 0 0 0;
    }

    /* Agent cards */
    .agent-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
        transition: all 0.2s ease;
    }
    .agent-card:hover {
        border-color: #6366f1;
        box-shadow: 0 0 12px rgba(99, 102, 241, 0.15);
    }
    .agent-card .agent-name {
        font-weight: 600;
        font-size: 1rem;
        color: #f1f5f9;
        margin-bottom: 0.25rem;
    }
    .agent-card .agent-detail {
        font-size: 0.85rem;
        color: #94a3b8;
    }

    /* Flow step */
    .flow-step {
        background: #1e293b;
        border-left: 4px solid #6366f1;
        border-radius: 0 12px 12px 0;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }
    .flow-step.escalated {
        border-left-color: #ef4444;
    }
    .flow-step.approved {
        border-left-color: #22c55e;
    }
    .flow-step .step-title {
        font-weight: 600;
        font-size: 0.95rem;
        color: #f1f5f9;
    }
    .flow-step .step-detail {
        font-size: 0.85rem;
        color: #94a3b8;
        margin-top: 0.25rem;
    }

    /* Status badges */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.3px;
    }
    .badge-clean {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    .badge-violation {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .badge-escalated {
        background: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    /* Metric card */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
    }
    .metric-card .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .metric-card .metric-label {
        font-size: 0.8rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 0.25rem;
    }

    /* Architecture diagram */
    .arch-box {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        font-family: 'Courier New', monospace;
        font-size: 0.8rem;
        color: #94a3b8;
        line-height: 1.6;
        white-space: pre;
        overflow-x: auto;
    }

    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🏥 Navigation")
    page = st.radio(
        "Go to",
        ["🩺 Patient Inquiry", "📊 Monitoring Dashboard", "🛡️ Guardrail Tester", "📐 Architecture"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("### 🤖 Active Agents")
    agents = [
        ("🧠", "Intent Classifier", "Routes queries"),
        ("📅", "Appointment Agent", "Scheduling"),
        ("💊", "Prescription Agent", "Refill & status"),
        ("🔬", "Lab Report Agent", "Result explanation"),
        ("🏥", "Insurance Agent", "Claim status"),
        ("🚨", "Escalation Agent", "Human fallback"),
    ]
    for icon, name, desc in agents:
        st.markdown(f"""
        <div class="agent-card">
            <div class="agent-name">{icon} {name}</div>
            <div class="agent-detail">{desc}</div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# HELPER: Call API
# ─────────────────────────────────────────────────────────────

def call_api(endpoint: str, payload: dict = None, method: str = "POST") -> dict:
    """Call the FastAPI backend."""
    try:
        url = f"{API_BASE}{endpoint}"
        if method == "POST":
            resp = requests.post(url, json=payload, timeout=10)
        else:
            resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to API. Make sure the FastAPI server is running: `python api.py`")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# PAGE 1: Patient Inquiry
# ─────────────────────────────────────────────────────────────

if page == "🩺 Patient Inquiry":
    st.markdown("""
    <div class="main-header">
        <h1>🩺 Patient Inquiry System</h1>
        <p>Multi-Agent Orchestrator with Healthcare Guardrails</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### 📝 Submit a Query")

        patient_id = st.text_input(
            "Patient ID",
            value="P001",
            placeholder="e.g. P001",
        )

        # Sample query selector
        selected_sample = st.selectbox(
            "Quick examples",
            ["— Type your own —"] + SAMPLE_QUERIES,
        )

        if selected_sample != "— Type your own —":
            query = st.text_area("Patient Query", value=selected_sample, height=100)
        else:
            query = st.text_area("Patient Query", placeholder="Describe your health inquiry...", height=100)

        submit = st.button("🚀 Submit Inquiry", type="primary", use_container_width=True)

    with col2:
        st.markdown("### 🔍 Pipeline Result")

        if submit and query:
            with st.spinner("Processing through agent pipeline..."):
                result = call_api("/inquiry", {"patient_id": patient_id, "query": query})

            if result:
                # Status badges
                compliance_badge = (
                    '<span class="badge badge-violation">⚠️ VIOLATION</span>'
                    if result["compliance_violation"]
                    else '<span class="badge badge-clean">✅ CLEAN</span>'
                )
                escalation_badge = (
                    '<span class="badge badge-escalated">🚨 ESCALATED</span>'
                    if result["escalated"]
                    else ""
                )

                st.markdown(f"""
                **Intent:** `{result['intent']}` &nbsp; {compliance_badge} {escalation_badge}
                """, unsafe_allow_html=True)

                st.markdown(f"**Handled by:** {AGENT_ICONS.get(result['source'], '🤖')} `{result['source']}`")
                st.markdown(f"**Response time:** `{result['response_time_sec']}s`")

                st.markdown("---")
                st.markdown("#### 💬 Response to Patient")
                st.info(result["response"])

                # Audit trail
                st.markdown("---")
                st.markdown("#### 📋 Audit Trail")
                for i, event in enumerate(result["audit_log"]):
                    agent = event.get("agent", "Unknown")
                    action = event.get("action", "")
                    icon = AGENT_ICONS.get(agent, "📌")

                    css_class = "flow-step"
                    if "VIOLATION" in action or "BLOCKED" in action:
                        css_class += " escalated"
                    elif "approved" in action or "confirmed" in action:
                        css_class += " approved"

                    # Build detail string from event keys
                    skip_keys = {"event_id", "timestamp", "session_id", "agent", "action"}
                    details = {k: v for k, v in event.items() if k not in skip_keys}
                    detail_str = " · ".join(f"{k}: {v}" for k, v in details.items()) if details else ""

                    st.markdown(f"""
                    <div class="{css_class}">
                        <div class="step-title">{icon} Step {i+1}: {agent} → {action}</div>
                        <div class="step-detail">{detail_str}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Raw JSON
                with st.expander("📦 Raw JSON Response"):
                    st.json(result)
        else:
            st.markdown("*Submit a query to see the pipeline in action.*")


# ─────────────────────────────────────────────────────────────
# PAGE 2: Monitoring Dashboard
# ─────────────────────────────────────────────────────────────

elif page == "📊 Monitoring Dashboard":
    st.markdown("""
    <div class="main-header">
        <h1>📊 Monitoring Dashboard</h1>
        <p>Real-time metrics, alerts, and compliance tracking</p>
    </div>
    """, unsafe_allow_html=True)

    dashboard = call_api("/dashboard", method="GET")

    if dashboard:
        if dashboard.get("status") == "no_data":
            st.warning("No sessions recorded yet. Submit some queries first!")
        else:
            # Metric cards
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{dashboard['total_sessions']}</div>
                    <div class="metric-label">Total Sessions</div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{dashboard['escalation_rate_pct']}%</div>
                    <div class="metric-label">Escalation Rate</div>
                </div>
                """, unsafe_allow_html=True)
            with c3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{dashboard['compliance_violation_rate_pct']}%</div>
                    <div class="metric-label">Violation Rate</div>
                </div>
                """, unsafe_allow_html=True)
            with c4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{dashboard['avg_response_time_sec']}s</div>
                    <div class="metric-label">Avg Response Time</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # Intent distribution
            st.markdown("### 📈 Intent Distribution")
            intent_dist = dashboard.get("intent_distribution", {})
            if intent_dist:
                st.bar_chart(intent_dist)

            # Alerts
            st.markdown("### 🚨 Alert Summary")
            alert_col1, alert_col2 = st.columns(2)
            with alert_col1:
                st.metric("Total Alerts", dashboard.get("total_alerts", 0))
            with alert_col2:
                st.metric("Critical Alerts", dashboard.get("critical_alerts", 0))

            # Compliance drift
            st.markdown("### 🔍 Compliance Drift Check")
            drift = call_api("/compliance-drift?window=100", method="GET")
            if drift:
                st.json(drift)


# ─────────────────────────────────────────────────────────────
# PAGE 3: Guardrail Tester
# ─────────────────────────────────────────────────────────────

elif page == "🛡️ Guardrail Tester":
    st.markdown("""
    <div class="main-header">
        <h1>🛡️ Guardrail Tester</h1>
        <p>Test if a response would pass or fail the compliance guardrails</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Test a Response")
    test_response = st.text_area(
        "Enter a response to test",
        placeholder="e.g. 'You should take 500mg of Aspirin daily'",
        height=120,
    )

    test_btn = st.button("🛡️ Run Guardrail Scan", type="primary")

    if test_btn and test_response:
        # Import guardrails directly for local testing
        from guardrails.guardrails import scan_for_violations, validate_response

        violations = scan_for_violations(test_response)
        is_safe, cleaned, violation_list = validate_response(test_response)

        if is_safe:
            st.success("✅ **PASSED** — No banned patterns detected. Response is safe to send.")
        else:
            st.error("🚫 **BLOCKED** — Banned medical advice patterns detected!")
            st.markdown("**Violations found:**")
            for v in violation_list:
                st.markdown(f"- 🔴 `{v}`")
            st.markdown("**Replacement response:**")
            st.info(cleaned)

    st.markdown("---")
    st.markdown("### 📋 Banned Patterns Reference")

    banned = [
        ("you should take", "Prescribing medication"),
        ("increase your dose/dosage/medication", "Dosage modification"),
        ("decrease your dose/dosage/medication", "Dosage modification"),
        ("stop taking", "Stopping medication"),
        ("you/this means/indicates/suggests you have", "Diagnosis"),
        ("you are diagnosed", "Diagnosis"),
        ("i recommend this medication/taking", "Prescription"),
        ("you have/likely have/probably have [disease]", "Diagnosis"),
        ("this result/test confirms", "Diagnosis confirmation"),
        ("no need to see a doctor", "Discouraging medical consultation"),
    ]

    for pattern, category in banned:
        st.markdown(f"- **{category}:** `{pattern}`")


# ─────────────────────────────────────────────────────────────
# PAGE 4: Architecture
# ─────────────────────────────────────────────────────────────

elif page == "📐 Architecture":
    st.markdown("""
    <div class="main-header">
        <h1>📐 System Architecture</h1>
        <p>How the multi-agent orchestrator works</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🔄 Pipeline Flow")
    st.markdown("""
    ```
    Patient Query
         │
         ▼
    ┌─────────────────────┐
    │  Intent Classifier   │   ← Orchestrator Router (Node 0)
    │  🧠 Classifies query │
    └────────┬────────────┘
             │
        ┌────┴────┬──────────┬──────────┬──────────────┐
        ▼         ▼          ▼          ▼              ▼
    ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
    │📅 Appt │ │💊 Rx     │ │🔬 Lab  │ │🏥 Ins.  │ │🚨 Human     │
    │Agent   │ │Agent     │ │Agent   │ │Agent     │ │Escalation    │
    └───┬────┘ └────┬─────┘ └───┬────┘ └────┬─────┘ └──────┬───────┘
        │           │            │           │              │
        └───────────┴────────────┴───────────┴──────────────┘
                                 │
                                 ▼
                       ┌──────────────────┐
                       │ 🛡️ Guardrail     │   ← Final compliance gate
                       │    Check         │
                       └────────┬─────────┘
                                ▼
                          Patient Response
    ```
    """)

    st.markdown("---")
    st.markdown("### 📁 Project Structure")

    st.markdown("""
    | File / Package | Purpose |
    |---|---|
    | `config.py` | Centralised constants (banned patterns, critical intents, disclaimer) |
    | `pipeline.py` | LangGraph orchestrator — wires agents into a graph, exposes `handle_inquiry()` |
    | `api.py` | FastAPI REST endpoints for all operations |
    | `app.py` | This Streamlit UI |
    | `state/patient_state.py` | `PatientState` TypedDict — the data that flows through every node |
    | `agents/intent_classifier.py` | Classifies query intent and decides routing |
    | `agents/appointment_agent.py` | Handles appointment booking/rescheduling |
    | `agents/prescription_agent.py` | Handles prescription refills (never dosage changes) |
    | `agents/lab_report_agent.py` | Explains lab results in plain language |
    | `agents/insurance_agent.py` | Returns insurance claim status |
    | `agents/human_escalation_agent.py` | Creates escalation tickets for human staff |
    | `guardrails/guardrails.py` | Banned patterns, session isolation, response validation |
    | `monitoring/monitor.py` | Metrics recording, alerting, compliance drift detection |
    | `utils/audit.py` | Audit logger (`log_event`) and guardrail scanner |
    | `tests/test_pipeline.py` | 25 unit + integration tests |
    """)

    st.markdown("---")
    st.markdown("### 🛡️ Guardrails Enforced")

    guardrails_info = [
        ("G1", "No Medical Advice", "Bans patterns like 'you should take', 'stop taking', 'you are diagnosed'"),
        ("G2", "Session Isolation", "Each session starts fresh — no cross-session patient data leaks"),
        ("G3", "Critical Verification", "Critical intents (prescription changes, emergencies) require verification"),
        ("G4", "Prescription Hard Stop", "Prescription changes ALWAYS escalate to a physician"),
        ("G5", "Emergency Escalation", "Emergency and mental health crisis intents always go to humans"),
        ("G6", "Response Gate", "Every response is scanned for banned patterns before sending"),
    ]

    for gid, name, desc in guardrails_info:
        st.markdown(f"**{gid} — {name}:** {desc}")

    st.markdown("---")
    st.markdown("### 🔌 API Endpoints")

    endpoints = [
        ("POST", "/inquiry", "Full pipeline — classify → route → agent → guardrail → response"),
        ("POST", "/classify", "Intent classification only"),
        ("POST", "/appointment", "Appointment agent directly"),
        ("POST", "/prescription", "Prescription agent directly"),
        ("POST", "/lab-report", "Lab report agent directly"),
        ("POST", "/insurance", "Insurance agent directly"),
        ("POST", "/escalate", "Human escalation agent directly"),
        ("GET", "/health", "Health check"),
        ("GET", "/dashboard", "Monitoring dashboard"),
        ("GET", "/compliance-drift", "Compliance drift report"),
    ]

    for method, path, desc in endpoints:
        badge_color = "#22c55e" if method == "GET" else "#3b82f6"
        st.markdown(f"- `{method}` **{path}** — {desc}")

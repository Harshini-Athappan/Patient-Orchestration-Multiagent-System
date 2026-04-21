"""
tests/test_pipeline.py — Unit tests for the healthcare agent pipeline

Run with:  pytest tests/test_pipeline.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import handle_inquiry
from guardrails.guardrails import (
    scan_for_violations,
    validate_response,
    is_critical,
    must_escalate,
    prescription_action_allowed,
    assert_session_isolation,
    SAFE_FALLBACK_RESPONSE,
)


# ─────────────────────────────────────────────────────────────
# PIPELINE INTEGRATION TESTS
# ─────────────────────────────────────────────────────────────

class TestIntentRouting:

    def test_appointment_query_routes_correctly(self):
        result = handle_inquiry("P001", "I need to book an appointment with a doctor")
        assert result["intent"] == "appointment"
        assert result["source"] == "AppointmentAgent"
        assert result["escalated"] is False

    def test_prescription_refill_routes_correctly(self):
        result = handle_inquiry("P002", "Can I get a refill for my Metformin prescription?")
        assert result["intent"] == "prescription_validation"
        assert result["source"] == "PrescriptionAgent"
        assert result["escalated"] is False

    def test_lab_report_routes_correctly(self):
        result = handle_inquiry("P003", "Can you explain my HbA1c lab result?")
        assert result["intent"] == "lab_report"
        assert result["source"] == "LabReportAgent"

    def test_insurance_query_routes_correctly(self):
        result = handle_inquiry("P004", "What is the status of my insurance claim?")
        assert result["intent"] == "insurance_claim"
        assert result["source"] == "InsuranceAgent"

    def test_emergency_always_escalates(self):
        result = handle_inquiry("P005", "I have severe chest pain and can't breathe")
        assert result["intent"] == "emergency_symptom"
        assert result["escalated"] is True
        assert result["source"] == "HumanEscalationAgent"

    def test_mental_health_crisis_always_escalates(self):
        result = handle_inquiry("P006", "I feel suicidal and in crisis")
        assert result["intent"] == "mental_health_crisis"
        assert result["escalated"] is True

    def test_prescription_change_escalates(self):
        result = handle_inquiry("P007", "I want to stop taking my blood pressure medication")
        assert result["escalated"] is True

    def test_each_session_is_independent(self):
        """Sessions must not share state."""
        r1 = handle_inquiry("P001", "Book an appointment")
        r2 = handle_inquiry("P001", "Book an appointment")
        assert r1["session_id"] != r2["session_id"]

    def test_audit_log_always_populated(self):
        result = handle_inquiry("P008", "Book an appointment with a physician")
        assert len(result["audit_log"]) > 0

    def test_every_response_has_source(self):
        result = handle_inquiry("P009", "Tell me about my insurance")
        assert result["source"] is not None


# ─────────────────────────────────────────────────────────────
# GUARDRAIL UNIT TESTS
# ─────────────────────────────────────────────────────────────

class TestGuardrails:

    def test_banned_pattern_you_should_take(self):
        violations = scan_for_violations("You should take 500mg of Aspirin daily.")
        assert len(violations) > 0

    def test_banned_pattern_stop_taking(self):
        violations = scan_for_violations("You can stop taking your medication now.")
        assert len(violations) > 0

    def test_banned_pattern_diagnosis(self):
        violations = scan_for_violations("This result confirms you have diabetes.")
        assert len(violations) > 0

    def test_clean_response_passes(self):
        violations = scan_for_violations(
            "Your appointment is confirmed for May 10 at 10:30 AM."
        )
        assert len(violations) == 0

    def test_validate_response_blocks_medical_advice(self):
        is_safe, response, violations = validate_response(
            "You should take 1000mg Paracetamol right now."
        )
        assert is_safe is False
        assert response == SAFE_FALLBACK_RESPONSE
        assert len(violations) > 0

    def test_validate_response_approves_safe_text(self):
        is_safe, response, violations = validate_response(
            "Your prescription refill is ready for pickup at the pharmacy."
        )
        assert is_safe is True
        assert len(violations) == 0

    def test_critical_intents_flagged(self):
        assert is_critical("prescription_change") is True
        assert is_critical("emergency_symptom") is True
        assert is_critical("appointment") is False

    def test_always_escalate_intents(self):
        assert must_escalate("mental_health_crisis") is True
        assert must_escalate("emergency_symptom") is True
        assert must_escalate("appointment") is False

    def test_prescription_change_blocked(self):
        allowed, reason = prescription_action_allowed("change_dose")
        assert allowed is False
        assert "physician" in reason.lower()

    def test_prescription_refill_allowed(self):
        allowed, reason = prescription_action_allowed("refill_status")
        assert allowed is True

    def test_session_isolation_passes_on_fresh_state(self):
        fresh_state = {
            "appointment_result": None,
            "prescription_result": None,
            "report_result": None,
            "insurance_result": None,
            "escalation_result": None,
        }
        ok, msg = assert_session_isolation(fresh_state)
        assert ok is True

    def test_session_isolation_fails_on_stale_state(self):
        stale_state = {
            "appointment_result": {"slot": "2025-05-01"},
            "prescription_result": None,
            "report_result": None,
            "insurance_result": None,
            "escalation_result": None,
        }
        ok, msg = assert_session_isolation(stale_state)
        assert ok is False
        assert "appointment_result" in msg


# ─────────────────────────────────────────────────────────────
# COMPLIANCE TESTS
# ─────────────────────────────────────────────────────────────

class TestCompliance:

    def test_no_compliance_violation_on_appointment(self):
        result = handle_inquiry("P010", "Schedule an appointment for next week")
        assert result["compliance_violation"] is False

    def test_emergency_response_includes_emergency_number(self):
        result = handle_inquiry("P011", "I have severe chest pain and can't breathe")
        assert "108" in result["response"] or "emergency" in result["response"].lower()

    def test_prescription_response_includes_disclaimer(self):
        result = handle_inquiry("P012", "Can I get a refill for my prescription?")
        assert "consult" in result["response"].lower() or "healthcare provider" in result["response"].lower()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

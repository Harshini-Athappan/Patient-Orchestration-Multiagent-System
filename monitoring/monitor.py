"""
monitoring/monitor.py — Real-time monitoring, alerting and compliance tracking

Tracks:
  - Response latency per agent
  - Escalation rate
  - Compliance violation rate
  - Intent distribution
  - Guardrail trigger frequency

In production: ship metrics to Prometheus / Grafana / CloudWatch.
"""

import datetime
import json
import uuid
from collections import defaultdict
from typing import List, Optional
from utils.logger import get_logger

logger = get_logger("monitor")


# ─────────────────────────────────────────────────────────────
# METRIC STORE (in-memory stub — replace with time-series DB)
# ─────────────────────────────────────────────────────────────

_metrics = defaultdict(list)
_alert_log = []

SUCCESS_METRICS = {
    "response_time_p95_target_sec": 3.0,     # 95th percentile < 3s
    "escalation_rate_target_pct": 15.0,      # <15% of queries escalated
    "compliance_violation_rate_target_pct": 0.1,   # <0.1% violations
    "patient_satisfaction_target": 4.2,      # Out of 5.0
    "first_contact_resolution_target_pct": 80.0,   # 80% resolved without human
}


# ─────────────────────────────────────────────────────────────
# LOG A COMPLETED SESSION
# ─────────────────────────────────────────────────────────────

def record_session(
    session_id: str,
    intent: str,
    response_time_sec: float,
    escalated: bool,
    compliance_violation: bool,
    audit_log: List[dict],
) -> None:
    """Called after every session completes."""
    record = {
        "session_id": session_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "intent": intent,
        "response_time_sec": round(response_time_sec, 3),
        "escalated": escalated,
        "compliance_violation": compliance_violation,
        "audit_event_count": len(audit_log),
    }
    _metrics["sessions"].append(record)

    # Trigger alerts
    _check_alerts(record)

    logger.info(f"Session recorded: {session_id} | {intent} | "
          f"{response_time_sec:.2f}s | escalated={escalated} | "
          f"violation={compliance_violation}")


# ─────────────────────────────────────────────────────────────
# ALERT ENGINE
# ─────────────────────────────────────────────────────────────

def _check_alerts(record: dict) -> None:
    """Evaluate alert conditions after each session."""

    # Alert 1: Compliance violation
    if record["compliance_violation"]:
        _fire_alert(
            level="CRITICAL",
            alert_type="COMPLIANCE_VIOLATION",
            session_id=record["session_id"],
            detail=f"Banned medical pattern detected in response. Intent: {record['intent']}",
            action="Block response. Notify compliance officer. Route to human.",
        )

    # Alert 2: Response time SLA breach
    if record["response_time_sec"] > SUCCESS_METRICS["response_time_p95_target_sec"]:
        _fire_alert(
            level="WARNING",
            alert_type="LATENCY_SLA_BREACH",
            session_id=record["session_id"],
            detail=f"Response time {record['response_time_sec']}s exceeded SLA of "
                   f"{SUCCESS_METRICS['response_time_p95_target_sec']}s",
            action="Page on-call engineering. Check agent health.",
        )

    # Alert 3: Rolling escalation rate check (every 100 sessions)
    sessions = _metrics["sessions"]
    if len(sessions) % 100 == 0 and len(sessions) > 0:
        recent = sessions[-100:]
        esc_rate = sum(1 for s in recent if s["escalated"]) / len(recent) * 100
        if esc_rate > SUCCESS_METRICS["escalation_rate_target_pct"]:
            _fire_alert(
                level="WARNING",
                alert_type="HIGH_ESCALATION_RATE",
                session_id="BATCH",
                detail=f"Escalation rate {esc_rate:.1f}% over last 100 sessions "
                       f"(target: <{SUCCESS_METRICS['escalation_rate_target_pct']}%)",
                action="Review intent classifier accuracy. Check for new query patterns.",
            )


def _fire_alert(
    level: str,
    alert_type: str,
    session_id: str,
    detail: str,
    action: str,
) -> None:
    alert = {
        "alert_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "level": level,
        "type": alert_type,
        "session_id": session_id,
        "detail": detail,
        "recommended_action": action,
    }
    _alert_log.append(alert)
    if level == "CRITICAL":
        logger.critical(f"{alert_type}: {detail}", extra={"alert": alert})
    else:
        logger.warning(f"{alert_type}: {detail}", extra={"alert": alert})


# ─────────────────────────────────────────────────────────────
# COMPLIANCE DRIFT DETECTION
# ─────────────────────────────────────────────────────────────

def detect_compliance_drift(window: int = 500) -> dict:
    """
    Analyse recent sessions for compliance drift patterns.
    In production: integrate with a statistical process control chart.
    """
    sessions = _metrics["sessions"][-window:]
    if not sessions:
        return {"status": "insufficient_data"}

    total = len(sessions)
    violations = sum(1 for s in sessions if s["compliance_violation"])
    escalations = sum(1 for s in sessions if s["escalated"])
    avg_latency = sum(s["response_time_sec"] for s in sessions) / total

    violation_rate = violations / total * 100
    escalation_rate = escalations / total * 100

    drift_detected = violation_rate > SUCCESS_METRICS["compliance_violation_rate_target_pct"]

    report = {
        "window": window,
        "total_sessions": total,
        "violation_rate_pct": round(violation_rate, 3),
        "escalation_rate_pct": round(escalation_rate, 1),
        "avg_response_time_sec": round(avg_latency, 3),
        "compliance_drift_detected": drift_detected,
        "alert_fired": drift_detected,
    }

    if drift_detected:
        _fire_alert(
            level="CRITICAL",
            alert_type="COMPLIANCE_DRIFT",
            session_id="BATCH",
            detail=f"Compliance violation rate {violation_rate:.3f}% "
                   f"exceeded target {SUCCESS_METRICS['compliance_violation_rate_target_pct']}%",
            action="Freeze autonomous responses. Escalate all to human until root cause identified.",
        )

    return report


# ─────────────────────────────────────────────────────────────
# DASHBOARD SUMMARY
# ─────────────────────────────────────────────────────────────

def get_dashboard() -> dict:
    """Returns a summary for the monitoring dashboard."""
    sessions = _metrics["sessions"]
    if not sessions:
        return {"status": "no_data"}

    total = len(sessions)
    return {
        "total_sessions": total,
        "escalation_rate_pct": round(sum(1 for s in sessions if s["escalated"]) / total * 100, 1),
        "compliance_violation_rate_pct": round(
            sum(1 for s in sessions if s["compliance_violation"]) / total * 100, 3
        ),
        "avg_response_time_sec": round(
            sum(s["response_time_sec"] for s in sessions) / total, 3
        ),
        "intent_distribution": _intent_counts(sessions),
        "total_alerts": len(_alert_log),
        "critical_alerts": sum(1 for a in _alert_log if a["level"] == "CRITICAL"),
        "success_metrics_targets": SUCCESS_METRICS,
    }


def _intent_counts(sessions: list) -> dict:
    counts = defaultdict(int)
    for s in sessions:
        counts[s["intent"]] += 1
    return dict(counts)

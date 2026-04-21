"""
utils/audit.py — Audit logging and guardrail scanning utilities

Used by every agent to record decisions for compliance audit.
"""

import uuid
import datetime
from typing import List

from config import BANNED_PATTERNS
from utils.logger import get_logger

logger = get_logger("audit")


def log_event(state: dict, agent: str, action: str, detail: dict) -> dict:
    """Append an audit entry to the session's audit log."""
    entry = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "session_id": state["session_id"],
        "agent": agent,
        "action": action,
        **detail,
    }
    state["audit_log"] = state.get("audit_log", []) + [entry]
    logger.info(f"Audit event: {action}", extra={"audit_detail": entry})
    return state


def guardrail_scan(text: str) -> List[str]:
    """Scan response text for banned medical advice patterns."""
    found = []
    lower = text.lower()
    for pattern in BANNED_PATTERNS:
        if pattern in lower:
            found.append(pattern)
    return found

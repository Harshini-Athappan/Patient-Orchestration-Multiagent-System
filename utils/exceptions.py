"""
utils/exceptions.py — Custom exception hierarchy for the patient orchestrator
"""

class PatientOrchestratorError(Exception):
    """Base exception for the orchestrator."""
    pass

class InputValidationError(PatientOrchestratorError):
    """Raised when input query or patient ID fails validation."""
    pass

class AgentExecutionError(PatientOrchestratorError):
    """Raised when an agent fails during execution (e.g., parsing, logic error)."""
    pass

class GuardrailViolationError(PatientOrchestratorError):
    """Raised when a strict compliance guardrail is breached and cannot be auto-mitigated."""
    pass

class ExternalServiceError(PatientOrchestratorError):
    """Raised when an external API (calendar, pharmacy, EHR) times out or fails."""
    pass

class SessionIsolationError(PatientOrchestratorError):
    """Raised when state data appears to leak between sessions."""
    pass

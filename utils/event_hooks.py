"""
utils/event_hooks.py — Event-driven hooks for non-linear workflow behavior
"""

from typing import Callable, List, Dict
from utils.logger import get_logger

logger = get_logger("event_hooks")

class EventDispatcher:
    def __init__(self):
        self.hooks: Dict[str, List[Callable]] = {
            "on_session_start": [],
            "on_intent_classified": [],
            "on_agent_complete": [],
            "on_escalation": [],
            "on_session_end": []
        }

    def register(self, event_name: str, callback: Callable):
        if event_name in self.hooks:
            self.hooks[event_name].append(callback)
        else:
            logger.warning(f"Attempted to register hook for unknown event: {event_name}")

    def dispatch(self, event_name: str, *args, **kwargs):
        if event_name in self.hooks:
            for callback in self.hooks[event_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error executing hook for {event_name}: {str(e)}")
        else:
            logger.warning(f"Attempted to dispatch unknown event: {event_name}")

# Global dispatcher instance
dispatcher = EventDispatcher()

# Example hooks
def load_patient_preferences(state):
    logger.info(f"Hook: Loaded patient preferences for {state.get('patient_id')}")

def notify_on_call(state):
    logger.info(f"Hook: Paging on-call staff for ticket {state.get('escalation_result', {}).get('ticket_id')}")

# Register default hooks
dispatcher.register("on_session_start", load_patient_preferences)
dispatcher.register("on_escalation", notify_on_call)

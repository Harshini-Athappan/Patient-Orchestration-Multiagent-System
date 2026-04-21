"""
utils/memory_utils.py — Utilities for formatting conversation memory
"""

def format_history(history: list) -> str:
    """Formats a list of message dicts into a readable string for prompts."""
    if not history:
        return "No recent messages."
    
    formatted = []
    for msg in history:
        role = "Patient" if msg["role"] == "user" else "Assistant"
        formatted.append(f"{role}: {msg['content']}")
    
    return "\n".join(formatted)

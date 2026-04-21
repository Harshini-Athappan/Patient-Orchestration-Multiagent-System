"""
utils/llm_client.py — Centralised Groq LLM client factory

All agents use this module to get a shared, configured LLM client.
Reads GROQ_API_KEY and GROQ_MODEL from environment (.env file).
"""

import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from utils.logger import get_logger

load_dotenv()

logger = get_logger("llm_client")

# Supported Groq models (fast, free tier available)
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


def get_llm(temperature: float = 0.1, model: str = None) -> ChatGroq:
    """
    Returns a configured ChatGroq LLM instance.
    - temperature=0.1 for consistent, deterministic agent responses.
    - Raises a clear error if the API key is not set.
    """
    if not GROQ_API_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Copy .env.example to .env and add your key from https://console.groq.com/"
        )

    selected_model = model or DEFAULT_MODEL
    logger.info(f"Initializing Groq LLM: model={selected_model}, temperature={temperature}")

    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=selected_model,
        temperature=temperature,
    )

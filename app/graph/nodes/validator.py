import logging
import re

from app.config import settings
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+",
    r"system\s*:\s*",
    r"<\s*script",
    r"javascript\s*:",
]


def validate(state: AgentState) -> dict:
    messages = state.get("messages", [])
    if not messages:
        return {"error": "No message provided", "intent": "rejected"}

    last_message = messages[-1].get("content", "")

    if not last_message.strip():
        return {"error": "Empty message", "intent": "rejected"}

    if len(last_message) > settings.max_message_length:
        return {"error": f"Message too long (max {settings.max_message_length} chars)", "intent": "rejected"}

    lower = last_message.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower):
            logger.warning("Prompt injection detected from user %s: %s", state.get("user_id"), pattern)
            return {"error": "Request rejected for safety reasons", "intent": "rejected"}

    return {}

import logging

import httpx

from app.config import settings
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

ROUTER_PROMPT = """You are an intent classifier for a kanban board AI assistant.
Classify the user's message into one of these intents:
- "rag" — the user is asking a question about the board's knowledge base, documentation, cards, history, or code
- "board_management" — the user wants to create, move, update, assign, or delete cards/columns
- "code" — the user wants to analyze code, find bugs, or get fix suggestions

Respond with ONLY the intent string, nothing else.

User message: {message}"""


def _classify_intent(message: str) -> str:
    payload = {
        "model": settings.kimi_model,
        "max_tokens": 20,
        "temperature": 1,
        "messages": [{"role": "user", "content": ROUTER_PROMPT.format(message=message)}],
    }

    try:
        resp = httpx.post(
            settings.kimi_api_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.kimi_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        intent = data["choices"][0]["message"]["content"].strip().lower().strip('"')

        if intent in ("rag", "board_management", "code"):
            return intent
        logger.warning("Unknown intent from LLM: %s, defaulting to rag", intent)
        return "rag"
    except Exception as e:
        logger.error("Intent classification failed: %s, defaulting to rag", e)
        return "rag"


def route(state: AgentState) -> dict:
    last_message = state["messages"][-1]["content"]
    intent = _classify_intent(last_message)
    logger.info("Classified intent: %s for message: %s", intent, last_message[:100])
    return {"intent": intent}

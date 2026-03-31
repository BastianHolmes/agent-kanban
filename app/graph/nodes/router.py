import logging

import httpx

from app.config import settings
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

ROUTER_PROMPT = """Classify the user message into exactly one category. Reply with ONLY one word — the category name.

Categories:
- rag — question about documentation, cards, board info, or general knowledge
- board_management — create, move, update, assign, or delete cards or columns
- code — analyze code, find bugs, suggest fixes

User message: {message}

Category:"""


def _classify_intent(message: str) -> str:
    payload = {
        "model": settings.kimi_router_model,
        "max_tokens": 100,
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
        msg = data["choices"][0]["message"]
        raw = (msg.get("content", "") or "").strip().lower()

        # If content is empty, check reasoning_content for the answer
        if not raw:
            reasoning = (msg.get("reasoning_content", "") or "").strip().lower()
            # Search reasoning for the intent keyword
            for candidate in ("board_management", "code", "rag"):
                if candidate in reasoning:
                    raw = candidate
                    break

        # Extract intent from response
        for candidate in ("board_management", "code", "rag"):
            if candidate in raw:
                return candidate

        logger.warning("Unknown intent from LLM: content=%s, defaulting to rag", raw)
        return "rag"
    except Exception as e:
        logger.error("Intent classification failed: %s, defaulting to rag", e)
        return "rag"


def route(state: AgentState) -> dict:
    last_message = state["messages"][-1]["content"]
    intent = _classify_intent(last_message)
    logger.info("Classified intent: %s for message: %s", intent, last_message[:100])
    return {"intent": intent}

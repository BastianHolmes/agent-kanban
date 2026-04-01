import logging

import httpx

from app.config import settings
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

BOARD_KEYWORDS = [
    "создай", "создать", "добавь", "добавить", "перемести", "переместить",
    "перенеси", "перенести", "назначь", "назначить", "удали", "удалить",
    "обнови", "обновить", "измени", "изменить", "отредактируй", "редактируй",
    "карточку", "карточка", "задачу", "задача", "колонку", "столбец",
    "create card", "move card", "assign", "delete card", "update card",
]

CODE_KEYWORDS = [
    "код", "баг", "bug", "fix", "исправь", "исправить", "файл",
    "функци", "ошибк", "code", "debug", "analyze", "анализ кода",
    "suggest fix", "предложи исправление",
]

ROUTER_PROMPT = """Classify the user message into exactly one category. Reply with ONLY one word — the category name.

Categories:
- rag — question about documentation, cards, board info, or general knowledge
- board_management — create, move, update, assign, or delete cards or columns
- code — analyze code, find bugs, suggest fixes

User message: {message}

Category:"""


def _keyword_classify(message: str) -> str | None:
    """Fast keyword-based classification. Returns None if no match."""
    lower = message.lower()
    for kw in BOARD_KEYWORDS:
        if kw in lower:
            return "board_management"
    for kw in CODE_KEYWORDS:
        if kw in lower:
            return "code"
    return None


def _llm_classify(message: str) -> str | None:
    """LLM-based classification. Returns None on failure."""
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

        if not raw:
            reasoning = (msg.get("reasoning_content", "") or "").strip().lower()
            for candidate in ("board_management", "code", "rag"):
                if candidate in reasoning:
                    return candidate

        for candidate in ("board_management", "code", "rag"):
            if candidate in raw:
                return candidate

        return None
    except Exception as e:
        logger.error("LLM classification failed: %s", e)
        return None


def _classify_intent(message: str) -> str:
    # 1. Try keyword match first (fast, reliable)
    kw_result = _keyword_classify(message)
    if kw_result:
        logger.info("Keyword classified: %s", kw_result)
        return kw_result

    # 2. Fall back to LLM
    llm_result = _llm_classify(message)
    if llm_result:
        logger.info("LLM classified: %s", llm_result)
        return llm_result

    # 3. Default
    logger.warning("Could not classify intent for: %s, defaulting to rag", message[:100])
    return "rag"


def route(state: AgentState) -> dict:
    last_message = state["messages"][-1]["content"]
    intent = _classify_intent(last_message)
    logger.info("Classified intent: %s for message: %s", intent, last_message[:100])
    return {"intent": intent}

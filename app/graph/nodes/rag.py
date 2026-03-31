import logging

import httpx

from app.config import settings
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """Ты — AI-ассистент канбан-доски "{board_key}".
Отвечай на основе предоставленного контекста.
Если в контексте нет ответа — скажи об этом честно.
Ссылайся на источники: [Документ: название] или [Карточка: {board_key}-N].
Отвечай на языке вопроса."""


def rag_node(state: AgentState, retriever) -> dict:
    query = state["messages"][-1]["content"]
    board_id = state["board_id"]
    board_key = state["board_key"]

    results = retriever.search(query, board_id=board_id, top_k=10)

    context_parts = []
    sources = []
    for r in results:
        source_type = r["source_type"]
        content = r["content"]
        context_parts.append(content)

        if source_type == "card":
            sources.append({"type": "card", "ref": f"{board_key}-{r['card_number']}", "title": r.get("title", "")})
        elif source_type == "doc":
            sources.append({"type": "doc", "ref": r.get("file_id", ""), "title": r.get("title", "")})
        elif source_type == "code":
            sources.append({"type": "code", "ref": r.get("file_path", ""), "repo_id": r.get("repo_id", "")})

    context = "\n\n---\n\n".join(context_parts)

    system = RAG_SYSTEM_PROMPT.format(board_key=board_key)

    # Build messages with conversation history
    all_messages = state.get("messages", [])
    llm_messages = [{"role": "system", "content": system}]
    # Add previous messages as context (keep last 10 for token limit)
    for msg in all_messages[:-1][-10:]:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})
    # Add current question with RAG context
    llm_messages.append({"role": "user", "content": f"Контекст:\n{context}\n\nВопрос: {query}"})

    payload = {
        "model": settings.kimi_model,
        "max_tokens": 2000,
        "temperature": 1,
        "messages": llm_messages,
    }

    try:
        resp = httpx.post(
            settings.kimi_api_url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.kimi_api_key}", "Content-Type": "application/json"},
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        answer = msg.get("content", "") or msg.get("reasoning_content", "")
    except Exception as e:
        logger.error("RAG LLM call failed: %s", e)
        answer = "Произошла ошибка при генерации ответа. Попробуйте позже."
        sources = []

    return {"response": answer, "sources": sources, "rag_context": results}

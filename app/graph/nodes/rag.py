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
    user_prompt = f"Контекст:\n{context}\n\nВопрос: {query}"

    payload = {
        "model": settings.kimi_model,
        "max_tokens": 2000,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
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
        answer = data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("RAG LLM call failed: %s", e)
        answer = "Произошла ошибка при генерации ответа. Попробуйте позже."
        sources = []

    return {"response": answer, "sources": sources, "rag_context": results}

import json
import logging

import httpx

from app.config import settings
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

CODE_PROMPT = """Ты — AI-ассистент для анализа кода на канбан-доске "{board_key}".

Доступные действия:
- search_code: Поиск по коду. Params: {{"query": "..."}}
- suggest_fix: Предложить исправление для карточки. Params: {{"card_number": N}}

Контекст из кодовой базы:
{code_context}

Проанализируй запрос и ответь. Если нужно действие, ответь JSON:
{{
  "action": "tool_name",
  "params": {{...}},
  "explanation": "..."
}}

Если можешь ответить на основе контекста, просто ответь текстом."""


def code_node(state: AgentState, retriever, go_client) -> dict:
    query = state["messages"][-1]["content"]
    board_id = state["board_id"]
    board_key = state["board_key"]

    results = retriever.search(query, board_id=board_id, source_type="code", top_k=5)
    code_context = "\n\n".join(f"File: {r.get('file_path', 'unknown')}\n```\n{r['content']}\n```" for r in results)
    sources = [{"type": "code", "ref": r.get("file_path", ""), "repo_id": r.get("repo_id", "")} for r in results]

    prompt = CODE_PROMPT.format(board_key=board_key, code_context=code_context or "Код не найден в индексе.")

    payload = {
        "model": settings.kimi_model,
        "max_tokens": 2000,
        "temperature": 1,
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": query}],
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
        logger.error("Code node LLM call failed: %s", e)
        return {"response": "Не удалось проанализировать код.", "sources": []}

    try:
        cleaned = answer.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        action_data = json.loads(cleaned)
        if action_data.get("action") == "suggest_fix":
            return {
                "pending_action": {"action": "suggest_fix", "params": action_data.get("params", {}), "explanation": action_data.get("explanation", "")},
                "response": action_data.get("explanation", ""),
                "sources": sources,
            }
    except (json.JSONDecodeError, KeyError):
        pass

    return {"response": answer, "sources": sources}

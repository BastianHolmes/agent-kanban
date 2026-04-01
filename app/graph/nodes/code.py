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
        msg = data["choices"][0]["message"]
        answer = msg.get("content", "") or msg.get("reasoning_content", "")
    except Exception as e:
        logger.error("Code node LLM call failed: %s", e)
        return {"response": "Не удалось проанализировать код.", "sources": []}

    try:
        # Try to extract JSON action from response
        action_data = None
        cleaned = answer.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            action_data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            # Search for JSON in text
            import re
            for match in re.finditer(r'\{', answer):
                start = match.start()
                depth = 0
                for i in range(start, len(answer)):
                    if answer[i] == '{': depth += 1
                    elif answer[i] == '}':
                        depth -= 1
                        if depth == 0:
                            try: action_data = json.loads(answer[start:i + 1])
                            except: pass
                            break
                if action_data: break

        if action_data and action_data.get("action") == "suggest_fix":
            return {
                "pending_action": {"action": "suggest_fix", "params": action_data.get("params", {}), "explanation": action_data.get("explanation", "")},
                "response": action_data.get("explanation", ""),
                "sources": sources,
            }
    except Exception:
        pass

    return {"response": answer, "sources": sources}

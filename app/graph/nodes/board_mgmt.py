import json
import logging

import httpx

from app.config import settings
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

BOARD_MGMT_PROMPT = """Ты — AI-ассистент для управления канбан-доской "{board_key}".
У тебя есть следующие инструменты:

{tools_description}

Текущее состояние доски:
{board_state}

Проанализируй запрос пользователя и определи, какое действие нужно выполнить.
Ответь в формате JSON:
{{
  "action": "tool_name",
  "params": {{...}},
  "explanation": "Краткое объяснение на русском"
}}

Если запрос не требует действия, ответь:
{{
  "action": "none",
  "params": {{}},
  "explanation": "Объяснение"
}}"""

TOOLS_DESCRIPTION = """- create_card: Создать карточку. Params: {"column_id": "...", "title": "...", "description": "..."}
- move_card: Переместить карточку. Params: {"card_number": N, "target_column_id": "..."}
- assign_card: Назначить исполнителя. Params: {"card_number": N, "assignee_id": "..."}
- update_card: Обновить карточку. Params: {"card_number": N, "title": "...", "description": "...", "priority": "..."}"""


import re


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from text that may contain markdown or reasoning."""
    if not text:
        return None

    # Try parsing the whole text
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Search for JSON object in text using brace matching
    for match in re.finditer(r'\{', text):
        start = match.start()
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break
    return None


def board_mgmt_node(state: AgentState, go_client) -> dict:
    query = state["messages"][-1]["content"]
    board_key = state["board_key"]
    board_id = state["board_id"]
    user_id = state["user_id"]
    user_role = state["user_role"]
    auth_token = state.get("auth_token", "")

    try:
        board_state = go_client.get_board_full(board_key, user_id, auth_token)
    except Exception as e:
        logger.error("Failed to fetch board state: %s", e)
        return {"response": "Не удалось получить состояние доски.", "sources": []}

    prompt = BOARD_MGMT_PROMPT.format(
        board_key=board_key,
        tools_description=TOOLS_DESCRIPTION,
        board_state=json.dumps(board_state, ensure_ascii=False, indent=2),
    )

    # Build messages with conversation history
    all_messages = state.get("messages", [])
    llm_messages = [{"role": "system", "content": prompt}]
    for msg in all_messages[:-1][-10:]:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})
    llm_messages.append({"role": "user", "content": query})

    payload = {
        "model": settings.kimi_model,
        "max_tokens": 4000,
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
        raw = msg.get("content", "") or msg.get("reasoning_content", "")
        logger.info("Board mgmt raw response (first 500 chars): %s", raw[:500])

        # Try to extract JSON from the response
        action_data = _extract_json(raw)
        if action_data is None:
            logger.error("Could not extract JSON action from LLM response")
            return {"response": raw or "Не удалось определить действие.", "sources": []}
    except Exception as e:
        logger.error("Board mgmt LLM call failed: %s", e)
        return {"response": "Не удалось обработать запрос на управление доской.", "sources": []}

    action = action_data.get("action", "none")
    explanation = action_data.get("explanation", "")

    if action == "none":
        return {"response": explanation, "sources": []}

    write_actions = {"create_card", "move_card", "assign_card", "update_card"}
    if action in write_actions and user_role == "guest":
        return {"response": "У вас нет прав для выполнения этого действия.", "sources": []}

    return {
        "pending_action": {"action": action, "params": action_data.get("params", {}), "explanation": explanation},
        "response": explanation,
        "sources": [],
    }

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


def board_mgmt_node(state: AgentState, go_client) -> dict:
    query = state["messages"][-1]["content"]
    board_key = state["board_key"]
    board_id = state["board_id"]
    user_id = state["user_id"]
    user_role = state["user_role"]

    try:
        board_state = go_client.get_board_state(board_id, user_id)
    except Exception as e:
        logger.error("Failed to fetch board state: %s", e)
        return {"response": "Не удалось получить состояние доски.", "sources": []}

    prompt = BOARD_MGMT_PROMPT.format(
        board_key=board_key,
        tools_description=TOOLS_DESCRIPTION,
        board_state=json.dumps(board_state, ensure_ascii=False, indent=2),
    )

    payload = {
        "model": settings.kimi_model,
        "max_tokens": 1000,
        "temperature": 1,
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": query}],
    }

    try:
        resp = httpx.post(
            settings.kimi_api_url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.kimi_api_key}", "Content-Type": "application/json"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        raw = msg.get("content", "") or msg.get("reasoning_content", "")

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        action_data = json.loads(cleaned)
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

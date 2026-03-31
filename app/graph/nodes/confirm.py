import logging

from app.graph.state import AgentState

logger = logging.getLogger(__name__)

SAFE_ACTIONS = {"search_code", "search_docs", "search_cards", "get_card", "get_board_state", "none"}


def confirm_node(state: AgentState) -> dict:
    pending = state.get("pending_action")
    if not pending:
        return {}

    action = pending.get("action", "none")

    if action in SAFE_ACTIONS:
        return {"confirmed": True}

    logger.info("Action '%s' requires user confirmation", action)
    return {"confirmed": None}

import logging

from app.api.go_client import GoClient

logger = logging.getLogger(__name__)

ROLE_PERMISSIONS = {
    "guest": set(),
    "member": {"create_card", "update_card", "assign_card"},
    "admin": {"create_card", "move_card", "assign_card", "update_card"},
    "developer": {"create_card", "move_card", "assign_card", "update_card"},
}


def check_permission(role: str, action: str) -> bool:
    return action in ROLE_PERMISSIONS.get(role, set())


def execute_board_action(go_client: GoClient, board_key: str, user_id: str, user_role: str, action: str, params: dict, auth_token: str = "") -> dict:
    if not check_permission(user_role, action):
        return {"success": False, "error": "Insufficient permissions"}

    try:
        if action == "create_card":
            result = go_client.create_card(board_key, params["column_id"], params["title"], params.get("description", ""), user_id, auth_token)
            return {"success": True, "result": result}
        elif action == "move_card":
            result = go_client.move_card(board_key, params["card_number"], params["target_column_id"], user_id, auth_token)
            return {"success": True, "result": result}
        elif action == "assign_card":
            result = go_client.assign_card(board_key, params["card_number"], params["assignee_id"], user_id, auth_token)
            return {"success": True, "result": result}
        elif action == "update_card":
            updates = {k: v for k, v in params.items() if k != "card_number"}
            result = go_client.update_card(board_key, params["card_number"], updates, user_id, auth_token)
            return {"success": True, "result": result}
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        logger.error("Board action '%s' failed: %s", action, e)
        return {"success": False, "error": str(e)}

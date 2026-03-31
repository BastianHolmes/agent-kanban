import logging

from app.api.go_client import GoClient

logger = logging.getLogger(__name__)


def suggest_fix(go_client: GoClient, board_key: str, card_number: int, user_id: str) -> dict:
    try:
        return go_client.suggest_fix(board_key, card_number, user_id)
    except Exception as e:
        logger.error("Suggest fix failed for %s-%d: %s", board_key, card_number, e)
        return {"error": str(e)}


def apply_fix(go_client: GoClient, board_key: str, card_number: int, user_id: str) -> dict:
    try:
        return go_client.apply_fix(board_key, card_number, user_id)
    except Exception as e:
        logger.error("Apply fix failed for %s-%d: %s", board_key, card_number, e)
        return {"error": str(e)}

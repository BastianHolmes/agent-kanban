import logging

from app.api.go_client import GoClient
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)


def search_docs(retriever: Retriever, board_id: str, query: str) -> list[dict]:
    return retriever.search(query, board_id=board_id, source_type="doc", top_k=10)


def search_cards(retriever: Retriever, board_id: str, query: str) -> list[dict]:
    return retriever.search(query, board_id=board_id, source_type="card", top_k=10)


def search_code(retriever: Retriever, board_id: str, query: str) -> list[dict]:
    return retriever.search(query, board_id=board_id, source_type="code", top_k=5)


def get_card(go_client: GoClient, board_key: str, card_number: int, user_id: str) -> dict:
    try:
        return go_client.get_card(board_key, card_number, user_id)
    except Exception as e:
        logger.error("Failed to get card %s-%d: %s", board_key, card_number, e)
        return {"error": str(e)}

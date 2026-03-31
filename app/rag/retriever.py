import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


def _collection_name(board_id: str) -> str:
    return f"board_{board_id}"


class Retriever:
    def __init__(self, qdrant: QdrantClient, embeddings: EmbeddingService):
        self.qdrant = qdrant
        self.embeddings = embeddings

    def search(self, query: str, board_id: str, top_k: int = 10, source_type: str | None = None) -> list[dict]:
        collection = _collection_name(board_id)
        if not self.qdrant.collection_exists(collection):
            logger.info("Collection %s does not exist yet, returning empty results", collection)
            return []

        vector = self.embeddings.encode(query)
        query_filter = None
        if source_type:
            query_filter = Filter(must=[FieldCondition(key="source_type", match=MatchValue(value=source_type))])
        results = self.qdrant.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=query_filter,
            limit=top_k,
        )
        return [{"score": hit.score, **hit.payload} for hit in results]

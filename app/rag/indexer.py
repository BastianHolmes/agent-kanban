import logging
from uuid import uuid5, NAMESPACE_URL

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

from app.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

VECTOR_SIZE = 384
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _collection_name(board_id: str) -> str:
    return f"board_{board_id}"


def _point_id(board_id: str, source_type: str, source_id: str) -> str:
    raw = f"{board_id}:{source_type}:{source_id}"
    return str(uuid5(NAMESPACE_URL, raw))


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


class Indexer:
    def __init__(self, qdrant: QdrantClient, embeddings: EmbeddingService):
        self.qdrant = qdrant
        self.embeddings = embeddings

    def ensure_collection(self, board_id: str):
        name = _collection_name(board_id)
        if not self.qdrant.collection_exists(name):
            self.qdrant.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection: %s", name)

    def delete_collection(self, board_id: str):
        name = _collection_name(board_id)
        if self.qdrant.collection_exists(name):
            self.qdrant.delete_collection(name)
            logger.info("Deleted Qdrant collection: %s", name)

    def index_card(self, board_id: str, card_number: int, title: str, description: str, column: str, assignee: str | None = None, priority: str | None = None, tags: list[str] | None = None):
        self.ensure_collection(board_id)
        text = f"Card {card_number}: {title}\n{description or ''}"
        vector = self.embeddings.encode(text)
        point = PointStruct(
            id=_point_id(board_id, "card", str(card_number)),
            vector=vector,
            payload={"source_type": "card", "card_number": card_number, "title": title, "content": text, "column": column, "assignee": assignee or "", "priority": priority or "", "tags": tags or []},
        )
        self.qdrant.upsert(collection_name=_collection_name(board_id), points=[point])

    def index_document(self, board_id: str, file_id: str, title: str, content: str, folder_path: str):
        self.ensure_collection(board_id)
        chunks = _chunk_text(f"{title}\n{content}")
        points = []
        for i, chunk in enumerate(chunks):
            vector = self.embeddings.encode(chunk)
            points.append(PointStruct(
                id=_point_id(board_id, "doc", f"{file_id}:{i}"),
                vector=vector,
                payload={"source_type": "doc", "file_id": file_id, "title": title, "content": chunk, "folder_path": folder_path, "chunk_index": i},
            ))
        self.qdrant.upsert(collection_name=_collection_name(board_id), points=points)

    def index_movement(self, board_id: str, card_number: int, from_column: str, to_column: str, timestamp: str):
        self.ensure_collection(board_id)
        text = f"Card {card_number} moved from '{from_column}' to '{to_column}' at {timestamp}"
        vector = self.embeddings.encode(text)
        point = PointStruct(
            id=_point_id(board_id, "movement", f"{card_number}:{timestamp}"),
            vector=vector,
            payload={"source_type": "movement", "card_number": card_number, "content": text, "from_column": from_column, "to_column": to_column, "timestamp": timestamp},
        )
        self.qdrant.upsert(collection_name=_collection_name(board_id), points=[point])

    def index_code_file(self, board_id: str, repo_id: str, file_path: str, content: str, language: str):
        self.ensure_collection(board_id)
        chunks = _chunk_text(content, chunk_size=800, overlap=50)
        points = []
        for i, chunk in enumerate(chunks):
            vector = self.embeddings.encode(chunk)
            points.append(PointStruct(
                id=_point_id(board_id, "code", f"{repo_id}:{file_path}:{i}"),
                vector=vector,
                payload={"source_type": "code", "repo_id": repo_id, "file_path": file_path, "content": chunk, "language": language, "chunk_index": i},
            ))
        self.qdrant.upsert(collection_name=_collection_name(board_id), points=points)

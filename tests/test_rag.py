import pytest
from unittest.mock import MagicMock
from qdrant_client.models import ScoredPoint

from app.rag.embeddings import EmbeddingService
from app.rag.indexer import Indexer
from app.rag.retriever import Retriever


class TestEmbeddingService:
    def test_encode_returns_list_of_floats(self, mock_embeddings):
        svc = EmbeddingService.__new__(EmbeddingService)
        svc.model = mock_embeddings
        result = svc.encode("test query")
        assert len(result) == 1024
        assert all(isinstance(v, float) for v in result)

    def test_encode_batch(self, mock_embeddings):
        mock_embeddings.encode.return_value = [[0.1] * 1024, [0.2] * 1024]
        svc = EmbeddingService.__new__(EmbeddingService)
        svc.model = mock_embeddings
        result = svc.encode_batch(["a", "b"])
        assert len(result) == 2


class TestIndexer:
    def test_index_card(self, mock_qdrant, mock_embeddings):
        embed_svc = EmbeddingService.__new__(EmbeddingService)
        embed_svc.model = mock_embeddings
        indexer = Indexer(mock_qdrant, embed_svc)
        indexer.index_card(board_id="board-1", card_number=1, title="Fix login bug", description="Users cannot login with SSO", column="In Progress", assignee="John", priority="high", tags=["bug"])
        mock_qdrant.upsert.assert_called_once()

    def test_index_document(self, mock_qdrant, mock_embeddings):
        embed_svc = EmbeddingService.__new__(EmbeddingService)
        embed_svc.model = mock_embeddings
        indexer = Indexer(mock_qdrant, embed_svc)
        indexer.index_document(board_id="board-1", file_id="file-1", title="API Guide", content="# API Guide\n\nThis is a guide to our API...", folder_path="/docs")
        assert mock_qdrant.upsert.call_count >= 1


class TestRetriever:
    def test_search_returns_results(self, mock_qdrant, mock_embeddings):
        mock_qdrant.search.return_value = [
            ScoredPoint(id="point-1", version=1, score=0.9, payload={"source_type": "card", "title": "Fix bug", "content": "Fix login"}, vector=None)
        ]
        embed_svc = EmbeddingService.__new__(EmbeddingService)
        embed_svc.model = mock_embeddings
        retriever = Retriever(mock_qdrant, embed_svc)
        results = retriever.search("login bug", board_id="board-1", top_k=10)
        assert len(results) == 1
        assert results[0]["source_type"] == "card"

    def test_search_with_source_filter(self, mock_qdrant, mock_embeddings):
        mock_qdrant.search.return_value = []
        embed_svc = EmbeddingService.__new__(EmbeddingService)
        embed_svc.model = mock_embeddings
        retriever = Retriever(mock_qdrant, embed_svc)
        retriever.search("query", board_id="board-1", source_type="doc")
        call_kwargs = mock_qdrant.search.call_args
        assert call_kwargs is not None

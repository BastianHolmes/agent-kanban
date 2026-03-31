import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_qdrant():
    client = MagicMock()
    client.upsert = MagicMock()
    client.search = MagicMock(return_value=[])
    client.delete_collection = MagicMock()
    client.collection_exists = MagicMock(return_value=True)
    client.create_collection = MagicMock()
    return client


@pytest.fixture
def mock_embeddings():
    model = MagicMock()
    model.encode.return_value = [[0.1] * 1024]
    return model

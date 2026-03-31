import logging
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        logger.info("Loading embedding model: %s", settings.embedding_model)
        self.model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded, dimension: %d", self.model.get_sentence_embedding_dimension())

    def encode(self, text: str) -> list[float]:
        vector = self.model.encode([text])[0]
        return vector.tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts)
        return [v.tolist() for v in vectors]

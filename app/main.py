import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from qdrant_client import QdrantClient

from app.config import settings
from app.api.routes import router as agent_router
from app.middleware.metrics import MetricsMiddleware, metrics_endpoint
from app.rag.embeddings import EmbeddingService
from app.rag.indexer import Indexer
from app.rag.retriever import Retriever
from app.api.go_client import GoClient
from app.graph.graph import build_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Agent service starting on port %d", settings.port)

    qdrant = QdrantClient(url=settings.qdrant_url)
    embeddings = EmbeddingService()
    indexer = Indexer(qdrant, embeddings)
    retriever = Retriever(qdrant, embeddings)
    go_client = GoClient()
    graph = build_graph(retriever, go_client)

    app.state.graph = graph
    app.state.indexer = indexer
    app.state.retriever = retriever
    app.state.go_client = go_client
    app.state.pending_actions = {}
    app.state.sessions = {}  # session_id -> list of messages
    app.state.reindexed_boards = set()  # boards already reindexed this session

    from app.scheduler.jobs import start_scheduler, stop_scheduler
    start_scheduler(indexer, go_client)

    logger.info("Agent service ready")
    yield
    stop_scheduler()
    logger.info("Agent service shutting down")


app = FastAPI(title="Easy Kanban Agent", lifespan=lifespan)
app.include_router(agent_router)
app.add_middleware(MetricsMiddleware)
app.add_route("/metrics", metrics_endpoint)


@app.get("/health")
async def health():
    return {"status": "ok"}

import time

from fastapi import Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "agent_requests_total",
    "Total agent requests",
    ["method", "path", "status"],
)

REQUEST_DURATION = Histogram(
    "agent_request_duration_seconds",
    "Agent request duration",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

LLM_TOKENS = Counter(
    "agent_llm_tokens_total",
    "LLM tokens used",
    ["direction"],
)

TOOL_CALLS = Counter(
    "agent_tool_calls_total",
    "Tool call count",
    ["tool", "status"],
)

RAG_DURATION = Histogram(
    "agent_rag_retrieval_duration_seconds",
    "RAG retrieval duration",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        path = request.url.path
        method = request.method
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        REQUEST_DURATION.labels(method=method, path=path).observe(duration)

        return response


async def metrics_endpoint(request: Request):
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

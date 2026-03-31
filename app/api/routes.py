import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.graph.state import AgentState

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ConfirmRequest(BaseModel):
    request_id: str
    confirmed: bool


class IndexEvent(BaseModel):
    event: str
    board_id: str
    payload: dict


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    user_id = request.headers.get("X-User-ID", "")
    board_id = request.headers.get("X-Board-ID", "")
    board_key = request.headers.get("X-Board-Key", "")
    user_role = request.headers.get("X-User-Role", "guest")

    if not user_id or not board_id:
        raise HTTPException(status_code=400, detail="Missing user/board context")

    graph = request.app.state.graph
    session_id = body.session_id or str(uuid.uuid4())

    initial_state = AgentState(
        messages=[{"role": "user", "content": body.message}],
        board_id=board_id, board_key=board_key, user_id=user_id, user_role=user_role,
        intent="", rag_context=[], pending_action=None, confirmed=None,
        tool_results=[], response="", sources=[], error=None,
    )

    async def event_stream():
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, graph.invoke, initial_state)

            response_text = result.get("response", "")
            words = response_text.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else " " + word
                yield f"event: token\ndata: {json.dumps({'content': token})}\n\n"

            sources = result.get("sources", [])
            if sources:
                yield f"event: sources\ndata: {json.dumps({'sources': sources})}\n\n"

            pending = result.get("pending_action")
            if pending and result.get("confirmed") is None:
                request_id = str(uuid.uuid4())
                request.app.state.pending_actions[request_id] = pending
                yield f"event: action_required\ndata: {json.dumps({'action': pending['action'], 'params': pending['params'], 'explanation': pending.get('explanation', ''), 'request_id': request_id})}\n\n"

            yield f"event: done\ndata: {json.dumps({'session_id': session_id})}\n\n"
        except Exception as e:
            logger.error("Chat error: %s", e)
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/chat/confirm")
async def confirm_action(request: Request, body: ConfirmRequest):
    user_id = request.headers.get("X-User-ID", "")
    board_key = request.headers.get("X-Board-Key", "")
    user_role = request.headers.get("X-User-Role", "guest")

    if not body.confirmed:
        request.app.state.pending_actions.pop(body.request_id, None)
        return {"status": "cancelled"}

    go_client = request.app.state.go_client
    action_data = request.app.state.pending_actions.pop(body.request_id, None)
    if not action_data:
        raise HTTPException(status_code=404, detail="Action not found or expired")

    from app.tools.board_tools import execute_board_action
    result = execute_board_action(go_client, board_key, user_id, user_role, action_data["action"], action_data["params"])
    return {"status": "executed", "result": result}


@router.post("/index/event")
async def index_event(request: Request, body: IndexEvent):
    indexer = request.app.state.indexer
    logger.info("Index event: %s for board %s", body.event, body.board_id)

    if body.event in ("card_created", "card_updated"):
        indexer.index_card(
            board_id=body.board_id, card_number=body.payload.get("card_number", 0),
            title=body.payload.get("title", ""), description=body.payload.get("description", ""),
            column=body.payload.get("column", ""), assignee=body.payload.get("assignee"),
            priority=body.payload.get("priority"), tags=body.payload.get("tags", []),
        )
    elif body.event in ("doc_created", "doc_updated"):
        indexer.index_document(
            board_id=body.board_id, file_id=body.payload.get("file_id", ""),
            title=body.payload.get("title", ""), content=body.payload.get("content", ""),
            folder_path=body.payload.get("folder_path", ""),
        )
    elif body.event == "card_moved":
        indexer.index_movement(
            board_id=body.board_id, card_number=body.payload.get("card_number", 0),
            from_column=body.payload.get("from_column", ""), to_column=body.payload.get("to_column", ""),
            timestamp=body.payload.get("timestamp", ""),
        )

    return {"status": "ok"}


@router.post("/index/reindex/{board_id}")
async def reindex_board(board_id: str):
    logger.info("Full reindex requested for board %s", board_id)
    return {"status": "queued", "board_id": board_id}

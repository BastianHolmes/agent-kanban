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

    auth_token = request.headers.get("X-Auth-Token", "")

    if not user_id or not board_id:
        raise HTTPException(status_code=400, detail="Missing user/board context")

    # Auto-reindex if board has no or very few indexed points
    indexer = request.app.state.indexer
    retriever = request.app.state.retriever
    reindexed_boards = request.app.state.reindexed_boards
    collection_name = f"board_{board_id}"
    needs_reindex = False

    if board_id not in reindexed_boards:
        if not retriever.qdrant.collection_exists(collection_name):
            needs_reindex = True
        else:
            try:
                info = retriever.qdrant.get_collection(collection_name)
                if info.points_count < 5:
                    needs_reindex = True
            except Exception:
                needs_reindex = True

    if needs_reindex:
        logger.info("Auto-reindex for board %s (first chat or too few points)", board_id)
        go_client = request.app.state.go_client
        try:
            _do_reindex(indexer, go_client, board_id, board_key, user_id, auth_token)
            reindexed_boards.add(board_id)
        except Exception as e:
            logger.error("Auto-reindex failed for board %s: %s", board_id, e)

    graph = request.app.state.graph
    sessions = request.app.state.sessions
    session_id = body.session_id or str(uuid.uuid4())

    # Load or create session history
    if session_id not in sessions:
        sessions[session_id] = []
        sessions[f"{session_id}:meta"] = {"board_id": board_id, "user_id": user_id}
    history = sessions[session_id]
    history.append({"role": "user", "content": body.message})

    initial_state = AgentState(
        messages=list(history),
        board_id=board_id, board_key=board_key, user_id=user_id, user_role=user_role, auth_token=auth_token,
        intent="", rag_context=[], pending_action=None, confirmed=None,
        tool_results=[], response="", sources=[], error=None,
    )

    async def event_stream():
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, graph.invoke, initial_state)

            response_text = result.get("response", "")
            # Save assistant response to session history
            history.append({"role": "assistant", "content": response_text})
            words = response_text.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else " " + word
                yield f"event: token\ndata: {json.dumps({'content': token})}\n\n"
                await asyncio.sleep(0.03)

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
    auth_token = request.headers.get("X-Auth-Token", "")

    if not body.confirmed:
        request.app.state.pending_actions.pop(body.request_id, None)
        return {"status": "cancelled"}

    go_client = request.app.state.go_client
    action_data = request.app.state.pending_actions.pop(body.request_id, None)
    if not action_data:
        raise HTTPException(status_code=404, detail="Action not found or expired")

    from app.tools.board_tools import execute_board_action
    result = execute_board_action(go_client, board_key, user_id, user_role, action_data["action"], action_data["params"], auth_token)
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


def _do_reindex(indexer, go_client, board_id: str, board_key: str, user_id: str, auth_token: str = "") -> dict:
    """Reindex all cards and docs for a board. Used by both auto-reindex and manual endpoint."""
    indexed = {"cards": 0, "docs": 0}

    try:
        board_data = go_client.get_board_full(board_key, user_id, auth_token)
        board = board_data.get("board", board_data)
        columns = board.get("columns", [])
        for col in columns:
            col_title = col.get("title", "")
            for card in col.get("cards", []):
                indexer.index_card(
                    board_id=board_id,
                    card_number=card.get("number", 0),
                    title=card.get("title", ""),
                    description=card.get("description", ""),
                    column=col_title,
                    assignee=card.get("assignee", {}).get("name") if card.get("assignee") else None,
                    priority=card.get("priority"),
                    tags=[t.get("name", "") for t in card.get("tags", [])],
                )
                indexed["cards"] += 1
    except Exception as e:
        logger.error("Failed to index cards: %s", e)

    try:
        tree_data = go_client.get_doc_tree(board_key, user_id, auth_token)

        def extract_files(node, path=""):
            results = []
            if "files" in node:
                for f in node["files"]:
                    results.append((f.get("id", ""), f.get("name", ""), path))
            if "folders" in node:
                for folder in node["folders"]:
                    folder_path = f"{path}/{folder.get('name', '')}"
                    results.extend(extract_files(folder, folder_path))
            return results

        all_files = extract_files(tree_data)
        for file_id, file_name, folder_path in all_files:
            try:
                file_data = go_client.get_doc_file(board_key, file_id, user_id, auth_token)
                doc = file_data.get("file", file_data)
                indexer.index_document(
                    board_id=board_id,
                    file_id=file_id,
                    title=doc.get("name", file_name),
                    content=doc.get("content", ""),
                    folder_path=folder_path,
                )
                indexed["docs"] += 1
            except Exception as e:
                logger.error("Failed to index doc %s: %s", file_id, e)
    except Exception as e:
        logger.error("Failed to index docs: %s", e)

    logger.info("Reindex complete for board %s: %s", board_id, indexed)
    return indexed


@router.post("/index/reindex/{board_id}")
async def reindex_board(request: Request, board_id: str):
    indexer = request.app.state.indexer
    go_client = request.app.state.go_client
    board_key = request.headers.get("X-Board-Key", "")
    user_id = request.headers.get("X-User-ID", "")

    auth_token = request.headers.get("X-Auth-Token", "")

    logger.info("Full reindex requested for board %s (key=%s)", board_id, board_key)

    if not board_key or not user_id:
        raise HTTPException(status_code=400, detail="Missing X-Board-Key or X-User-ID headers")

    indexed = _do_reindex(indexer, go_client, board_id, board_key, user_id, auth_token)
    return {"status": "done", "board_id": board_id, "indexed": indexed}


@router.get("/sessions")
async def list_sessions(request: Request):
    """List all chat sessions for the current user+board."""
    user_id = request.headers.get("X-User-ID", "")
    board_id = request.headers.get("X-Board-ID", "")
    sessions = request.app.state.sessions

    result = []
    for sid, messages in sessions.items():
        # Filter by board context stored in session metadata
        meta = sessions.get(f"{sid}:meta", {})
        if meta.get("board_id") == board_id and meta.get("user_id") == user_id:
            first_msg = messages[0]["content"] if messages else ""
            result.append({
                "session_id": sid,
                "title": first_msg[:50],
                "message_count": len(messages),
            })

    return {"sessions": result}


@router.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: str):
    """Get full message history for a session."""
    sessions = request.app.state.sessions
    messages = sessions.get(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": messages}


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    """Delete a chat session."""
    sessions = request.app.state.sessions
    sessions.pop(session_id, None)
    sessions.pop(f"{session_id}:meta", None)
    return {"status": "deleted"}

from typing import TypedDict


class AgentState(TypedDict, total=False):
    messages: list[dict]
    board_id: str
    board_key: str
    user_id: str
    user_role: str
    auth_token: str
    intent: str
    rag_context: list[dict]
    pending_action: dict | None
    confirmed: bool | None
    tool_results: list[dict]
    response: str
    sources: list[dict]
    error: str | None

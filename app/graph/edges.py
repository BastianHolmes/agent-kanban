from app.graph.state import AgentState


def route_by_intent(state: AgentState) -> str:
    intent = state.get("intent", "rag")
    error = state.get("error")

    if error:
        return "response"

    if intent == "rejected":
        return "response"

    return intent


def route_after_action(state: AgentState) -> str:
    pending = state.get("pending_action")
    if pending and pending.get("action", "none") != "none":
        return "confirm"
    return "response"


def route_after_confirm(state: AgentState) -> str:
    return "response"

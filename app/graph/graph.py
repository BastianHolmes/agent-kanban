import logging
from functools import partial

from langgraph.graph import StateGraph, END

from app.graph.state import AgentState
from app.graph.nodes.validator import validate
from app.graph.nodes.router import route
from app.graph.nodes.rag import rag_node
from app.graph.nodes.board_mgmt import board_mgmt_node
from app.graph.nodes.code import code_node
from app.graph.nodes.confirm import confirm_node
from app.graph.nodes.response import response_node
from app.graph.edges import route_by_intent, route_after_action, route_after_confirm

logger = logging.getLogger(__name__)


def build_graph(retriever, go_client):
    graph = StateGraph(AgentState)

    graph.add_node("validator", validate)
    graph.add_node("router", route)
    graph.add_node("rag", partial(rag_node, retriever=retriever))
    graph.add_node("board_management", partial(board_mgmt_node, go_client=go_client))
    graph.add_node("code", partial(code_node, retriever=retriever, go_client=go_client))
    graph.add_node("confirm", confirm_node)
    graph.add_node("format_response", response_node)

    graph.set_entry_point("validator")
    graph.add_edge("validator", "router")

    graph.add_conditional_edges("router", route_by_intent, {"rag": "rag", "board_management": "board_management", "code": "code", "response": "format_response"})
    graph.add_conditional_edges("rag", route_after_action, {"confirm": "confirm", "response": "format_response"})
    graph.add_conditional_edges("board_management", route_after_action, {"confirm": "confirm", "response": "format_response"})
    graph.add_conditional_edges("code", route_after_action, {"confirm": "confirm", "response": "format_response"})
    graph.add_conditional_edges("confirm", route_after_confirm, {"response": "format_response"})

    graph.add_edge("format_response", END)

    return graph.compile()

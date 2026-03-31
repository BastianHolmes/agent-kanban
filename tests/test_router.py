import pytest
from unittest.mock import patch
from app.graph.state import AgentState
from app.graph.nodes.router import route


def _make_state(message: str) -> AgentState:
    return AgentState(
        messages=[{"role": "user", "content": message}],
        board_id="board-1",
        board_key="TEST",
        user_id="user-1",
        user_role="admin",
        intent="",
        rag_context=[],
        pending_action=None,
        confirmed=None,
        tool_results=[],
        response="",
        sources=[],
        error=None,
    )


class TestRouter:
    @patch("app.graph.nodes.router._classify_intent")
    def test_routes_to_rag(self, mock_classify):
        mock_classify.return_value = "rag"
        result = route(_make_state("Что написано в документации про API?"))
        assert result["intent"] == "rag"

    @patch("app.graph.nodes.router._classify_intent")
    def test_routes_to_board(self, mock_classify):
        mock_classify.return_value = "board_management"
        result = route(_make_state("Создай задачу"))
        assert result["intent"] == "board_management"

    @patch("app.graph.nodes.router._classify_intent")
    def test_routes_to_code(self, mock_classify):
        mock_classify.return_value = "code"
        result = route(_make_state("Найди баг в auth.go"))
        assert result["intent"] == "code"

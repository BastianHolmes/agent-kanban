import pytest
from unittest.mock import MagicMock, patch

from app.graph.graph import build_graph
from app.graph.state import AgentState


class TestGraphBuild:
    def test_graph_compiles(self):
        retriever = MagicMock()
        go_client = MagicMock()
        graph = build_graph(retriever, go_client)
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        retriever = MagicMock()
        go_client = MagicMock()
        graph = build_graph(retriever, go_client)
        node_names = set(graph.nodes.keys())
        expected = {"validator", "router", "rag", "board_management", "code", "confirm", "response"}
        assert expected.issubset(node_names)

    @patch("app.graph.nodes.router._classify_intent", return_value="rag")
    @patch("app.graph.nodes.rag.httpx")
    def test_rag_flow(self, mock_httpx, mock_classify):
        retriever = MagicMock()
        retriever.search.return_value = [
            {"source_type": "doc", "content": "Test doc", "title": "Guide", "file_id": "f1", "score": 0.9}
        ]
        go_client = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Ответ на основе документации."}}]}
        mock_httpx.post.return_value = mock_response

        graph = build_graph(retriever, go_client)
        initial_state = AgentState(
            messages=[{"role": "user", "content": "Что написано в документации?"}],
            board_id="board-1", board_key="TEST", user_id="user-1", user_role="admin",
            intent="", rag_context=[], pending_action=None, confirmed=None,
            tool_results=[], response="", sources=[], error=None,
        )
        result = graph.invoke(initial_state)
        assert result["intent"] == "rag"
        assert len(result["response"]) > 0

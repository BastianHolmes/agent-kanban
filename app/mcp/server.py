import json
import logging

from fastmcp import FastMCP

from app.config import settings

logger = logging.getLogger(__name__)

mcp = FastMCP("Easy Kanban Agent")


@mcp.tool()
def kanban_ask(board_key: str, question: str, api_key: str) -> str:
    """Ask a question about the kanban board's knowledge base, cards, or code."""
    import httpx

    resp = httpx.post(
        f"http://localhost:{settings.port}/chat",
        json={"message": question},
        headers={
            "X-User-ID": "mcp-user",
            "X-Board-ID": board_key,
            "X-Board-Key": board_key,
            "X-User-Role": "admin",
        },
        timeout=120,
    )
    resp.raise_for_status()

    answer_parts = []
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if "content" in data:
                    answer_parts.append(data["content"])
            except json.JSONDecodeError:
                pass
    return "".join(answer_parts)


@mcp.tool()
def kanban_board_state(board_key: str, api_key: str) -> str:
    """Get the current state of a kanban board (columns and cards)."""
    import httpx

    resp = httpx.get(
        f"{settings.go_api_url}/api/v1/boards/{board_key}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return json.dumps(resp.json(), ensure_ascii=False, indent=2)


@mcp.tool()
def kanban_create_card(board_key: str, column_id: str, title: str, description: str, api_key: str) -> str:
    """Create a new card on the kanban board."""
    import httpx

    resp = httpx.post(
        f"{settings.go_api_url}/api/v1/boards/{board_key}/columns/{column_id}/cards",
        json={"title": title, "description": description},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return json.dumps(resp.json(), ensure_ascii=False)


@mcp.tool()
def kanban_move_card(board_key: str, card_number: int, target_column_id: str, api_key: str) -> str:
    """Move a card to a different column."""
    import httpx

    resp = httpx.patch(
        f"{settings.go_api_url}/api/v1/boards/{board_key}/cards/{card_number}",
        json={"column_id": target_column_id},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return json.dumps(resp.json(), ensure_ascii=False)


@mcp.tool()
def kanban_search(board_key: str, query: str, api_key: str) -> str:
    """Search across board documents, cards, and code."""
    import httpx

    resp = httpx.post(
        f"http://localhost:{settings.port}/chat",
        json={"message": f"Найди информацию: {query}"},
        headers={
            "X-User-ID": "mcp-user",
            "X-Board-ID": board_key,
            "X-Board-Key": board_key,
            "X-User-Role": "admin",
        },
        timeout=120,
    )
    resp.raise_for_status()

    answer_parts = []
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if "content" in data:
                    answer_parts.append(data["content"])
            except json.JSONDecodeError:
                pass
    return "".join(answer_parts)


def run_mcp_server():
    """Run the MCP server (called as a separate process)."""
    mcp.run()


if __name__ == "__main__":
    run_mcp_server()

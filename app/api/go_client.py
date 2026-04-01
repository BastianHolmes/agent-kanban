import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GoClient:
    def __init__(self):
        self.base_url = settings.go_api_url
        self.client = httpx.Client(base_url=self.base_url, timeout=settings.tool_timeout)

    def _headers(self, user_id: str, auth_token: str = "") -> dict:
        h = {"X-User-ID": user_id}
        if auth_token:
            h["Authorization"] = auth_token
        return h

    def get_board_state(self, board_id: str, user_id: str) -> dict:
        resp = self.client.get(f"/api/v1/boards/{board_id}", headers=self._headers(user_id))
        resp.raise_for_status()
        return resp.json()

    def get_card(self, board_key: str, card_number: int, user_id: str) -> dict:
        resp = self.client.get(f"/api/v1/boards/{board_key}/cards/{card_number}", headers=self._headers(user_id))
        resp.raise_for_status()
        return resp.json()

    def create_card(self, board_key: str, column_id: str, title: str, description: str, user_id: str, auth_token: str = "") -> dict:
        resp = self.client.post(
            f"/api/v1/boards/{board_key}/columns/{column_id}/cards",
            json={"title": title, "description": description},
            headers=self._headers(user_id, auth_token),
        )
        resp.raise_for_status()
        return resp.json()

    def move_card(self, board_key: str, card_number: int, target_column_id: str, user_id: str, auth_token: str = "") -> dict:
        resp = self.client.patch(f"/api/v1/boards/{board_key}/cards/{card_number}", json={"column_id": target_column_id}, headers=self._headers(user_id, auth_token))
        resp.raise_for_status()
        return resp.json()

    def assign_card(self, board_key: str, card_number: int, assignee_id: str, user_id: str, auth_token: str = "") -> dict:
        resp = self.client.patch(f"/api/v1/boards/{board_key}/cards/{card_number}", json={"assignee_id": assignee_id}, headers=self._headers(user_id, auth_token))
        resp.raise_for_status()
        return resp.json()

    def update_card(self, board_key: str, card_number: int, updates: dict, user_id: str, auth_token: str = "") -> dict:
        resp = self.client.patch(f"/api/v1/boards/{board_key}/cards/{card_number}", json=updates, headers=self._headers(user_id, auth_token))
        resp.raise_for_status()
        return resp.json()

    def search_docs(self, board_key: str, query: str, user_id: str) -> dict:
        resp = self.client.get(f"/api/v1/boards/{board_key}/docs/search", params={"q": query, "limit": "10"}, headers=self._headers(user_id))
        resp.raise_for_status()
        return resp.json()

    def suggest_fix(self, board_key: str, card_number: int, user_id: str) -> dict:
        resp = self.client.post(f"/api/v1/boards/{board_key}/cards/{card_number}/suggest-fix", headers=self._headers(user_id))
        resp.raise_for_status()
        return resp.json()

    def apply_fix(self, board_key: str, card_number: int, user_id: str) -> dict:
        resp = self.client.post(f"/api/v1/boards/{board_key}/cards/{card_number}/apply-fix", headers=self._headers(user_id))
        resp.raise_for_status()
        return resp.json()

    def get_board_full(self, board_key: str, user_id: str, auth_token: str = "") -> dict:
        resp = self.client.get(f"/api/v1/boards/{board_key}", headers=self._headers(user_id, auth_token))
        resp.raise_for_status()
        return resp.json()

    def get_doc_tree(self, board_key: str, user_id: str, auth_token: str = "") -> dict:
        resp = self.client.get(f"/api/v1/boards/{board_key}/docs/tree", headers=self._headers(user_id, auth_token))
        resp.raise_for_status()
        return resp.json()

    def get_doc_file(self, board_key: str, file_id: str, user_id: str, auth_token: str = "") -> dict:
        resp = self.client.get(f"/api/v1/boards/{board_key}/docs/files/{file_id}", headers=self._headers(user_id, auth_token))
        resp.raise_for_status()
        return resp.json()

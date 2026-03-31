import pytest
from unittest.mock import MagicMock

from app.tools.board_tools import execute_board_action, check_permission


class TestPermissions:
    def test_guest_cannot_create(self):
        assert check_permission("guest", "create_card") is False

    def test_member_can_create(self):
        assert check_permission("member", "create_card") is True

    def test_admin_can_move(self):
        assert check_permission("admin", "move_card") is True

    def test_member_cannot_move(self):
        assert check_permission("member", "move_card") is False


class TestExecuteBoardAction:
    def test_create_card_success(self):
        go_client = MagicMock()
        go_client.create_card.return_value = {"card": {"id": "c1", "title": "New"}}
        result = execute_board_action(go_client, "TEST", "user-1", "admin", "create_card", {"column_id": "col-1", "title": "New", "description": "Desc"})
        assert result["success"] is True
        go_client.create_card.assert_called_once()

    def test_insufficient_permissions(self):
        go_client = MagicMock()
        result = execute_board_action(go_client, "TEST", "user-1", "guest", "create_card", {"column_id": "col-1", "title": "New"})
        assert result["success"] is False
        assert "permissions" in result["error"].lower()

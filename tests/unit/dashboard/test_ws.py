"""Tests for WebSocket log streaming."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from forge_agent.dashboard.app import create_app
from forge_agent.dashboard.routes.ws import LogBroadcaster, get_broadcaster, reset_broadcaster


@pytest.fixture(autouse=True)
def clean_broadcaster():
    """Reset broadcaster before each test."""
    reset_broadcaster()
    yield
    reset_broadcaster()


class TestLogBroadcaster:
    """Tests for the LogBroadcaster class."""

    def test_initial_state(self) -> None:
        b = LogBroadcaster()
        assert b.client_count == 0

    def test_get_broadcaster_singleton(self) -> None:
        b1 = get_broadcaster()
        b2 = get_broadcaster()
        assert b1 is b2

    def test_reset_broadcaster(self) -> None:
        b1 = get_broadcaster()
        reset_broadcaster()
        b2 = get_broadcaster()
        assert b1 is not b2


class TestWebSocketEndpoint:
    """Tests for the /ws/logs WebSocket endpoint."""

    def test_ws_connect_and_receive(self, tmp_path) -> None:
        app = create_app(project_root=tmp_path)
        client = TestClient(app)
        with client.websocket_connect("/ws/logs") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "Connected" in data["message"]
            # Send a message and receive ack
            ws.send_text("test_message")
            ack = ws.receive_json()
            assert ack["type"] == "ack"
            assert ack["data"] == "test_message"

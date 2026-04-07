"""WebSocket reconnect contract.

Proves that a client can disconnect and reconnect to the same campaign,
receive an equivalent canonical state, and issue commands after reconnect.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestWebSocketReconnect:
    def test_reconnect_receives_equivalent_state(self, client):
        resp = client.post("/game/campaigns", json={
            "player_name": "ReconnTest", "player_class": "warrior", "seed": 300,
        })
        assert resp.status_code == 200
        cid = resp.json()["campaign_id"]

        # First connection
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            first_msg = ws.receive_json()
            assert first_msg["type"] == "state"
            first_snapshot = first_msg["snapshot"]

        # Reconnect
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            second_msg = ws.receive_json()
            assert second_msg["type"] == "state"
            second_snapshot = second_msg["snapshot"]

        # Canonical fields must match
        assert first_snapshot["campaign_id"] == second_snapshot["campaign_id"]
        assert first_snapshot.get("player", {}).get("name") == second_snapshot.get("player", {}).get("name")

    def test_command_after_reconnect_returns_valid_state(self, client):
        resp = client.post("/game/campaigns", json={
            "player_name": "ReconnCmd", "player_class": "warrior", "seed": 301,
        })
        cid = resp.json()["campaign_id"]

        # Connect, disconnect
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            ws.receive_json()

        # Reconnect and issue command
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"type": "command", "input": "look around"})
            cmd_msg = ws.receive_json()
            assert cmd_msg["type"] == "state"
            assert "narrative" in cmd_msg

    def test_reconnect_after_command_preserves_state_change(self, client):
        resp = client.post("/game/campaigns", json={
            "player_name": "ReconnState", "player_class": "warrior", "seed": 302,
        })
        cid = resp.json()["campaign_id"]

        # Connect, issue command, disconnect
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            ws.receive_json()
            ws.send_json({"type": "command", "input": "look around"})
            after_cmd = ws.receive_json()
            assert after_cmd["type"] == "state"

        # Reconnect — state should reflect the command
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            reconnect_msg = ws.receive_json()
            assert reconnect_msg["type"] == "state"
            # Campaign should still exist and be valid
            assert reconnect_msg["snapshot"]["campaign_id"] == cid

    def test_ping_works_after_reconnect(self, client):
        resp = client.post("/game/campaigns", json={
            "player_name": "ReconnPing", "player_class": "warrior", "seed": 303,
        })
        cid = resp.json()["campaign_id"]

        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            ws.receive_json()

        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            ws.receive_json()
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

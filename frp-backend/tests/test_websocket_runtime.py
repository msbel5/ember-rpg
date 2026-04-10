"""Tests for WebSocket transport wiring and tick push."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """TestClient with lifespan triggered (sets up runtime)."""
    with TestClient(app) as c:
        yield c


class TestWebSocketConnection:
    def test_ws_rejects_unknown_campaign(self, client):
        with client.websocket_connect("/game/ws/campaigns/nonexistent") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["message"].lower()

    def test_ws_connects_and_receives_snapshot(self, client):
        resp = client.post("/game/campaigns", json={
            "player_name": "WSTest", "player_class": "warrior", "seed": 42,
        })
        assert resp.status_code == 200
        cid = resp.json()["campaign_id"]
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "state"
            assert "snapshot" in msg
            snapshot = msg["snapshot"]
            assert snapshot["transport"]["mode"] == "ws"
            assert snapshot["transport"]["bootstrap"] == "http"
            assert snapshot["transport"]["ws_path"] == f"/game/ws/campaigns/{cid}"
            assert snapshot["runtime_mode"] in {"exploration_realtime", "travel", "dialog"}

    def test_ws_ping_pong(self, client):
        resp = client.post("/game/campaigns", json={
            "player_name": "PingTest", "player_class": "warrior", "seed": 43,
        })
        cid = resp.json()["campaign_id"]
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            ws.receive_json()  # initial snapshot
            ws.send_json({"type": "ping"})
            msg = ws.receive_json()
            assert msg["type"] == "pong"

    def test_ws_command_returns_state(self, client):
        resp = client.post("/game/campaigns", json={
            "player_name": "CmdTest", "player_class": "warrior", "seed": 44,
        })
        cid = resp.json()["campaign_id"]
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            ws.receive_json()  # initial snapshot
            ws.send_json({"type": "command", "input": "look around"})
            msg = ws.receive_json()
            assert msg["type"] == "state"
            assert "narrative" in msg
            assert "events" in msg

    def test_ws_empty_command_rejected(self, client):
        resp = client.post("/game/campaigns", json={
            "player_name": "EmptyCmd", "player_class": "warrior", "seed": 45,
        })
        cid = resp.json()["campaign_id"]
        with client.websocket_connect(f"/game/ws/campaigns/{cid}") as ws:
            ws.receive_json()  # initial snapshot
            ws.send_json({"type": "command", "input": ""})
            msg = ws.receive_json()
            assert msg["type"] == "error"


class TestConnectionRegistry:
    def test_runtime_is_wired(self, client):
        from engine.api import ws_campaign
        assert ws_campaign._runtime_ref is not None

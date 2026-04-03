"""Phase 3: WebSocket transport tests.

Tests the WebSocket campaign handler for real-time communication.
Uses FastAPI's TestClient WebSocket support.
"""

import json

import pytest
from fastapi.testclient import TestClient

from main import app
from engine.api.ws_campaign import set_runtime


# ── Mock runtime for testing ─────────────────────────────────────────

class _MockRuntime:
    """Minimal CampaignRuntime mock for WebSocket tests."""

    def __init__(self):
        self.campaigns = {"test_campaign": True}
        self.last_command = None

    def get_campaign(self, campaign_id: str):
        if campaign_id not in self.campaigns:
            raise KeyError(f"Campaign {campaign_id} not found")
        return {"campaign_id": campaign_id}

    def snapshot(self, campaign_id: str, narrative: str = "") -> dict:
        return {
            "campaign_id": campaign_id,
            "narrative": narrative,
            "player": {"name": "TestPlayer", "hp": 20},
        }

    def run_command(self, campaign_id: str, input_text: str, shortcut=None, args=None) -> dict:
        self.last_command = input_text
        return {
            "narrative": f"You said: {input_text}",
            "events": [{"type": "test_event"}],
        }


@pytest.fixture(autouse=True)
def _register_mock_runtime():
    """Register mock runtime before each test."""
    mock = _MockRuntime()
    set_runtime(mock)
    yield
    set_runtime(None)


# ── Connection tests ─────────────────────────────────────────────────

def test_connect_to_valid_campaign():
    """WebSocket connects and receives initial state snapshot."""
    client = TestClient(app)
    with client.websocket_connect("/game/ws/campaigns/test_campaign") as ws:
        data = ws.receive_json()
        assert data["type"] == "state"
        assert "snapshot" in data
        assert data["snapshot"]["campaign_id"] == "test_campaign"


def test_connect_to_invalid_campaign():
    """WebSocket rejects connection to non-existent campaign."""
    client = TestClient(app)
    with client.websocket_connect("/game/ws/campaigns/nonexistent") as ws:
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "not found" in data["message"].lower()


# ── Command tests ────────────────────────────────────────────────────

def test_send_command_receive_state():
    """Sending a command returns updated state snapshot."""
    client = TestClient(app)
    with client.websocket_connect("/game/ws/campaigns/test_campaign") as ws:
        # Consume initial snapshot.
        ws.receive_json()
        # Send command.
        ws.send_json({"type": "command", "input": "look around"})
        data = ws.receive_json()
        assert data["type"] == "state"
        assert "look around" in data["narrative"]
        assert len(data["events"]) > 0


def test_empty_command_returns_error():
    """Empty command input should return an error."""
    client = TestClient(app)
    with client.websocket_connect("/game/ws/campaigns/test_campaign") as ws:
        ws.receive_json()
        ws.send_json({"type": "command", "input": ""})
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "empty" in data["message"].lower()


# ── Ping/pong ────────────────────────────────────────────────────────

def test_ping_pong():
    """Ping message should receive pong response."""
    client = TestClient(app)
    with client.websocket_connect("/game/ws/campaigns/test_campaign") as ws:
        ws.receive_json()
        ws.send_json({"type": "ping"})
        data = ws.receive_json()
        assert data["type"] == "pong"


# ── Error handling ───────────────────────────────────────────────────

def test_invalid_json_returns_error():
    """Non-JSON message should return error, not crash."""
    client = TestClient(app)
    with client.websocket_connect("/game/ws/campaigns/test_campaign") as ws:
        ws.receive_json()
        ws.send_text("not valid json{{{")
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "json" in data["message"].lower()


def test_unknown_message_type():
    """Unknown message type should return error."""
    client = TestClient(app)
    with client.websocket_connect("/game/ws/campaigns/test_campaign") as ws:
        ws.receive_json()
        ws.send_json({"type": "unknown_action"})
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "unknown" in data["message"].lower()


# ── HTTP still works alongside WebSocket ─────────────────────────────

def test_http_routes_still_work():
    """HTTP campaign routes should work alongside WebSocket."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "Ember RPG"

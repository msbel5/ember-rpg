from __future__ import annotations

import pytest

from engine.api import ws_campaign
from engine.api.campaign.runtime_transport import emit_visual_delta


class _FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.messages.append(dict(payload))


@pytest.mark.asyncio
async def test_visual_delta_routes_through_existing_websocket_connections(monkeypatch) -> None:
    fake_socket = _FakeWebSocket()
    monkeypatch.setattr(ws_campaign, "get_connections", lambda _campaign_id: [fake_socket])
    payload = {
        "tick_index": 7,
        "actors": [{"id": "npc_1", "position": [4, 5], "facing": "east", "state": "walk"}],
    }
    await emit_visual_delta("campaign-1", payload)
    assert fake_socket.messages == [
        {
            "type": "visual_delta",
            "tick_index": 7,
            "actors": [{"id": "npc_1", "position": [4, 5], "facing": "east", "state": "walk"}],
        }
    ]

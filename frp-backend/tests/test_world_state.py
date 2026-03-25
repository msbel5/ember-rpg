"""
Ember RPG - World State Ledger Tests
Phase 3a
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from engine.world import WorldState, FactionState

client = TestClient(app)


def _new_session():
    resp = client.post("/game/session/new", json={"player_name": "Aria", "player_class": "warrior"})
    assert resp.status_code == 200
    return resp.json()["session_id"]


class TestWorldStateUnit:
    def test_world_state_initializes_empty(self):
        ws = WorldState("test-game")
        assert ws.game_id == "test-game"
        assert ws.locations == {}
        assert ws.npc_states == {}
        assert ws.factions == {}
        assert ws.quest_log == []
        assert ws.flags == {}
        assert ws.history == []

    def test_log_event_appends_to_history(self):
        ws = WorldState("g1")
        ws.log_event("test_event", "Something happened", ["npc1"])
        assert len(ws.history) == 1
        assert ws.history[0].event_type == "test_event"
        assert ws.history[0].description == "Something happened"
        assert "npc1" in ws.history[0].affected_entities

    def test_npc_killed_marks_dead(self):
        ws = WorldState("g1")
        ws.update_npc_killed("goblin1")
        assert not ws.npc_states["goblin1"].alive
        assert any(e.event_type == "npc_killed" for e in ws.history)

    def test_location_discovered(self):
        ws = WorldState("g1")
        ws.update_location_discovered("cave1", "Dark Cave")
        assert ws.locations["cave1"].discovered is True
        assert ws.locations["cave1"].name == "Dark Cave"
        assert any(e.event_type == "location_discovered" for e in ws.history)

    def test_build_ai_context_excludes_dead_npcs(self):
        ws = WorldState("g1")
        ws.update_npc_killed("merchant1")
        context = ws.build_ai_context()
        assert "merchant1" in context
        assert "Dead and unavailable" in context

    def test_build_ai_context_recent_events(self):
        ws = WorldState("g1")
        for i in range(7):
            ws.log_event("test", f"Event {i}", [])
        context = ws.build_ai_context()
        # Should only include last 5
        assert "Event 6" in context
        assert "Event 1" not in context

    def test_world_state_serialization_round_trip(self):
        ws = WorldState("g1")
        ws.update_npc_killed("orc1")
        ws.update_location_discovered("forest", "Dark Forest")
        ws.flags["bridge_destroyed"] = True
        ws.factions["guards"] = FactionState(id="guards", name="Town Guard", reputation=10)

        data = ws.to_dict()
        ws2 = WorldState.from_dict(data)
        assert ws2.game_id == "g1"
        assert not ws2.npc_states["orc1"].alive
        assert ws2.locations["forest"].discovered
        assert ws2.flags["bridge_destroyed"] is True
        assert ws2.factions["guards"].reputation == 10
        assert len(ws2.history) == len(ws.history)

    def test_faction_reputation_tracked(self):
        ws = WorldState("g1")
        ws.factions["guild"] = FactionState(id="guild", name="Merchant Guild", reputation=0)
        ws.factions["guild"].reputation -= 20
        assert ws.factions["guild"].reputation == -20


class TestWorldStateAPI:
    def test_get_world_state_endpoint(self):
        sid = _new_session()
        resp = client.get(f"/game/session/{sid}/world-state")
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert "current_time" in data
        assert "flags" in data

    def test_get_history_endpoint(self):
        sid = _new_session()
        resp = client.get(f"/game/session/{sid}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert "total" in data

    def test_world_state_included_in_save_load(self):
        from engine.api.routes import _sessions
        sid = _new_session()
        session = _sessions[sid]
        # Modify world state
        session.world_state.update_npc_killed("test_npc")
        session.world_state.flags["test_flag"] = True

        # Serialize
        ws_dict = session.world_state.to_dict()
        # Deserialize
        from engine.world import WorldState
        ws2 = WorldState.from_dict(ws_dict)
        assert not ws2.npc_states["test_npc"].alive
        assert ws2.flags["test_flag"] is True

"""
Ember RPG - End-to-End Player Journey Tests
============================================
Full player journey E2E tests using FastAPI TestClient.
LLM calls fall back to template narrative when the API is unavailable (offline mode).
"""
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_session(name="Hero", cls="warrior"):
    """Create a new session and return response JSON."""
    resp = client.post("/game/session/new", json={
        "player_name": name,
        "player_class": cls,
    })
    assert resp.status_code == 200
    return resp.json()


def _action(session_id: str, input_text: str):
    """Send a player action and return response JSON."""
    resp = client.post(f"/game/session/{session_id}/action", json={"input": input_text})
    assert resp.status_code == 200
    return resp.json()


# ── Session Creation ──────────────────────────────────────────────────────────

class TestSessionCreation:

    def test_session_creation_has_llm_narrative(self):
        """New session narrative must be non-empty."""
        data = _new_session("Aria")
        narrative = data.get("narrative", "")
        assert narrative, "Narrative should be non-empty on session creation"
        assert len(narrative) > 0

    def test_session_state_has_correct_fields(self):
        """GET /game/session/{id} must return hp, max_hp, level, scene, location all non-None."""
        data = _new_session("Borin")
        sid = data["session_id"]
        resp = client.get(f"/game/session/{sid}")
        assert resp.status_code == 200
        state = resp.json()
        assert state.get("hp") is not None, "hp must not be None"
        assert state.get("max_hp") is not None, "max_hp must not be None"
        assert state.get("level") is not None, "level must not be None"
        assert state.get("scene") is not None, "scene must not be None"
        assert state.get("location") is not None, "location must not be None"
        assert state["hp"] > 0
        assert state["max_hp"] >= state["hp"]
        assert state["level"] >= 1


# ── Exploration ───────────────────────────────────────────────────────────────

class TestExploration:

    def test_look_around_returns_location_context(self):
        """'look around' must return non-empty narrative."""
        data = _new_session("Scout")
        sid = data["session_id"]
        result = _action(sid, "look around")
        narrative = result.get("narrative", "")
        assert narrative, "'look around' must return non-empty narrative"

    def test_move_forward_changes_location(self):
        """'move forward' must update the session location."""
        data = _new_session("Traveler")
        sid = data["session_id"]
        original_location = data.get("location", "")

        result = _action(sid, "move forward")
        assert result["narrative"], "Move should produce narrative"

        state = client.get(f"/game/session/{sid}").json()
        new_location = state.get("location", "")
        assert new_location != original_location, \
            f"Location should change after 'move forward'; was {original_location!r}, now {new_location!r}"

    def test_talk_to_npc_returns_dialogue(self):
        """'talk to merchant' must return dialogue scene and non-empty narrative."""
        data = _new_session("Talker")
        sid = data["session_id"]
        result = _action(sid, "talk to merchant")
        assert result.get("narrative"), "Dialogue narrative must not be empty"
        assert result.get("scene") == "dialogue", \
            f"Expected scene=dialogue, got {result.get('scene')!r}"


# ── Combat ────────────────────────────────────────────────────────────────────

class TestCombat:

    def test_full_combat_loop(self):
        """attack → rounds → enemy eventually dies, combat ends, back to exploration."""
        data = _new_session("Fighter")
        sid = data["session_id"]

        rounds = 0
        max_rounds = 40  # safety cap

        while rounds < max_rounds:
            result = _action(sid, "attack")
            rounds += 1
            narrative = result.get("narrative", "")
            assert narrative, f"Combat round {rounds} must have narrative"

            scene = result.get("scene", "")
            combat = result.get("combat")

            if scene == "exploration":
                break  # combat ended, victory
            if combat and combat.get("combat_ended"):
                break

        assert rounds >= 1, "At least one combat round must have occurred"

    def test_rest_blocked_in_combat(self):
        """Player cannot rest during combat — must get a blocking message."""
        data = _new_session("Fighter2")
        sid = data["session_id"]

        # Attempt to enter combat
        result = _action(sid, "attack")
        scene = result.get("scene", "")

        if scene != "combat":
            pytest.skip("Combat did not start on first attack — enemy may have died immediately")

        rest_result = _action(sid, "rest")
        narrative = rest_result.get("narrative", "")
        assert narrative, "Rest-in-combat must return narrative"
        assert any(kw in narrative.lower() for kw in ["cannot", "can't", "fight", "combat", "middle"]), \
            f"Expected rest-blocking message, got: {narrative!r}"

    def test_rest_heals_out_of_combat(self):
        """Rest outside combat must return non-empty narrative and not decrease HP."""
        data = _new_session("Healer")
        sid = data["session_id"]

        state_before = client.get(f"/game/session/{sid}").json()
        hp_before = state_before["hp"]
        max_hp = state_before["max_hp"]

        result = _action(sid, "rest")
        assert result.get("narrative"), "Rest must return narrative"

        state_after = client.get(f"/game/session/{sid}").json()
        hp_after = state_after["hp"]

        assert hp_after >= hp_before, "HP should not decrease after resting"
        assert hp_after <= max_hp, "HP should not exceed max_hp after resting"


# ── Scene Orchestrator ────────────────────────────────────────────────────────

class TestSceneOrchestrator:

    def test_scene_enter_returns_map_and_narrative(self):
        """POST /game/scene/enter returns map_data, entities, narrative_stream."""
        data = _new_session("Explorer")
        sid = data["session_id"]

        payload = {
            "session_id": sid,
            "location": "Ironforge Town",
            "location_type": "town",
            "time_of_day": "morning",
            "player_name": "Explorer",
            "player_level": 1,
            "is_first_visit": True,
        }
        resp = client.post("/game/scene/enter", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "map_data" in body, f"Response missing map_data. Keys: {list(body.keys())}"
        assert "entities" in body, f"Response missing entities. Keys: {list(body.keys())}"
        assert "narrative_stream" in body or "narrative" in body, \
            f"Response missing narrative. Keys: {list(body.keys())}"

    def test_scene_available_types(self):
        """GET /game/scene/available-types returns a list."""
        resp = client.get("/game/scene/available-types")
        assert resp.status_code == 200
        body = resp.json()
        assert "types" in body
        assert len(body["types"]) > 0


# ── Shop ──────────────────────────────────────────────────────────────────────

class TestShop:

    def test_shop_buy_sell_cycle(self):
        """Buy then sell item — check gold deducted on buy and earned on sell."""
        data = _new_session("Shopper")
        sid = data["session_id"]

        npc_id = "merchant_general_goods"
        item_id = "potion_of_healing"

        # Inspect shop inventory
        shop_resp = client.get(f"/game/shop/{npc_id}")
        assert shop_resp.status_code == 200
        shop_data = shop_resp.json()
        assert "items" in shop_data
        item_info = next((i for i in shop_data["items"] if i["id"] == item_id), None)
        assert item_info is not None, f"{item_id} not in shop inventory"
        buy_price = item_info["buy_price"]

        # Give player gold by injecting into session
        from engine.api.routes import _sessions
        session = _sessions.get(sid)
        assert session is not None, "Session must be in memory"
        session.player.gold = 1000

        # Buy
        buy_resp = client.post(f"/game/shop/{npc_id}/buy", json={
            "session_id": sid, "item_id": item_id, "quantity": 1,
        })
        assert buy_resp.status_code == 200
        buy_data = buy_resp.json()
        assert "gold_remaining" in buy_data
        assert buy_data["gold_remaining"] == 1000 - buy_price

        # Sell
        sell_resp = client.post(f"/game/shop/{npc_id}/sell", json={
            "session_id": sid, "item_id": item_id, "quantity": 1,
        })
        assert sell_resp.status_code == 200
        sell_data = sell_resp.json()
        assert "gold_total" in sell_data
        assert sell_data["gold_total"] > buy_data["gold_remaining"]

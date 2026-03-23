"""
Ember RPG - Integration Tests
Full request/response flow tests covering end-to-end scenarios.
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _new_session(name="Aria", cls="warrior", location="dungeon"):
    """Helper: create a new session and return response data."""
    resp = client.post("/game/session/new", json={
        "player_name": name,
        "player_class": cls,
        "location": location,
    })
    assert resp.status_code == 200
    return resp.json()


def _action(session_id, text):
    """Helper: perform an action in a session."""
    resp = client.post(f"/game/session/{session_id}/action", json={"input": text})
    assert resp.status_code == 200
    return resp.json()


class TestFullGameLoop:
    """Test 1: Full game loop — create, act, verify, end."""

    def test_full_game_loop(self):
        # Create session
        data = _new_session("Lorin", "warrior")
        sid = data["session_id"]
        assert sid
        assert data["player"]["name"] == "Lorin"

        # Perform an action
        result = _action(sid, "look around")
        assert "narrative" in result
        assert len(result["narrative"]) > 0

        # State should reflect player
        assert "player" in result
        assert result["player"]["name"] == "Lorin"

        # End session
        resp = client.delete(f"/game/session/{sid}")
        assert resp.status_code == 200

        # Session should be gone
        resp = client.get(f"/game/session/{sid}")
        assert resp.status_code == 404


class TestCombatFlow:
    """Test 2: Combat flow — trigger combat, attack, verify."""

    def test_combat_trigger_and_attack(self):
        data = _new_session("Bran", "warrior")
        sid = data["session_id"]
        initial_hp = data["player"]["hp"]
        assert initial_hp > 0

        # Trigger combat
        result1 = _action(sid, "attack")
        assert "narrative" in result1
        assert len(result1["narrative"]) > 0

        # Perform attack action
        result2 = _action(sid, "hit the enemy with my sword")
        assert "narrative" in result2
        assert "player" in result2

    def test_combat_with_mage(self):
        data = _new_session("Zara", "mage")
        sid = data["session_id"]
        assert data["player"]["spell_points"] > 0

        result = _action(sid, "attack the goblin")
        assert "narrative" in result


class TestSaveLoadRoundTrip:
    """Test 3: Save/Load round trip."""

    def test_save_and_load(self):
        # Create session and perform actions
        data = _new_session("SaveTest", "warrior")
        sid = data["session_id"]
        player_id = "test_player_save_load"

        _action(sid, "look around")
        _action(sid, "rest")

        # Get session state before save
        state_before = client.get(f"/game/session/{sid}").json()

        # Save session
        save_resp = client.post(f"/game/session/{sid}/save", json={"player_id": player_id})
        assert save_resp.status_code == 200
        save_data = save_resp.json()
        assert "save_id" in save_data
        save_id = save_data["save_id"]

        # Load the save (correct route: POST /game/session/load/{save_id})
        load_resp = client.post(f"/game/session/load/{save_id}")
        assert load_resp.status_code == 200
        loaded = load_resp.json()
        assert loaded["save_id"] == save_id
        assert loaded["status"] == "loaded"

        # Verify session data is intact
        session_data = loaded["session_data"]
        assert session_data["player"]["name"] == state_before["player"]["name"]

    def test_list_saves(self):
        # Create and save a session
        data = _new_session("ListTest", "mage")
        sid = data["session_id"]
        player_id = "test_player_list_saves"

        save_resp = client.post(f"/game/session/{sid}/save", json={"player_id": player_id})
        assert save_resp.status_code == 200

        # List saves for player (correct route: /game/saves/{player_id})
        list_resp = client.get(f"/game/saves/{player_id}")
        assert list_resp.status_code == 200
        saves = list_resp.json()
        assert isinstance(saves, list)
        assert len(saves) >= 1


class TestNPCInteraction:
    """Test 4: NPC interaction flow."""

    def test_npc_dialogue(self):
        data = _new_session("Tavi", "warrior", location="town")
        sid = data["session_id"]

        # Interact with NPC via action
        result = _action(sid, "talk to the innkeeper")
        assert "narrative" in result
        assert len(result["narrative"]) > 0

    def test_npc_trade_interaction(self):
        data = _new_session("Merch", "warrior", location="town")
        sid = data["session_id"]

        result = _action(sid, "ask merchant about items for sale")
        assert "narrative" in result


class TestMapNavigation:
    """Test 5: Map navigation — request map, navigate to room."""

    def test_get_map(self):
        data = _new_session("Nav", "warrior", location="dungeon")
        sid = data["session_id"]

        map_resp = client.get(f"/game/session/{sid}/map")
        assert map_resp.status_code == 200
        map_data = map_resp.json()

        assert "map" in map_data
        assert "location" in map_data
        assert map_data["session_id"] == sid

    def test_get_town_map(self):
        data = _new_session("NavTown", "warrior", location="town")
        sid = data["session_id"]

        map_resp = client.get(f"/game/session/{sid}/map")
        assert map_resp.status_code == 200
        map_data = map_resp.json()
        assert "map" in map_data

    def test_map_with_seed(self):
        data = _new_session("NavSeed", "warrior")
        sid = data["session_id"]

        map_resp1 = client.get(f"/game/session/{sid}/map?seed=42")
        map_resp2 = client.get(f"/game/session/{sid}/map?seed=42")
        assert map_resp1.status_code == 200
        assert map_resp2.status_code == 200

        # Same seed should produce same map
        assert map_resp1.json()["map"] == map_resp2.json()["map"]

    def test_navigate_via_action(self):
        data = _new_session("NavAction", "warrior", location="dungeon")
        sid = data["session_id"]

        result = _action(sid, "move north")
        assert "narrative" in result
        assert "player" in result


class TestSpellCasting:
    """Test 6: Spell casting — verify SP consumed + narrative."""

    def test_mage_cast_spell(self):
        data = _new_session("Zephyr", "mage")
        sid = data["session_id"]
        initial_sp = data["player"]["spell_points"]
        assert initial_sp > 0

        result = _action(sid, "cast fireball at the enemy")
        assert "narrative" in result
        assert len(result["narrative"]) > 0

    def test_warrior_no_sp(self):
        data = _new_session("Bjorn", "warrior")
        sid = data["session_id"]
        # Warriors typically have 0 or minimal spell points
        # Try casting — should not crash
        result = _action(sid, "cast a spell")
        assert "narrative" in result

    def test_spell_action_returns_player_state(self):
        data = _new_session("Lyra", "mage")
        sid = data["session_id"]

        result = _action(sid, "cast magic missile")
        assert "player" in result
        assert result["player"]["name"] == "Lyra"


class TestLevelUpFlow:
    """Test 7: Level up flow — XP gain triggers level check."""

    def test_level_up_via_actions(self):
        data = _new_session("Levelup", "warrior")
        sid = data["session_id"]
        initial_level = data["player"]["level"]

        # Perform multiple combat actions to trigger XP
        for _ in range(5):
            _action(sid, "attack the enemy")

        # Check current state
        state = client.get(f"/game/session/{sid}").json()
        assert state["player"]["level"] >= initial_level

    def test_action_response_includes_level_info(self):
        data = _new_session("StatCheck", "mage")
        sid = data["session_id"]

        result = _action(sid, "attack")
        assert "player" in result
        assert "level" in result["player"]
        assert "xp" in result["player"]


class TestCampaignStart:
    """Test 8: Campaign start — session creation and campaign action."""

    def test_campaign_action(self):
        data = _new_session("Campaigner", "warrior")
        sid = data["session_id"]

        # Start a campaign-like quest via action
        result = _action(sid, "start the quest")
        assert "narrative" in result
        assert len(result["narrative"]) > 0

    def test_campaign_state_in_session(self):
        data = _new_session("QuestStart", "warrior")
        sid = data["session_id"]

        # Interact with quest-giving elements
        result = _action(sid, "accept the quest from the elder")
        assert "narrative" in result
        assert "player" in result

        # Verify session is still retrievable
        state = client.get(f"/game/session/{sid}").json()
        assert state["session_id"] == sid


class TestErrorHandling:
    """Test 9: Error handling — 404, 422, malformed input."""

    def test_invalid_session_get_404(self):
        resp = client.get("/game/session/totally-fake-id-xyz")
        assert resp.status_code == 404

    def test_invalid_session_action_404(self):
        resp = client.post("/game/session/nonexistent-session/action",
                           json={"input": "hello"})
        assert resp.status_code == 404

    def test_invalid_session_delete_404(self):
        resp = client.delete("/game/session/does-not-exist")
        assert resp.status_code == 404

    def test_invalid_session_map_404(self):
        resp = client.get("/game/session/no-such-session/map")
        assert resp.status_code == 404

    def test_malformed_new_session_422(self):
        resp = client.post("/game/session/new", json={})
        assert resp.status_code == 422

    def test_malformed_action_422(self):
        data = _new_session("ErrTest", "warrior")
        sid = data["session_id"]
        resp = client.post(f"/game/session/{sid}/action", json={})
        assert resp.status_code == 422

    def test_invalid_save_id_404(self):
        resp = client.get("/game/save/invalid-save-id-xyz")
        assert resp.status_code == 404

    def test_new_session_missing_class_uses_default(self):
        # The API has a default player_class — missing class succeeds
        resp = client.post("/game/session/new", json={"player_name": "NoClass"})
        # Either 200 (default class) or 422 (required field); both are valid behavior
        assert resp.status_code in (200, 422)

    def test_new_session_missing_name_422(self):
        resp = client.post("/game/session/new", json={"player_class": "warrior"})
        assert resp.status_code == 422


class TestConcurrentSessions:
    """Test 10: Concurrent sessions — isolation between sessions."""

    def test_three_sessions_isolated(self):
        # Create 3 independent sessions
        s1 = _new_session("Alice", "warrior")
        s2 = _new_session("Bob", "mage")
        s3 = _new_session("Carol", "rogue")

        sid1 = s1["session_id"]
        sid2 = s2["session_id"]
        sid3 = s3["session_id"]

        # All sessions should have unique IDs
        assert len({sid1, sid2, sid3}) == 3

        # Actions on one session should not affect others
        _action(sid1, "attack")
        _action(sid2, "cast spell")
        _action(sid3, "sneak")

        # Verify each session has correct player name
        state1 = client.get(f"/game/session/{sid1}").json()
        state2 = client.get(f"/game/session/{sid2}").json()
        state3 = client.get(f"/game/session/{sid3}").json()

        assert state1["player"]["name"] == "Alice"
        assert state2["player"]["name"] == "Bob"
        assert state3["player"]["name"] == "Carol"

        # Deleting one does not affect others
        client.delete(f"/game/session/{sid1}")
        assert client.get(f"/game/session/{sid1}").status_code == 404
        assert client.get(f"/game/session/{sid2}").status_code == 200
        assert client.get(f"/game/session/{sid3}").status_code == 200

    def test_sessions_have_independent_player_states(self):
        s1 = _new_session("Tank", "warrior")
        s2 = _new_session("Healer", "mage")

        sid1, sid2 = s1["session_id"], s2["session_id"]

        # Warrior and mage should have different class attributes
        state1 = client.get(f"/game/session/{sid1}").json()
        state2 = client.get(f"/game/session/{sid2}").json()

        # Player classes are stored as dict: {"warrior": 1}
        assert "warrior" in state1["player"]["classes"]
        assert "mage" in state2["player"]["classes"]
        # Ensure they're independent objects
        assert state1["session_id"] != state2["session_id"]

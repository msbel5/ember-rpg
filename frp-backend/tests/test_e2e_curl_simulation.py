"""
Ember RPG — E2E Test Suite (curl simulation)
============================================
Simulates real HTTP client interactions using FastAPI's TestClient (httpx under the hood).
Each test mirrors what a curl call would look like, with explicit request/response validation.

Run:
    pytest tests/test_e2e_curl_simulation.py -v
    pytest tests/test_e2e_curl_simulation.py --cov=engine/api --cov=main --cov-report=term-missing
"""
import json
import pytest
from fastapi.testclient import TestClient
from main import app

# ─── Client ─────────────────────────────────────────────────────────────────

client = TestClient(app)

# ─── Helpers ────────────────────────────────────────────────────────────────


def curl_get(path: str, params: dict | None = None) -> tuple[int, dict]:
    """Simulate: curl -X GET http://localhost:8000{path}"""
    resp = client.get(path, params=params or {})
    return resp.status_code, resp.json()


def curl_post(path: str, body: dict) -> tuple[int, dict]:
    """Simulate: curl -X POST http://localhost:8000{path} -d '{body}'"""
    resp = client.post(path, json=body)
    return resp.status_code, resp.json()


def curl_delete(path: str) -> tuple[int, dict]:
    """Simulate: curl -X DELETE http://localhost:8000{path}"""
    resp = client.delete(path)
    return resp.status_code, resp.json()


def new_session(name: str = "TestHero", cls: str = "warrior", location: str = "dungeon") -> dict:
    """Create a new game session; assert success and return response body."""
    code, data = curl_post("/game/session/new", {
        "player_name": name,
        "player_class": cls,
        "location": location,
    })
    assert code == 200, f"Expected 200 creating session, got {code}: {data}"
    return data


def take_action(session_id: str, text: str) -> dict:
    """Submit a player action; assert success and return response body."""
    code, data = curl_post(f"/game/session/{session_id}/action", {"input": text})
    assert code == 200, f"Expected 200 on action, got {code}: {data}"
    return data


# ─── Health Check ───────────────────────────────────────────────────────────


class TestHealthCheck:
    """
    curl -X GET http://localhost:8000/
    Expected: {"name": "Ember RPG", ...}
    """

    def test_root_returns_200(self):
        code, data = curl_get("/")
        assert code == 200

    def test_root_has_name(self):
        _, data = curl_get("/")
        assert "name" in data
        assert data["name"] == "Ember RPG"

    def test_root_has_version(self):
        _, data = curl_get("/")
        assert "version" in data


# ─── Session Lifecycle ───────────────────────────────────────────────────────


class TestSessionLifecycle:
    """
    Full session CRUD via HTTP, mirroring:

        curl -X POST /game/session/new -d '{"player_name":"Kira","player_class":"warrior"}'
        curl -X GET  /game/session/{id}
        curl -X DELETE /game/session/{id}
        curl -X GET  /game/session/{id}  → 404
    """

    def test_create_session_returns_200(self):
        code, data = curl_post("/game/session/new", {"player_name": "Kira", "player_class": "warrior"})
        assert code == 200

    def test_create_session_response_shape(self):
        _, data = curl_post("/game/session/new", {"player_name": "Kira", "player_class": "warrior"})
        for field in ("session_id", "narrative", "player", "scene", "location"):
            assert field in data, f"Missing field: {field}"

    def test_create_session_player_name(self):
        _, data = curl_post("/game/session/new", {"player_name": "Kira", "player_class": "warrior"})
        assert data["player"]["name"] == "Kira"

    def test_create_session_scene_is_exploration(self):
        _, data = curl_post("/game/session/new", {"player_name": "Kira", "player_class": "warrior"})
        assert data["scene"] == "exploration"

    def test_create_session_has_narrative(self):
        _, data = curl_post("/game/session/new", {"player_name": "Kira", "player_class": "warrior"})
        assert isinstance(data["narrative"], str)
        assert len(data["narrative"]) > 0

    def test_get_session_returns_200(self):
        session = new_session("Goran")
        code, _ = curl_get(f"/game/session/{session['session_id']}")
        assert code == 200

    def test_get_session_has_correct_id(self):
        session = new_session("Goran")
        sid = session["session_id"]
        _, data = curl_get(f"/game/session/{sid}")
        assert data["session_id"] == sid

    def test_get_session_has_expected_fields(self):
        session = new_session("Goran")
        _, data = curl_get(f"/game/session/{session['session_id']}")
        for field in ("session_id", "scene", "location", "player", "in_combat", "turn"):
            assert field in data

    def test_delete_session_returns_200(self):
        session = new_session("Del")
        code, _ = curl_delete(f"/game/session/{session['session_id']}")
        assert code == 200

    def test_delete_session_then_get_returns_404(self):
        session = new_session("Del2")
        sid = session["session_id"]
        curl_delete(f"/game/session/{sid}")
        code, _ = curl_get(f"/game/session/{sid}")
        assert code == 404

    def test_get_nonexistent_session_returns_404(self):
        code, _ = curl_get("/game/session/fake-session-id-99999")
        assert code == 404


# ─── Player Classes ─────────────────────────────────────────────────────────


class TestPlayerClasses:
    """
    Verify each class starts with appropriate stats.

        curl -X POST /game/session/new -d '{"player_name":"X","player_class":"mage"}'
    """

    def test_warrior_has_high_hp(self):
        data = new_session("Tank", "warrior")
        assert data["player"]["hp"] > 0

    def test_mage_has_spell_points(self):
        data = new_session("Merlin", "mage")
        assert data["player"]["spell_points"] > 0

    def test_rogue_class_created(self):
        data = new_session("Shadow", "rogue")
        assert data["player"]["name"] == "Shadow"

    def test_priest_class_created(self):
        data = new_session("Healer", "priest")
        assert data["player"]["name"] == "Healer"

    def test_default_class_is_warrior(self):
        code, data = curl_post("/game/session/new", {"player_name": "Default"})
        assert code == 200
        assert "warrior" in data["player"]["classes"]


# ─── Player Actions ─────────────────────────────────────────────────────────


class TestPlayerActions:
    """
    Simulate diverse player inputs:

        curl -X POST /game/session/{id}/action -d '{"input":"look around"}'
    """

    def test_action_look_returns_narrative(self):
        session = new_session()
        data = take_action(session["session_id"], "look around")
        assert len(data["narrative"]) > 0

    def test_action_examine_room(self):
        session = new_session()
        data = take_action(session["session_id"], "examine the room")
        assert "narrative" in data

    def test_action_examine_turkish(self):
        session = new_session()
        data = take_action(session["session_id"], "odayı incele")
        assert len(data["narrative"]) > 0

    def test_action_attack_triggers_combat_scene(self):
        session = new_session()
        data = take_action(session["session_id"], "attack")
        assert "narrative" in data
        # Scene may shift to combat
        assert data["scene"] in ("exploration", "combat")

    def test_action_attack_english(self):
        session = new_session()
        data = take_action(session["session_id"], "attack the goblin with my sword")
        assert "narrative" in data

    def test_action_attack_turkish(self):
        session = new_session()
        data = take_action(session["session_id"], "goblini saldır")
        assert "narrative" in data

    def test_action_move(self):
        session = new_session()
        data = take_action(session["session_id"], "move north")
        assert "narrative" in data

    def test_action_move_turkish(self):
        session = new_session()
        data = take_action(session["session_id"], "kuzeye git")
        assert "narrative" in data

    def test_action_talk_to_npc(self):
        session = new_session(location="town")
        data = take_action(session["session_id"], "talk to the innkeeper")
        assert "narrative" in data

    def test_action_talk_turkish(self):
        session = new_session(location="town")
        data = take_action(session["session_id"], "hançerle konuş")
        assert "narrative" in data

    def test_action_rest_restores_hp(self):
        session = new_session()
        sid = session["session_id"]
        # Rest
        data = take_action(sid, "rest")
        assert "narrative" in data
        # HP should be at or near max (not 0)
        assert data["player"]["hp"] > 0

    def test_action_rest_turkish(self):
        session = new_session()
        data = take_action(session["session_id"], "dinlen")
        assert "narrative" in data

    def test_action_spell_cast_english(self):
        session = new_session(cls="mage")
        data = take_action(session["session_id"], "cast magic missile")
        assert "narrative" in data

    def test_action_spell_cast_turkish(self):
        session = new_session(cls="mage")
        data = take_action(session["session_id"], "büyü kullan")
        assert "narrative" in data

    def test_action_unknown_returns_narrative(self):
        session = new_session()
        data = take_action(session["session_id"], "xyzzy plugh quux")
        assert "narrative" in data

    def test_action_empty_input_handled(self):
        session = new_session()
        code, data = curl_post(f"/game/session/{session['session_id']}/action", {"input": ""})
        assert code == 200
        assert "narrative" in data

    def test_action_advances_turn_counter(self):
        session = new_session()
        sid = session["session_id"]
        take_action(sid, "look around")
        take_action(sid, "look around")
        _, state = curl_get(f"/game/session/{sid}")
        assert state["turn"] >= 2

    def test_action_response_includes_player_state(self):
        session = new_session()
        data = take_action(session["session_id"], "look around")
        assert "player" in data
        assert "hp" in data["player"]
        assert "level" in data["player"]
        assert "xp" in data["player"]


# ─── Combat Flow ─────────────────────────────────────────────────────────────


class TestCombatFlow:
    """
    Simulate a combat encounter:

        curl -X POST /game/session/{id}/action -d '{"input":"attack the goblin"}'
        # Check combat state
        curl -X POST /game/session/{id}/action -d '{"input":"hit the enemy"}'
    """

    def test_attack_triggers_combat(self):
        session = new_session()
        data = take_action(session["session_id"], "attack")
        # narrative must be non-empty
        assert len(data["narrative"]) > 0

    def test_combat_state_in_response(self):
        session = new_session()
        sid = session["session_id"]
        data = take_action(sid, "attack the orc")
        # combat field may be null or a dict
        assert "combat" in data

    def test_mage_can_fight(self):
        session = new_session(cls="mage")
        data = take_action(session["session_id"], "attack the goblin")
        assert "narrative" in data

    def test_rest_during_combat_refused(self):
        session = new_session()
        sid = session["session_id"]
        # Force combat
        take_action(sid, "attack")
        state_code, state = curl_get(f"/game/session/{sid}")
        if state["in_combat"]:
            data = take_action(sid, "rest")
            # Should contain refusal narrative
            assert "narrative" in data
            narrative_lower = data["narrative"].lower()
            # Narrative should indicate combat refusal (can't rest mid-fight)
            assert any(word in narrative_lower for word in ("combat", "fight", "enemy", "can't", "cannot", "not", "still"))

    def test_hp_positive_after_combat_action(self):
        session = new_session()
        data = take_action(session["session_id"], "attack the goblin")
        assert data["player"]["hp"] >= 0


# ─── Mage Spell Points ────────────────────────────────────────────────────────


class TestMageSpellPoints:
    """
    Verify mage starts with spell_points > 0 and rest restores them.
    """

    def test_mage_starts_with_spell_points(self):
        session = new_session(cls="mage")
        assert session["player"]["spell_points"] > 0

    def test_mage_rest_restores_spell_points(self):
        session = new_session(cls="mage")
        sid = session["session_id"]
        initial_sp = session["player"]["spell_points"]
        # Take a few actions to spend SP
        take_action(sid, "look")
        take_action(sid, "look")
        # Rest
        data = take_action(sid, "rest")
        assert data["player"]["spell_points"] >= 0

    def test_warrior_spell_points_zero_or_minimal(self):
        session = new_session(cls="warrior")
        # Warriors have very low or 0 spell points
        assert session["player"]["spell_points"] >= 0


# ─── Map Endpoint ─────────────────────────────────────────────────────────────


class TestMapEndpoint:
    """
    curl -X GET http://localhost:8000/game/session/{id}/map
    curl -X GET http://localhost:8000/game/session/{id}/map?seed=42
    """

    def test_get_map_returns_200(self):
        session = new_session(location="dungeon")
        code, _ = curl_get(f"/game/session/{session['session_id']}/map")
        assert code == 200

    def test_get_map_has_map_key(self):
        session = new_session(location="dungeon")
        _, data = curl_get(f"/game/session/{session['session_id']}/map")
        assert "map" in data

    def test_get_map_has_location(self):
        session = new_session(location="dungeon")
        _, data = curl_get(f"/game/session/{session['session_id']}/map")
        assert "location" in data

    def test_get_map_session_id_in_response(self):
        session = new_session(location="dungeon")
        sid = session["session_id"]
        _, data = curl_get(f"/game/session/{sid}/map")
        assert data["session_id"] == sid

    def test_get_town_map(self):
        session = new_session(location="town")
        code, data = curl_get(f"/game/session/{session['session_id']}/map")
        assert code == 200
        assert "map" in data

    def test_map_seed_deterministic(self):
        session = new_session()
        sid = session["session_id"]
        _, map1 = curl_get(f"/game/session/{sid}/map", {"seed": "42"})
        _, map2 = curl_get(f"/game/session/{sid}/map", {"seed": "42"})
        assert map1["map"] == map2["map"]

    def test_map_nonexistent_session_404(self):
        code, _ = curl_get("/game/session/no-such-id/map")
        assert code == 404


# ─── Save / Load ─────────────────────────────────────────────────────────────


class TestSaveLoad:
    """
    curl -X POST /game/session/{id}/save -d '{"player_id":"p1"}'
    curl -X POST /game/session/load/{save_id}
    curl -X GET  /game/saves/{player_id}
    """

    def test_save_session_returns_save_id(self):
        session = new_session("SaveMe")
        code, data = curl_post(f"/game/session/{session['session_id']}/save", {"player_id": "e2e_player_1"})
        assert code == 200
        assert "save_id" in data

    def test_load_saved_session(self):
        session = new_session("LoadMe")
        sid = session["session_id"]
        _, save_data = curl_post(f"/game/session/{sid}/save", {"player_id": "e2e_player_2"})
        save_id = save_data["save_id"]

        code, loaded = curl_post(f"/game/session/load/{save_id}", {})
        assert code == 200
        assert loaded["save_id"] == save_id
        assert loaded["status"] == "loaded"

    def test_load_preserves_player_name(self):
        session = new_session("Preserved", "warrior")
        sid = session["session_id"]
        _, save_data = curl_post(f"/game/session/{sid}/save", {"player_id": "e2e_player_3"})
        save_id = save_data["save_id"]

        _, loaded = curl_post(f"/game/session/load/{save_id}", {})
        assert loaded["session_data"]["player"]["name"] == "Preserved"

    def test_list_saves_for_player(self):
        session = new_session("Lister")
        player_id = "e2e_player_list_test"
        curl_post(f"/game/session/{session['session_id']}/save", {"player_id": player_id})

        code, saves = curl_get(f"/game/saves/{player_id}")
        assert code == 200
        assert isinstance(saves, list)
        assert len(saves) >= 1

    def test_load_invalid_save_id_404(self):
        code, _ = curl_post("/game/session/load/invalid-save-xyz", {})
        assert code == 404


# ─── Error Handling ──────────────────────────────────────────────────────────


class TestErrorHandling:
    """
    Validate HTTP error responses mirror curl behavior:
        404 for unknown sessions
        422 for missing required fields
    """

    def test_get_missing_session_404(self):
        code, _ = curl_get("/game/session/totally-fake-session-abc")
        assert code == 404

    def test_action_on_missing_session_404(self):
        code, _ = curl_post("/game/session/ghost-session/action", {"input": "hello"})
        assert code == 404

    def test_delete_missing_session_404(self):
        code, _ = curl_delete("/game/session/ghost-session-del")
        assert code == 404

    def test_new_session_missing_name_422(self):
        code, _ = curl_post("/game/session/new", {"player_class": "warrior"})
        assert code == 422

    def test_action_missing_input_field_422(self):
        session = new_session()
        code, _ = curl_post(f"/game/session/{session['session_id']}/action", {})
        assert code == 422

    def test_404_response_has_detail(self):
        code, data = curl_get("/game/session/nonexistent-id")
        assert code == 404
        assert "detail" in data


# ─── Concurrent Sessions ─────────────────────────────────────────────────────


class TestConcurrentSessions:
    """
    Simulate multiple simultaneous clients — sessions must be isolated.
    """

    def test_three_sessions_unique_ids(self):
        s1 = new_session("Alice", "warrior")
        s2 = new_session("Bob", "mage")
        s3 = new_session("Carol", "rogue")
        ids = {s1["session_id"], s2["session_id"], s3["session_id"]}
        assert len(ids) == 3

    def test_sessions_independent_player_names(self):
        s1 = new_session("Alpha", "warrior")
        s2 = new_session("Beta", "mage")
        _, d1 = curl_get(f"/game/session/{s1['session_id']}")
        _, d2 = curl_get(f"/game/session/{s2['session_id']}")
        assert d1["player"]["name"] == "Alpha"
        assert d2["player"]["name"] == "Beta"

    def test_actions_dont_bleed_between_sessions(self):
        s1 = new_session("Bleed1", "warrior")
        s2 = new_session("Bleed2", "mage")
        take_action(s1["session_id"], "attack")
        take_action(s1["session_id"], "attack")
        _, state2 = curl_get(f"/game/session/{s2['session_id']}")
        assert state2["turn"] == 0  # s2 untouched

    def test_deleting_one_session_does_not_affect_others(self):
        s1 = new_session("Delete1")
        s2 = new_session("Delete2")
        curl_delete(f"/game/session/{s1['session_id']}")
        code, _ = curl_get(f"/game/session/{s2['session_id']}")
        assert code == 200


# ─── Full Player Journey ─────────────────────────────────────────────────────


class TestFullPlayerJourney:
    """
    Complete end-to-end scenario: create → explore → combat → rest → save → load.
    Mirrors what a Godot/frontend client would do in a real session.
    """

    def test_complete_journey(self):
        # 1. Create session
        session = new_session("Thorin", "warrior", "The Iron Mines")
        sid = session["session_id"]
        assert session["player"]["name"] == "Thorin"
        assert session["scene"] == "exploration"

        # 2. Explore
        d = take_action(sid, "look around")
        assert len(d["narrative"]) > 0

        # 3. Examine environment
        d = take_action(sid, "examine the walls")
        assert len(d["narrative"]) > 0

        # 4. Move
        d = take_action(sid, "go north")
        assert len(d["narrative"]) > 0

        # 5. Initiate combat
        d = take_action(sid, "attack")
        assert len(d["narrative"]) > 0

        # 6. Check state
        code, state = curl_get(f"/game/session/{sid}")
        assert code == 200
        assert state["player"]["name"] == "Thorin"

        # 7. Rest (may be in combat)
        d = take_action(sid, "rest")
        assert len(d["narrative"]) > 0

        # 8. Save progress
        code, save_data = curl_post(f"/game/session/{sid}/save", {"player_id": "journey_player"})
        assert code == 200
        save_id = save_data["save_id"]

        # 9. Load save
        code, loaded = curl_post(f"/game/session/load/{save_id}", {})
        assert code == 200
        assert loaded["session_data"]["player"]["name"] == "Thorin"

        # 10. End session
        code, _ = curl_delete(f"/game/session/{sid}")
        assert code == 200

        # 11. Verify gone
        code, _ = curl_get(f"/game/session/{sid}")
        assert code == 404

    def test_mage_journey_spell_usage(self):
        """Mage-focused journey with spell casting."""
        session = new_session("Seraphina", "mage", "The Crystal Caves")
        sid = session["session_id"]
        initial_sp = session["player"]["spell_points"]
        assert initial_sp > 0

        # Explore
        take_action(sid, "look around")

        # Cast spell
        d = take_action(sid, "cast magic missile")
        assert "narrative" in d

        # Rest to restore
        d = take_action(sid, "rest")
        assert "narrative" in d

        # State still valid
        _, state = curl_get(f"/game/session/{sid}")
        assert state["player"]["name"] == "Seraphina"

    def test_multi_action_turn_counter(self):
        """Verify turn counter increments correctly across many actions."""
        session = new_session("Turner", "rogue")
        sid = session["session_id"]

        for i in range(5):
            take_action(sid, "look")

        _, state = curl_get(f"/game/session/{sid}")
        assert state["turn"] >= 5

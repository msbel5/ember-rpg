"""
Ember RPG - FastAPI endpoint integration tests
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from engine.api.routes import _sessions

client = TestClient(app)


class TestRootEndpoint:
    def test_root(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Ember RPG"


class TestSessionEndpoints:

    def _new_session(self, name="Aria", cls="warrior"):
        resp = client.post("/game/session/new", json={
            "player_name": name,
            "player_class": cls,
        })
        assert resp.status_code == 200
        return resp.json()

    def test_new_session(self):
        data = self._new_session()
        assert "session_id" in data
        assert "narrative" in data
        assert data["player"]["name"] == "Aria"
        assert data["scene"] == "exploration"

    def test_new_session_mage(self):
        data = self._new_session("Kael", "mage")
        assert data["player"]["spell_points"] > 0

    def test_get_session(self):
        created = self._new_session()
        sid = created["session_id"]
        resp = client.get(f"/game/session/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid

    def test_get_nonexistent_session(self):
        resp = client.get("/game/session/nonexistent-id")
        assert resp.status_code == 404

    def test_action_examine(self):
        created = self._new_session()
        sid = created["session_id"]
        resp = client.post(f"/game/session/{sid}/action", json={"input": "odayı incele"})
        assert resp.status_code == 200
        data = resp.json()
        assert "narrative" in data
        assert len(data["narrative"]) > 0

    def test_action_attack(self):
        created = self._new_session()
        sid = created["session_id"]
        resp = client.post(f"/game/session/{sid}/action", json={"input": "saldır"})
        assert resp.status_code == 200
        data = resp.json()
        assert "narrative" in data

    def test_action_rest(self):
        created = self._new_session()
        sid = created["session_id"]
        resp = client.post(f"/game/session/{sid}/action", json={"input": "dinlen"})
        assert resp.status_code == 200
        data = resp.json()
        assert "narrative" in data

    def test_action_unknown(self):
        created = self._new_session()
        sid = created["session_id"]
        resp = client.post(f"/game/session/{sid}/action", json={"input": "xyzzy plugh"})
        assert resp.status_code == 200
        data = resp.json()
        assert "narrative" in data

    def test_action_on_nonexistent_session(self):
        resp = client.post("/game/session/bad-id/action", json={"input": "bak"})
        assert resp.status_code == 404

    def test_delete_session(self):
        created = self._new_session()
        sid = created["session_id"]
        resp = client.delete(f"/game/session/{sid}")
        assert resp.status_code == 200
        # Session should be gone
        resp2 = client.get(f"/game/session/{sid}")
        assert resp2.status_code == 404

    def test_response_includes_player_state(self):
        created = self._new_session()
        sid = created["session_id"]
        resp = client.post(f"/game/session/{sid}/action", json={"input": "bak"})
        data = resp.json()
        player = data["player"]
        assert "hp" in player
        assert "level" in player
        assert "spell_points" in player

    def test_action_response_includes_canonical_fr15_fields(self):
        created = self._new_session()
        sid = created["session_id"]

        resp = client.post(f"/game/session/{sid}/action", json={"input": "bak"})
        assert resp.status_code == 200
        data = resp.json()
        snapshot = _sessions[sid].to_dict()

        assert "active_quests" in data
        assert "quest_offers" in data
        assert "ground_items" in data
        assert "campaign_state" in data
        assert data["active_quests"] == snapshot.get("active_quests", [])
        assert data["quest_offers"] == snapshot.get("quest_offers", [])
        assert data["ground_items"] == snapshot.get("ground_items", [])
        assert data["campaign_state"] == snapshot.get("campaign_state", {})

    def test_action_attack_response_player_ap_matches_combat_ap(self):
        created = self._new_session()
        sid = created["session_id"]

        resp = client.post(f"/game/session/{sid}/action", json={"input": "saldır"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["combat"] is not None
        player_name = data["player"]["name"]
        combat_player = next(combatant for combatant in data["combat"]["combatants"] if combatant["name"] == player_name)

        assert data["player"]["ap"]["current"] == combat_player["ap"]
        assert data["player"]["ap"]["max"] == 3

    def test_custom_location(self):
        resp = client.post("/game/session/new", json={
            "player_name": "Aria",
            "player_class": "warrior",
            "location": "Dark Tower"
        })
        assert resp.status_code == 200
        assert resp.json()["location"] == "Dark Tower"

    def test_delete_session_does_not_restore_from_manual_save(self):
        created = self._new_session("ManualSave", "warrior")
        sid = created["session_id"]
        slot_name = f"manual_restore_{sid.replace('-', '_')}"

        try:
            save_resp = client.post(
                f"/game/session/{sid}/save",
                json={"player_id": "manual_restore_player", "slot_name": slot_name},
            )
            assert save_resp.status_code == 200

            load_resp = client.post(f"/game/session/load/{slot_name}")
            assert load_resp.status_code == 200

            delete_resp = client.delete(f"/game/session/{sid}")
            assert delete_resp.status_code == 200

            resp = client.get(f"/game/session/{sid}")
            assert resp.status_code == 404
        finally:
            client.delete(f"/game/saves/{slot_name}")


class TestMapEndpoint:

    def _new_session(self, location="Dark Keep"):
        resp = client.post("/game/session/new", json={
            "player_name": "Scout",
            "player_class": "rogue",
            "location": location,
        })
        assert resp.status_code == 200
        return resp.json()["session_id"]

    def test_get_map_dungeon(self):
        sid = self._new_session("Dark Dungeon")
        resp = client.get(f"/game/session/{sid}/map")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert "map" in data
        assert "tiles" in data["map"]

    def test_get_map_town(self):
        sid = self._new_session("Harbor Town")
        resp = client.get(f"/game/session/{sid}/map")
        assert resp.status_code == 200
        data = resp.json()
        assert "map" in data
        assert data["map"]["metadata"]["map_type"] in ("dungeon", "town")

    def test_get_map_seeded(self):
        sid = self._new_session("Forest Road")
        resp1 = client.get(f"/game/session/{sid}/map?seed=42")
        resp2 = client.get(f"/game/session/{sid}/map?seed=42")
        assert resp1.status_code == 200
        assert resp1.json()["map"]["width"] == resp2.json()["map"]["width"]

    def test_get_map_nonexistent_session(self):
        resp = client.get("/game/session/no-such-id/map")
        assert resp.status_code == 404

    def test_map_has_required_fields(self):
        sid = self._new_session()
        resp = client.get(f"/game/session/{sid}/map")
        m = resp.json()["map"]
        assert "width" in m
        assert "height" in m
        assert "tiles" in m


# ---------------------------------------------------------------------------
# Save route error path coverage
# ---------------------------------------------------------------------------

class TestSaveRouteErrors:
    """Cover error paths in save_routes.py."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_save_nonexistent_session(self):
        resp = self.client.post("/game/session/does-not-exist/save", json={"player_id": "p1"})
        assert resp.status_code == 404

    def test_get_save_not_found(self):
        resp = self.client.get("/game/saves/file/nonexistent-save-id")
        assert resp.status_code == 404

    def test_delete_save_not_found(self):
        resp = self.client.delete("/game/saves/nonexistent-save-id")
        assert resp.status_code == 404

    def test_load_session_not_found(self):
        resp = self.client.post("/game/session/load/nonexistent-save-id")
        assert resp.status_code == 404

    def test_save_and_list_saves(self):
        # Create a session
        s = self.client.post("/game/session/new", json={"player_name": "SaveTest", "player_class": "warrior"})
        sid = s.json()["session_id"]
        # Save it
        r = self.client.post(f"/game/session/{sid}/save", json={"player_id": "player_save_test"})
        assert r.status_code == 200
        save_id = r.json()["save_id"]
        # List saves
        lst = self.client.get("/game/saves/player_save_test")
        assert lst.status_code == 200
        assert any(sv["save_id"] == save_id for sv in lst.json())
        # Get specific save
        g = self.client.get(f"/game/saves/file/{save_id}")
        assert g.status_code == 200
        # Load session
        load = self.client.post(f"/game/session/load/{save_id}")
        assert load.status_code == 200
        # Delete save
        d = self.client.delete(f"/game/saves/{save_id}")
        assert d.status_code == 200

    def test_load_session_returns_canonical_structured_inventory(self):
        created = self.client.post(
            "/game/session/new",
            json={"player_name": "CanonicalLoad", "player_class": "warrior"},
        )
        sid = created.json()["session_id"]
        save_resp = self.client.post(
            f"/game/session/{sid}/save",
            json={"player_id": "canonical_load_player", "slot_name": "canonical_load_slot"},
        )
        assert save_resp.status_code == 200

        try:
            load_resp = self.client.post("/game/session/load/canonical_load_slot")
            assert load_resp.status_code == 200
            data = load_resp.json()["session_data"]
            player_inventory = data["player"]["inventory"]
            assert isinstance(player_inventory, list)
            assert player_inventory
            assert isinstance(player_inventory[0], dict)
            assert "id" in player_inventory[0]
        finally:
            self.client.delete("/game/saves/canonical_load_slot")

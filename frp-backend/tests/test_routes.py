"""
Ember RPG - FastAPI endpoint integration tests
"""
import pytest
from fastapi.testclient import TestClient
from main import app

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

    def test_custom_location(self):
        resp = client.post("/game/session/new", json={
            "player_name": "Aria",
            "player_class": "warrior",
            "location": "Dark Tower"
        })
        assert resp.status_code == 200
        assert resp.json()["location"] == "Dark Tower"


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

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
            "location": "Karanlık Kule"
        })
        assert resp.status_code == 200
        assert resp.json()["location"] == "Karanlık Kule"

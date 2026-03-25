"""
TDD: Inventory endpoint tests
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _create_session():
    resp = client.post("/game/session/new", json={"player_name": "Tester", "player_class": "Fighter"})
    assert resp.status_code == 200
    return resp.json()["session_id"]


def test_get_inventory_empty():
    sid = _create_session()
    resp = client.get(f"/game/session/{sid}/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert "inventory" in data
    assert isinstance(data["inventory"], list)


def test_get_inventory_with_items():
    sid = _create_session()
    # Add items via session state - inject directly
    from engine.api.routes import _sessions
    session = _sessions.get(sid)
    if session:
        session.player.inventory = ["iron_shortsword", "potion_of_healing", "leather_armor"]
    resp = client.get(f"/game/session/{sid}/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert "iron_shortsword" in data["inventory"]
    assert "potion_of_healing" in data["inventory"]


def test_equip_item():
    sid = _create_session()
    from engine.api.routes import _sessions
    session = _sessions.get(sid)
    if session:
        session.player.inventory = ["iron_shortsword"]
    resp = client.post(f"/game/session/{sid}/inventory/equip", json={"item_id": "iron_shortsword"})
    assert resp.status_code == 200
    data = resp.json()
    assert "slot" in data
    assert data["equipped"] == "iron_shortsword"


def test_equip_item_not_in_inventory():
    sid = _create_session()
    resp = client.post(f"/game/session/{sid}/inventory/equip", json={"item_id": "magic_sword"})
    assert resp.status_code == 404


def test_drop_item():
    sid = _create_session()
    from engine.api.routes import _sessions
    session = _sessions.get(sid)
    if session:
        session.player.inventory = ["potion_of_healing", "iron_shortsword"]
    resp = client.post(f"/game/session/{sid}/inventory/drop", json={"item_id": "potion_of_healing"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["dropped"] == "potion_of_healing"
    # Verify it's gone
    resp2 = client.get(f"/game/session/{sid}/inventory")
    assert "potion_of_healing" not in resp2.json()["inventory"]


def test_drop_item_not_in_inventory():
    sid = _create_session()
    resp = client.post(f"/game/session/{sid}/inventory/drop", json={"item_id": "ghost_item"})
    assert resp.status_code == 404


def test_get_equipped():
    sid = _create_session()
    from engine.api.routes import _sessions
    session = _sessions.get(sid)
    if session:
        session.player.equipment = {"weapon": "iron_shortsword", "armor": "leather_armor"}
    resp = client.get(f"/game/session/{sid}/inventory/equipped")
    assert resp.status_code == 200
    data = resp.json()
    assert "equipped" in data
    assert data["equipped"].get("weapon") == "iron_shortsword"


def test_equip_updates_equipment_slot():
    sid = _create_session()
    from engine.api.routes import _sessions
    session = _sessions.get(sid)
    if session:
        session.player.inventory = ["iron_shortsword", "steel_axe"]
        session.player.equipment = {}
    resp = client.post(f"/game/session/{sid}/inventory/equip", json={"item_id": "iron_shortsword"})
    assert resp.status_code == 200
    # Check equipped endpoint shows it
    resp2 = client.get(f"/game/session/{sid}/inventory/equipped")
    assert resp2.status_code == 200
    equipped = resp2.json()["equipped"]
    assert "weapon" in equipped


def test_inventory_session_not_found():
    resp = client.get("/game/session/nonexistent-id/inventory")
    assert resp.status_code == 404

"""
Tests for Shop/Merchant Endpoints (Deliverable 5)
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)

# ── Helper ────────────────────────────────────────────────────────────────────

def create_session(player_name="TestHero", player_class="warrior"):
    resp = client.post("/game/session/new", json={
        "player_name": player_name,
        "player_class": player_class,
    })
    assert resp.status_code == 200
    return resp.json()["session_id"]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_get_shop_inventory():
    """GET /shop/{npc_id} should return list of items."""
    resp = client.get("/game/shop/merchant_general_goods")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) > 0
    item = data["items"][0]
    assert "id" in item
    assert "name" in item
    assert "buy_price" in item
    assert "sell_price" in item


def test_get_shop_inventory_blacksmith():
    """Blacksmith should sell weapons/armor."""
    resp = client.get("/game/shop/misc_blacksmith")
    assert resp.status_code == 200
    data = resp.json()
    types = [item["type"] for item in data["items"]]
    assert any(t in ("weapon", "armor", "shield") for t in types)


def test_get_shop_inventory_not_found():
    """NPC that doesn't exist should return 404."""
    resp = client.get("/game/shop/nonexistent_npc")
    assert resp.status_code == 404


def test_get_shop_no_inventory():
    """NPC without shop_inventory should return 404."""
    resp = client.get("/game/shop/guard_captain")
    assert resp.status_code == 404


def test_buy_item_deducts_gold():
    """Buying an item should deduct gold and add item to inventory."""
    session_id = create_session()

    # Give player some gold first via direct session access
    from engine.api.routes import _sessions
    session = _sessions[session_id]
    session.player.gold = 500

    # Find a cheap item in the shop
    shop_resp = client.get("/game/shop/merchant_general_goods")
    item_id = shop_resp.json()["items"][0]["id"]
    buy_price = shop_resp.json()["items"][0]["buy_price"]

    resp = client.post(f"/game/shop/merchant_general_goods/buy", json={
        "session_id": session_id,
        "item_id": item_id,
        "quantity": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["price_paid"] == buy_price
    assert data["gold_remaining"] == 500 - buy_price
    assert item_id in session.player.inventory


def test_buy_item_insufficient_gold():
    """Buying with insufficient gold should return 400."""
    session_id = create_session()
    from engine.api.routes import _sessions
    session = _sessions[session_id]
    session.player.gold = 0

    resp = client.post("/game/shop/merchant_general_goods/buy", json={
        "session_id": session_id,
        "item_id": "potion_of_healing",
        "quantity": 1,
    })
    assert resp.status_code == 400
    assert "Insufficient" in resp.json()["detail"]


def test_buy_item_not_in_shop():
    """Buying an item not in the shop should return 404."""
    session_id = create_session()
    from engine.api.routes import _sessions
    session = _sessions[session_id]
    session.player.gold = 9999

    resp = client.post("/game/shop/merchant_general_goods/buy", json={
        "session_id": session_id,
        "item_id": "vorpal_sword",  # Not in general goods shop
        "quantity": 1,
    })
    assert resp.status_code == 404


def test_sell_item_adds_gold():
    """Selling an item should add gold and remove from inventory."""
    session_id = create_session()
    from engine.api.routes import _sessions
    session = _sessions[session_id]
    session.player.gold = 0
    session.inventory = [{"id": "potion_of_healing", "name": "Potion Of Healing", "qty": 1}]
    session.sync_player_state()

    # Get sell price from shop
    shop_resp = client.get("/game/shop/merchant_general_goods")
    items = {i["id"]: i for i in shop_resp.json()["items"]}
    sell_price = items.get("potion_of_healing", {}).get("sell_price", 0)

    resp = client.post("/game/shop/merchant_general_goods/sell", json={
        "session_id": session_id,
        "item_id": "potion_of_healing",
        "quantity": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["gold_earned"] == sell_price
    assert "potion_of_healing" not in session.player.inventory


def test_sell_item_not_in_inventory():
    """Selling an item the player doesn't have should return 400."""
    session_id = create_session()
    from engine.api.routes import _sessions
    session = _sessions[session_id]
    session.inventory = []
    session.sync_player_state()

    resp = client.post("/game/shop/merchant_general_goods/sell", json={
        "session_id": session_id,
        "item_id": "potion_of_healing",
        "quantity": 1,
    })
    assert resp.status_code == 400


def test_sell_price_is_60_percent():
    """Sell price should be 60% of buy price (rounded down)."""
    resp = client.get("/game/shop/merchant_general_goods")
    for item in resp.json()["items"]:
        expected_sell = int(item["buy_price"] * 0.6)
        assert item["sell_price"] == expected_sell


def test_buy_invalid_session():
    """Buying with invalid session_id should return 404."""
    resp = client.post("/game/shop/merchant_general_goods/buy", json={
        "session_id": "nonexistent-session-id",
        "item_id": "health_potion",
        "quantity": 1,
    })
    assert resp.status_code == 404


def test_require_session_preserves_canonical_inventory_and_equipment():
    """Shop session resolution must not rebuild canonical state from player mirrors."""
    session_id = create_session()
    from engine.api.routes import _sessions
    from engine.api.shop_routes import _require_session

    session = _sessions[session_id]
    session.inventory = [
        {
            "id": "iron_sword",
            "name": "Iron Sword",
            "qty": 1,
            "material": "iron",
            "quality": "masterwork",
            "damage": 9,
            "instance_id": "iron_sword-special",
            "type": "weapon",
            "slot": "weapon",
        }
    ]
    session.set_equipment_slot("weapon", {
        "id": "iron_sword",
        "name": "Iron Sword",
        "material": "iron",
        "quality": "masterwork",
        "damage": 9,
        "instance_id": "iron_sword-special",
        "type": "weapon",
        "slot": "weapon",
    })
    session.ensure_consistency()

    inventory_before = [dict(item) for item in session.inventory]
    equipment_before = dict(session.equipment)
    session.player.inventory = ["junk_item"]
    session.player.equipment = {"weapon": "junk_sword"}

    resolved = _require_session(session_id)

    assert resolved is session
    assert session.inventory == inventory_before
    assert session.equipment["weapon"] == equipment_before["weapon"]
    assert session.player.inventory == ["iron_sword"]
    assert session.player.equipment["weapon"] == "iron_sword"


def test_buy_item_preserves_existing_metadata():
    """Buying another item must not corrupt canonical metadata already in inventory."""
    session_id = create_session()
    from engine.api.routes import _sessions

    session = _sessions[session_id]
    session.player.gold = 500
    session.inventory = [
        {
            "id": "iron_sword",
            "name": "Iron Sword",
            "qty": 1,
            "material": "iron",
            "quality": "masterwork",
            "damage": 9,
            "instance_id": "iron_sword-special",
            "type": "weapon",
            "slot": "weapon",
        }
    ]
    session.ensure_consistency()

    with patch("engine.api.shop_routes._get_npc") as mock_npc, patch("engine.api.shop_routes._get_item") as mock_item:
        mock_npc.return_value = {"id": "merchant", "name": "Merchant", "shop_inventory": ["healing_potion"]}
        mock_item.return_value = {"id": "healing_potion", "name": "Healing Potion", "value": 25, "type": "consumable"}
        resp = client.post("/game/shop/merchant/buy", json={
            "session_id": session_id,
            "item_id": "healing_potion",
            "quantity": 1,
        })

    assert resp.status_code == 200
    sword = next(item for item in session.inventory if item["id"] == "iron_sword")
    assert sword["material"] == "iron"
    assert sword["quality"] == "masterwork"
    assert sword["damage"] == 9
    assert sword["instance_id"] == "iron_sword-special"
    assert sword["qty"] == 1
    assert any(item["id"] == "healing_potion" for item in session.inventory)


def test_sell_item_uses_canonical_stack_qty_and_preserves_metadata():
    """Selling should count canonical stack qty, not player.inventory mirror, and preserve metadata."""
    session_id = create_session()
    from engine.api.routes import _sessions

    session = _sessions[session_id]
    session.player.gold = 0
    session.inventory = [
        {
            "id": "iron_sword",
            "name": "Iron Sword",
            "qty": 1,
            "material": "iron",
            "quality": "masterwork",
            "damage": 9,
            "instance_id": "iron_sword-special",
            "type": "weapon",
            "slot": "weapon",
        },
        {
            "id": "potion_of_healing",
            "name": "Potion Of Healing",
            "qty": 2,
            "quality": "fine",
            "instance_id": "potion-stack-special",
            "type": "item",
        },
    ]
    session.ensure_consistency()
    session.player.inventory = []

    with patch("engine.api.shop_routes._get_npc") as mock_npc, patch("engine.api.shop_routes._get_item") as mock_item:
        mock_npc.return_value = {"id": "merchant", "name": "Merchant", "shop_inventory": ["potion_of_healing"]}
        mock_item.return_value = {"id": "potion_of_healing", "name": "Potion Of Healing", "value": 50, "type": "consumable"}
        resp = client.post("/game/shop/merchant/sell", json={
            "session_id": session_id,
            "item_id": "potion_of_healing",
            "quantity": 1,
        })

    assert resp.status_code == 200
    potion = next(item for item in session.inventory if item["id"] == "potion_of_healing")
    sword = next(item for item in session.inventory if item["id"] == "iron_sword")
    assert potion["qty"] == 1
    assert potion["quality"] == "fine"
    assert potion["instance_id"] == "potion-stack-special"
    assert sword["material"] == "iron"
    assert sword["quality"] == "masterwork"
    assert sword["damage"] == 9
    assert sword["instance_id"] == "iron_sword-special"

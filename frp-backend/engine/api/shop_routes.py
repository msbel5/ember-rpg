"""
Ember RPG - Shop/Merchant Endpoints (Deliverable 5)
Players can buy/sell items through NPC merchants.
"""
import copy
import json
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# ── Path helpers ──────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_HERE, "../../data")

# Lazy-loaded caches
_npc_templates: Optional[list] = None
_item_db: Optional[dict] = None  # id -> item dict


def _load_npc_templates() -> list:
    global _npc_templates
    if _npc_templates is None:
        path = os.path.join(_DATA_DIR, "npc_templates.json")
        with open(path) as f:
            _npc_templates = json.load(f)["npc_templates"]
    return _npc_templates


def _load_items() -> dict:
    global _item_db
    if _item_db is None:
        path = os.path.join(_DATA_DIR, "items.json")
        with open(path) as f:
            raw = json.load(f)["items"]
        _item_db = {item["id"]: item for item in raw if "id" in item}
    return _item_db


def _get_npc(npc_id: str) -> dict:
    """Find NPC template by id. Raises 404 if not found."""
    for npc in _load_npc_templates():
        if npc["id"] == npc_id:
            return npc
    raise HTTPException(status_code=404, detail=f"NPC '{npc_id}' not found")


def _get_item(item_id: str) -> dict:
    """Find item by id. Raises 404 if not found."""
    items = _load_items()
    if item_id not in items:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")
    return items[item_id]


# ── In-memory session store (shared with routes.py) ───────────────────────────
# Import the same store from routes
def _get_sessions():
    from engine.api.routes import _sessions
    return _sessions


def _require_session(session_id: str):
    sessions = _get_sessions()
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if hasattr(session, "ensure_consistency"):
        session.ensure_consistency()
    return session


# ── Request/Response models ───────────────────────────────────────────────────

class BuyRequest(BaseModel):
    session_id: str
    item_id: str
    quantity: int = 1


class SellRequest(BaseModel):
    session_id: str
    item_id: str
    quantity: int = 1


class ShopItemResponse(BaseModel):
    id: str
    name: str
    buy_price: int
    sell_price: int
    type: str
    description: str = ""
    rarity: str = "COMMON"


class ShopInventoryResponse(BaseModel):
    npc_id: str
    npc_name: str
    items: List[ShopItemResponse]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/shop/{npc_id}", response_model=ShopInventoryResponse)
def get_shop_inventory(npc_id: str):
    """List all items for sale by this merchant NPC."""
    npc = _get_npc(npc_id)
    shop_inventory: List[str] = npc.get("shop_inventory", [])
    if not shop_inventory:
        raise HTTPException(status_code=404, detail=f"NPC '{npc_id}' has no shop inventory")

    items_db = _load_items()
    shop_items = []
    for item_id in shop_inventory:
        if item_id in items_db:
            item = items_db[item_id]
            buy_price = item.get("value", 0)
            sell_price = int(buy_price * 0.6)
            shop_items.append(ShopItemResponse(
                id=item_id,
                name=item.get("name", item_id),
                buy_price=buy_price,
                sell_price=sell_price,
                type=item.get("type", "unknown"),
                description=item.get("description", ""),
                rarity=item.get("rarity", "COMMON"),
            ))

    return ShopInventoryResponse(
        npc_id=npc_id,
        npc_name=npc.get("name", npc_id),
        items=shop_items,
    )


@router.post("/shop/{npc_id}/buy")
def buy_item(npc_id: str, req: BuyRequest):
    """Buy an item from a merchant NPC."""
    npc = _get_npc(npc_id)
    shop_inventory: List[str] = npc.get("shop_inventory", [])

    if req.item_id not in shop_inventory:
        raise HTTPException(status_code=404, detail=f"Item '{req.item_id}' is not available in this shop")

    item = _get_item(req.item_id)
    session = _require_session(req.session_id)
    if hasattr(session, "ensure_consistency"):
        session.ensure_consistency()
    player = session.player

    unit_price = item.get("value", 0)
    total_price = unit_price * req.quantity

    # Check player gold
    player_gold = getattr(player, 'gold', 0)
    if player_gold < total_price:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient gold. Need {total_price}g, have {player_gold}g"
        )

    purchased_item = copy.deepcopy(item)
    purchased_item["qty"] = req.quantity
    status = session.assess_item_addition(purchased_item) if hasattr(session, "assess_item_addition") else None
    if status is not None and not status["allowed"]:
        if status["reason"] == "overweight":
            session._record_add_item_failure(status)
            detail = (
                f"{item['name']} is too heavy to carry right now. It would bring you to "
                f"{status['projected_weight']:.1f}/{status['max_weight']:.1f} kg, and you strain your back trying."
            )
        else:
            detail = f"No room to carry {req.quantity}x {item['name']}. Free some inventory space first."
        raise HTTPException(
            status_code=400,
            detail=detail,
        )

    player.gold -= total_price
    added = session.add_item(purchased_item)
    if added is None:
        player.gold += total_price
        error = dict(getattr(session, "narration_context", {}).get("_last_add_item_error", {}) or {})
        if error.get("reason") == "overweight":
            detail = (
                f"{item['name']} is too heavy to carry right now. It would bring you to "
                f"{float(error.get('projected_weight', 0.0)):.1f}/{float(error.get('max_weight', 0.0)):.1f} kg."
            )
        else:
            detail = f"No room to carry {req.quantity}x {item['name']}. Free some inventory space first."
        raise HTTPException(
            status_code=400,
            detail=detail,
        )

    if getattr(session, "location_stock", None) is not None:
        removed = session.location_stock.remove_stock(req.item_id, req.quantity)
        if removed < req.quantity:
            session.location_stock.add_stock(req.item_id, max(0, req.quantity - removed))

    return {
        "message": f"Purchased {req.quantity}x {item['name']} for {total_price}g",
        "item_id": req.item_id,
        "quantity": req.quantity,
        "price_paid": total_price,
        "gold_remaining": player.gold,
    }


@router.post("/shop/{npc_id}/sell")
def sell_item(npc_id: str, req: SellRequest):
    """Sell an item to a merchant NPC."""
    _get_npc(npc_id)  # Validate NPC exists

    item = _get_item(req.item_id)
    session = _require_session(req.session_id)
    if hasattr(session, "ensure_consistency"):
        session.ensure_consistency()
    player = session.player

    owned_count = sum(
        int(entry.get("qty", 1))
        for entry in getattr(session, "inventory", [])
        if entry.get("id") == req.item_id
    )
    if owned_count < req.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"You don't have {req.quantity}x {req.item_id} to sell (have {owned_count})"
        )

    sell_price_each = int(item.get("value", 0) * 0.6)
    total_earned = sell_price_each * req.quantity

    for _ in range(req.quantity):
        session.remove_item(req.item_id)

    if not hasattr(player, 'gold'):
        player.gold = 0
    player.gold += total_earned
    if getattr(session, "location_stock", None) is not None:
        session.location_stock.add_stock(req.item_id, req.quantity)

    return {
        "message": f"Sold {req.quantity}x {item['name']} for {total_earned}g",
        "item_id": req.item_id,
        "quantity": req.quantity,
        "gold_earned": total_earned,
        "gold_total": player.gold,
    }

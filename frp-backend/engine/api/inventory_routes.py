"""
Ember RPG - Inventory Routes
Player inventory management endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional

router = APIRouter()

# Item slot mapping by item ID keywords
ITEM_SLOTS = {
    "sword": "weapon",
    "axe": "weapon",
    "bow": "weapon",
    "staff": "weapon",
    "wand": "weapon",
    "dagger": "weapon",
    "shortsword": "weapon",
    "longsword": "weapon",
    "mace": "weapon",
    "armor": "armor",
    "shield": "offhand",
    "helmet": "helmet",
    "boots": "boots",
    "gloves": "gloves",
    "ring": "ring",
    "amulet": "amulet",
    "cloak": "cloak",
}


def _infer_slot(item_id: str) -> str:
    """Infer equipment slot from item ID."""
    item_lower = item_id.lower()
    for keyword, slot in ITEM_SLOTS.items():
        if keyword in item_lower:
            return slot
    return "misc"


class EquipRequest(BaseModel):
    item_id: str


class DropRequest(BaseModel):
    item_id: str


def _get_sessions():
    from engine.api.routes import _sessions
    return _sessions


@router.get("/session/{session_id}/inventory")
def get_inventory(session_id: str):
    sessions = _get_sessions()
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "inventory": list(session.player.inventory),
        "gold": session.player.gold,
    }


@router.post("/session/{session_id}/inventory/equip")
def equip_item(session_id: str, body: EquipRequest):
    sessions = _get_sessions()
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    item_id = body.item_id
    if item_id not in session.player.inventory:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not in inventory")
    
    slot = _infer_slot(item_id)
    # Unequip previous item in slot (put back to inventory)
    if slot in session.player.equipment:
        old_item = session.player.equipment[slot]
        if old_item not in session.player.inventory:
            session.player.inventory.append(old_item)
    
    session.player.equipment[slot] = item_id
    
    return {
        "session_id": session_id,
        "equipped": item_id,
        "slot": slot,
        "equipment": dict(session.player.equipment),
    }


@router.post("/session/{session_id}/inventory/drop")
def drop_item(session_id: str, body: DropRequest):
    sessions = _get_sessions()
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    item_id = body.item_id
    if item_id not in session.player.inventory:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not in inventory")
    
    session.player.inventory.remove(item_id)
    
    return {
        "session_id": session_id,
        "dropped": item_id,
        "inventory": list(session.player.inventory),
    }


@router.get("/session/{session_id}/inventory/equipped")
def get_equipped(session_id: str):
    sessions = _get_sessions()
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "equipped": dict(session.player.equipment),
    }

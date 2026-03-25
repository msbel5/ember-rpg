"""
Ember RPG - Inventory Routes
Player inventory management endpoints.
"""
from __future__ import annotations

import copy
import uuid
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine.world.entity import Entity, EntityType

router = APIRouter()


class EquipRequest(BaseModel):
    item_id: str


class DropRequest(BaseModel):
    item_id: str


def _get_sessions():
    from engine.api.routes import _sessions
    return _sessions


def _require_session(session_id: str):
    session = _get_sessions().get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    legacy_inventory = list(getattr(session.player, "inventory", []) or [])
    if legacy_inventory:
        session.inventory = [session._normalize_item_record(item) for item in legacy_inventory]
    legacy_equipment = dict(getattr(session.player, "equipment", {}) or {})
    if legacy_equipment:
        merged = dict(session.equipment or {})
        for slot, item in legacy_equipment.items():
            merged[slot] = item
        session.equipment = merged
    if hasattr(session, "ensure_consistency"):
        session.ensure_consistency()
    return session


def _legacy_inventory(session) -> list:
    if hasattr(session, "inventory_item_ids"):
        return session.inventory_item_ids()
    return list(getattr(session.player, "inventory", []))


def _legacy_equipment(session) -> Dict[str, str]:
    if hasattr(session, "equipment_ids"):
        return {slot: item_id for slot, item_id in session.equipment_ids().items() if item_id}
    return dict(getattr(session.player, "equipment", {}))


@router.get("/session/{session_id}/inventory")
def get_inventory(session_id: str):
    session = _require_session(session_id)
    return {
        "session_id": session_id,
        "inventory": _legacy_inventory(session),
        "items": copy.deepcopy(getattr(session, "inventory", [])),
        "gold": getattr(session.player, "gold", 0),
    }


@router.post("/session/{session_id}/inventory/equip")
def equip_item(session_id: str, body: EquipRequest):
    session = _require_session(session_id)
    equipped = session.equip_item(body.item_id) if hasattr(session, "equip_item") else None
    if equipped is None:
        raise HTTPException(status_code=404, detail=f"Item '{body.item_id}' not in inventory")

    return {
        "session_id": session_id,
        "equipped": equipped.get("id", body.item_id),
        "item": copy.deepcopy(equipped),
        "slot": equipped.get("slot", ""),
        "equipment": _legacy_equipment(session),
        "equipment_items": copy.deepcopy(getattr(session, "equipment", {})),
    }


@router.post("/session/{session_id}/inventory/drop")
def drop_item(session_id: str, body: DropRequest):
    session = _require_session(session_id)
    dropped = session.remove_item(body.item_id) if hasattr(session, "remove_item") else None
    if dropped is None:
        raise HTTPException(status_code=404, detail=f"Item '{body.item_id}' not in inventory")

    px, py = session.position[0], session.position[1]
    ground_id = dropped.get("ground_instance_id") or dropped.get("instance_id") or f"ground-{uuid.uuid4().hex[:8]}"
    dropped["ground_instance_id"] = ground_id
    item_entity = Entity(
        id=ground_id,
        entity_type=EntityType.ITEM,
        name=dropped.get("name", dropped.get("id", "Item")),
        position=(px, py),
        glyph="!",
        color="yellow",
        blocking=False,
        inventory=[copy.deepcopy(dropped)],
    )
    if session.spatial_index:
        session.spatial_index.add(item_entity)
    if hasattr(session, "sync_player_state"):
        session.sync_player_state()

    return {
        "session_id": session_id,
        "dropped": dropped.get("id", body.item_id),
        "item": copy.deepcopy(dropped),
        "inventory": _legacy_inventory(session),
        "items": copy.deepcopy(getattr(session, "inventory", [])),
    }


@router.get("/session/{session_id}/inventory/equipped")
def get_equipped(session_id: str):
    session = _require_session(session_id)
    return {
        "session_id": session_id,
        "equipped": _legacy_equipment(session),
        "equipment": copy.deepcopy(getattr(session, "equipment", {})),
    }

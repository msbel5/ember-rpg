"""Shared helper utilities for GameSession state normalization."""
from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List, Optional


def make_conversation_state(
    turn: int,
    *,
    target_type: str = "dm",
    npc_id: Optional[str] = None,
    npc_name: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "target_type": target_type,
        "npc_id": npc_id,
        "npc_name": npc_name,
        "started_turn": int(turn),
    }


def normalize_conversation_state(state: Any, *, turn: int = 0) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return make_conversation_state(turn)
    normalized = make_conversation_state(
        int(state.get("started_turn", turn) or turn),
        target_type=str(state.get("target_type", "dm")),
        npc_id=state.get("npc_id"),
        npc_name=state.get("npc_name"),
    )
    return normalized


def canonical_slot(slot: Optional[str], legacy_slot_aliases: Dict[str, str]) -> Optional[str]:
    if slot is None:
        return None
    slot_lower = slot.lower().strip()
    return legacy_slot_aliases.get(slot_lower, slot_lower)


def display_name(item_id: str) -> str:
    return item_id.replace("_", " ").strip().title() or "Unknown Item"


def infer_slot(item: Dict[str, Any], legacy_slot_aliases: Dict[str, str]) -> Optional[str]:
    item_type = str(item.get("type", "")).lower()
    item_id = str(item.get("id", "")).lower()
    name = str(item.get("name", "")).lower()
    slot = canonical_slot(item.get("slot"), legacy_slot_aliases)
    if slot:
        return slot
    candidates = f"{item_type} {item_id} {name}"
    if "shield" in candidates or item_type == "shield":
        return "shield"
    if "helmet" in candidates or "helm" in candidates:
        return "helmet"
    if "boot" in candidates:
        return "boots"
    if "glove" in candidates or "gauntlet" in candidates:
        return "gloves"
    if "ring" in candidates:
        return "ring"
    if "amulet" in candidates or "necklace" in candidates:
        return "amulet"
    if "armor" in candidates or "mail" in candidates or "robe" in candidates:
        return "armor"
    if item_type == "weapon" or any(word in candidates for word in ["sword", "axe", "dagger", "mace", "staff", "bow", "wand", "hammer"]):
        return "weapon"
    return None


def normalize_item_record(item: Any, legacy_slot_aliases: Dict[str, str]) -> Dict[str, Any]:
    if isinstance(item, str):
        data: Dict[str, Any] = {"id": item, "name": display_name(item), "qty": 1}
    else:
        data = dict(item or {})
    item_id = str(data.get("id") or data.get("item_id") or data.get("name", "")).strip()
    if not item_id:
        item_id = f"item_{uuid.uuid4().hex[:8]}"
    data["id"] = item_id
    data["name"] = str(data.get("name") or display_name(item_id))
    qty = data.get("qty", data.get("quantity", 1))
    try:
        data["qty"] = max(1, int(qty))
    except (TypeError, ValueError):
        data["qty"] = 1
    slot = infer_slot(data, legacy_slot_aliases)
    if slot:
        data["slot"] = slot
    data.setdefault("type", slot or "item")
    quality = data.get("quality")
    if hasattr(quality, "value"):
        data["quality"] = quality.value
    data.setdefault("instance_id", data.get("ground_instance_id") or f"{item_id}-{uuid.uuid4().hex[:8]}")
    if data.get("ground_instance_id") is None and data.get("entity_id"):
        data["ground_instance_id"] = data["entity_id"]
    return data


def item_stack_key(item: Dict[str, Any]) -> tuple:
    return (
        item.get("id"),
        item.get("name"),
        item.get("type"),
        item.get("slot"),
        item.get("material"),
        item.get("quality"),
        item.get("damage"),
        item.get("ac_bonus"),
        item.get("heal"),
        item.get("restore_sp"),
        item.get("uses"),
    )


def is_stackable(item: Dict[str, Any]) -> bool:
    if item.get("slot"):
        return False
    if item.get("uses") is not None:
        return False
    return item.get("type") not in {"weapon", "armor", "shield"}


def canonical_offer_source(source: Optional[str], default_source: str = "authored") -> str:
    source_value = str(source or default_source or "authored").strip().lower()
    if source_value not in {"authored", "emergent"}:
        return "authored"
    return source_value


def normalize_quest_offer(offer: Any, default_source: str = "authored") -> Dict[str, Any]:
    data = copy.deepcopy(dict(offer or {}))
    meta = data.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    offer_id = str(data.get("id") or "").strip()
    if not offer_id:
        offer_id = f"quest_offer_{uuid.uuid4().hex[:8]}"
    data["id"] = offer_id
    if not data.get("kind"):
        offer_kind = data.get("type") or meta.get("kind") or meta.get("type")
        if offer_kind:
            data["kind"] = str(offer_kind).strip().lower()
    required_items = data.get("required_items") or meta.get("required_items") or []
    if isinstance(required_items, list) and required_items:
        first_required = dict(required_items[0] or {})
        if not data.get("target_item"):
            target_item = (
                first_required.get("id")
                or first_required.get("item_id")
                or first_required.get("name")
            )
            if target_item:
                data["target_item"] = str(target_item).strip().lower().replace(" ", "_")
        if data.get("required_qty") is None:
            required_qty = first_required.get("qty", first_required.get("quantity", 1))
            try:
                data["required_qty"] = max(1, int(required_qty))
            except (TypeError, ValueError):
                data["required_qty"] = 1
    rewards = data.get("rewards")
    if not isinstance(rewards, dict):
        rewards = {}
    if data.get("reward_gold") is None and rewards.get("gold") is not None:
        data["reward_gold"] = int(rewards["gold"])
    if data.get("reward_xp") is None and rewards.get("xp") is not None:
        data["reward_xp"] = int(rewards["xp"])
    if not data.get("giver_entity_id") and meta.get("giver_entity_id"):
        data["giver_entity_id"] = meta.get("giver_entity_id")
    if not data.get("giver_name") and meta.get("giver_name"):
        data["giver_name"] = meta.get("giver_name")
    data["source"] = canonical_offer_source(data.get("source"), default_source)
    return data


def normalize_quest_offers(
    offers: Optional[List[Dict[str, Any]]],
    default_source: str = "authored",
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen_ids = set()
    for offer in offers or []:
        normalized_offer = normalize_quest_offer(offer, default_source=default_source)
        offer_id = normalized_offer["id"]
        if offer_id in seen_ids:
            continue
        normalized.append(normalized_offer)
        seen_ids.add(offer_id)
    return normalized


def merge_quest_offers(
    existing: Optional[List[Dict[str, Any]]],
    new_offers: Optional[List[Dict[str, Any]]],
    new_default_source: str = "emergent",
) -> List[Dict[str, Any]]:
    merged = normalize_quest_offers(existing, default_source="authored")
    seen_ids = {offer["id"] for offer in merged}
    for offer in normalize_quest_offers(new_offers, default_source=new_default_source):
        if offer["id"] in seen_ids:
            continue
        merged.append(offer)
        seen_ids.add(offer["id"])
    return merged

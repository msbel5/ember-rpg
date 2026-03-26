"""Centralized data loader — all game content from JSON files, no hardcoded data.

Every class, item, enemy, NPC template, spell, and recipe is loaded from
frp-backend/data/*.json at module import time.  Game code should import
from here instead of hardcoding dictionaries.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(filename: str) -> Any:
    """Load a JSON file from the data directory."""
    path = _DATA_DIR / filename
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Classes ──────────────────────────────────────────────────────────
CLASSES: Dict[str, Dict[str, Any]] = _load_json("classes.json")


def get_class(class_id: str) -> Dict[str, Any]:
    """Get class definition by ID. Returns empty dict if not found."""
    return CLASSES.get(class_id, {})


def get_class_ap(class_id: str) -> int:
    """Get AP per turn for a class."""
    return get_class(class_id).get("ap_per_turn", 4)


def get_class_hit_die_size(class_id: str) -> int:
    """Get hit die size for a class."""
    return get_class(class_id).get("hit_die_size", 8)


def get_class_starting_equipment(class_id: str) -> List[Dict[str, Any]]:
    """Get starting equipment for a class."""
    return get_class(class_id).get("starting_equipment", [])


def get_class_starting_gold(class_id: str) -> int:
    """Get starting gold for a class."""
    return get_class(class_id).get("starting_gold", 50)


def get_class_armor_type(class_id: str) -> str:
    """Get default armor type for a class."""
    return get_class(class_id).get("armor_type", "none")


def get_class_ability_priority(class_id: str) -> List[str]:
    """Get ability score priority order for stat assignment."""
    return get_class(class_id).get("ability_priority", ["MIG", "AGI", "END", "MND", "INS", "PRE"])


def get_class_skill_pool(class_id: str) -> List[str]:
    """Get available skill proficiency choices for a class."""
    return get_class(class_id).get("skill_pool", [])


def get_class_skill_pick_count(class_id: str) -> int:
    """Get how many skills a class picks at creation."""
    return get_class(class_id).get("skill_pick_count", 2)


def get_class_default_skills(class_id: str) -> List[str]:
    """Get default skill proficiencies if player doesn't choose."""
    return get_class(class_id).get("default_skills", [])


def list_class_ids() -> List[str]:
    """Return all available class IDs."""
    return list(CLASSES.keys())


# ── AP mapping (used by action_points.py) ────────────────────────────
def get_class_ap_map() -> Dict[str, int]:
    """Return {class_id: ap_per_turn} for all classes."""
    return {cid: cdata.get("ap_per_turn", 4) for cid, cdata in CLASSES.items()}


# ── Items ────────────────────────────────────────────────────────────
ITEMS: Dict[str, Dict[str, Any]] = _load_json("items.json")


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    """Get item definition by ID."""
    if isinstance(ITEMS, list):
        return next((i for i in ITEMS if i.get("id") == item_id), None)
    return ITEMS.get(item_id)


# ── Monsters ─────────────────────────────────────────────────────────
MONSTERS: Dict[str, Dict[str, Any]] = _load_json("monsters.json")


def get_monster(monster_id: str) -> Optional[Dict[str, Any]]:
    """Get monster definition by ID."""
    if isinstance(MONSTERS, list):
        return next((m for m in MONSTERS if m.get("id") == monster_id), None)
    return MONSTERS.get(monster_id)


# ── NPC Templates ────────────────────────────────────────────────────
NPC_TEMPLATES: Dict[str, Dict[str, Any]] = _load_json("npc_templates.json")

# ── Spells ───────────────────────────────────────────────────────────
SPELLS: Dict[str, Dict[str, Any]] = _load_json("spells.json")

# ── Campaign Templates ───────────────────────────────────────────────
CAMPAIGN_TEMPLATES: Dict[str, Dict[str, Any]] = _load_json("campaign_templates.json")

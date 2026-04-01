"""Data-driven inventory layouts and defaults."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from engine.data._shared import load_json_path
from engine.world.matter_state import MatterState

from .inventory_types import ItemShape, StashTier

_LAYOUTS_PATH = Path(__file__).resolve().parents[2] / "data" / "inventory_layouts.json"


@lru_cache(maxsize=1)
def _load_layouts() -> Dict[str, Any]:
    return dict(load_json_path(_LAYOUTS_PATH))


def _shape_map() -> Dict[str, ItemShape]:
    raw_shapes = _load_layouts().get("shapes", {})
    return {name: ItemShape.from_dict(payload) for name, payload in raw_shapes.items()}


SHAPES: Dict[str, ItemShape] = _shape_map()
ITEM_TYPE_SHAPES: Dict[str, str] = dict(_load_layouts().get("item_type_shapes", {}))
DEFAULT_EQUIPMENT_SLOTS: Dict[str, None] = {
    slot: None for slot in _load_layouts().get("default_equipment_slots", [])
}


def container_kwargs(spec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "container_id": spec["container_id"],
        "rows": spec["rows"],
        "cols": spec["cols"],
        "max_weight": spec.get("max_weight", 999.0),
        "accepted_states": [MatterState(state) for state in spec.get("accepted_states", ["solid"])],
        "sealed": spec.get("sealed", False),
        "liquid_capacity_ml": spec.get("liquid_capacity_ml", 0),
        "current_liquid": deepcopy(spec.get("current_liquid")),
    }


def default_backpack_kwargs() -> Dict[str, Any]:
    return container_kwargs(deepcopy(_load_layouts()["default_containers"]["backpack"]))


def default_belt_kwargs() -> Dict[str, Any]:
    return container_kwargs(deepcopy(_load_layouts()["default_containers"]["belt"]))


def default_pocket_specs() -> list[Dict[str, Any]]:
    return deepcopy(_load_layouts()["default_containers"]["pockets"])


def default_hidden_stash_specs() -> Dict[str, Dict[str, Any]]:
    return deepcopy(_load_layouts()["default_containers"]["hidden_stashes"])


def default_stash_tiers() -> Dict[str, StashTier]:
    return {
        stash_id: StashTier[spec.get("tier", "SIMPLE")]
        for stash_id, spec in default_hidden_stash_specs().items()
    }


def get_item_shape(item_data: Dict[str, Any]) -> ItemShape:
    if "item_shape" in item_data:
        return ItemShape.from_dict(item_data["item_shape"])
    shape_name = item_data.get("shape_name")
    if shape_name and shape_name in SHAPES:
        return SHAPES[shape_name]
    item_type = item_data.get("type", "default")
    armor_type = item_data.get("armor_type", "")
    if item_type == "weapon":
        damage = item_data.get("damage", 0) or 0
        if damage <= 4:
            return SHAPES["small_h"]
        if damage <= 7:
            return SHAPES["medium_h"]
        return SHAPES["long"]
    if item_type == "armor":
        if armor_type == "heavy" or (item_data.get("ac_bonus", 0) or 0) >= 5:
            return SHAPES["large"]
        return SHAPES["square_2x2"]
    type_key = f"{item_type}_{armor_type}" if armor_type else item_type
    shape_name = ITEM_TYPE_SHAPES.get(type_key, ITEM_TYPE_SHAPES.get(item_type, "tiny"))
    return SHAPES.get(shape_name, SHAPES["tiny"])

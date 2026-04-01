"""Creation catalog builders shared by API routes and UI clients."""
from __future__ import annotations

import copy
from functools import lru_cache
from typing import Any

from engine.data_loader import (
    get_creation_ability_order,
    get_creation_allocation_rules,
    get_creation_default_adapter,
    get_creation_default_class,
    get_creation_default_profile,
    get_creation_faction_labels,
    get_creation_genesis_defaults,
    get_creation_settlement_labels,
    list_classes,
)
from engine.worldgen.registries import load_adapter_ids, load_adapter_pack, load_world_profiles


MECHANICS_VERSION = "ember_hybrid_v1"


def _label_from_id(raw_id: str) -> str:
    parts = [part for part in str(raw_id).replace("-", "_").split("_") if part]
    return " ".join(part.capitalize() for part in parts) if parts else str(raw_id)


def _adapter_catalog_entry(adapter_id: str) -> dict[str, Any]:
    adapter = dict(load_adapter_pack(adapter_id))
    starter_content = dict(adapter.get("starter_content", {}))
    species_labels = dict(adapter.get("species_labels", {}))
    allowed_species = list(adapter.get("allowed_species", []))
    return {
        "id": str(adapter_id),
        "label": str(adapter.get("title") or adapter.get("name") or _label_from_id(adapter_id)),
        "allowed_species": allowed_species,
        "species_labels": species_labels,
        "default_player_class": str(starter_content.get("default_player_class", get_creation_default_class())),
        "starting_focus": str(starter_content.get("starting_focus", "")),
    }


@lru_cache(maxsize=1)
def build_class_catalog() -> tuple[dict[str, Any], ...]:
    entries: list[dict[str, Any]] = []
    for class_data in list_classes():
        class_id = str(class_data.get("id", "")).lower()
        if not class_id:
            continue
        entries.append(
            {
                "id": class_id,
                "label": str(class_data.get("name") or _label_from_id(class_id)),
                "description": str(class_data.get("description", "")),
                "ability_priority": list(class_data.get("ability_priority", [])),
                "skill_pool": list(class_data.get("skill_pool", [])),
                "default_skills": list(class_data.get("default_skills", [])),
                "skill_pick_count": int(class_data.get("skill_pick_count", 0)),
                "ap_per_turn": int(class_data.get("ap_per_turn", 0)),
                "hit_die_size": int(class_data.get("hit_die_size", 0)),
                "armor_type": str(class_data.get("armor_type", "")),
            }
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def build_adapter_catalog() -> tuple[dict[str, Any], ...]:
    return tuple(_adapter_catalog_entry(adapter_id) for adapter_id in load_adapter_ids())


@lru_cache(maxsize=1)
def build_profile_catalog() -> tuple[dict[str, Any], ...]:
    entries: list[dict[str, Any]] = []
    for profile_id, profile in load_world_profiles().items():
        entries.append(
            {
                "id": str(profile_id),
                "label": str(profile.get("title") or _label_from_id(profile_id)),
                "world_width": int(profile.get("world_width", 0)),
                "world_height": int(profile.get("world_height", 0)),
                "history_end_year": int(profile.get("history_end_year", 0)),
            }
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def build_creation_catalog() -> dict[str, Any]:
    return {
        "mechanics_version": MECHANICS_VERSION,
        "default_class_id": get_creation_default_class(),
        "default_adapter_id": get_creation_default_adapter(),
        "default_profile_id": get_creation_default_profile(),
        "ability_order": list(get_creation_ability_order()),
        "allocation_rules": dict(get_creation_allocation_rules()),
        "settlement_labels": dict(get_creation_settlement_labels()),
        "faction_labels": dict(get_creation_faction_labels()),
        "genesis_defaults": dict(get_creation_genesis_defaults()),
        "class_catalog": [dict(entry) for entry in build_class_catalog()],
        "adapter_catalog": [dict(entry) for entry in build_adapter_catalog()],
        "profile_catalog": [dict(entry) for entry in build_profile_catalog()],
    }


def get_creation_catalog() -> dict[str, Any]:
    return copy.deepcopy(build_creation_catalog())


def get_creation_class_entry(class_id: str) -> dict[str, Any]:
    normalized = str(class_id or "").lower()
    for entry in build_class_catalog():
        if str(entry.get("id", "")) == normalized:
            return dict(entry)
    return {}


def get_creation_adapter_entry(adapter_id: str) -> dict[str, Any]:
    normalized = str(adapter_id or "").strip()
    for entry in build_adapter_catalog():
        if str(entry.get("id", "")) == normalized:
            return dict(entry)
    return {}

"""Shared registry loading helpers for gameplay data."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_json_path(path_like: str | Path) -> Any:
    """Load arbitrary JSON from a path, resolving relative paths safely."""
    path = Path(path_like)
    if not path.exists():
        candidates = [
            _DATA_DIR / path.name,
            _DATA_DIR.parent / path_like,
            Path(__file__).resolve().parents[3] / path_like,
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=None)
def _load_json(filename: str) -> Any:
    path = _DATA_DIR / filename
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _unwrap(raw: Any, collection_key: Optional[str] = None) -> Any:
    if collection_key and isinstance(raw, dict) and collection_key in raw:
        return raw[collection_key]
    return raw


def _normalize_list(raw: Any, collection_key: Optional[str] = None) -> List[Any]:
    data = _unwrap(raw, collection_key)
    if data is None:
        return []
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict):
        return list(data.values())
    return []


def _normalize_map(raw: Any, collection_key: Optional[str] = None, id_field: str = "id") -> Dict[str, Dict[str, Any]]:
    data = _unwrap(raw, collection_key)
    if data is None:
        return {}
    if isinstance(data, dict):
        if all(isinstance(value, dict) for value in data.values()):
            if all(id_field in value or str(key) == str(value.get(id_field, key)) for key, value in data.items()):
                normalized: Dict[str, Dict[str, Any]] = {}
                for key, value in data.items():
                    item = dict(value)
                    item.setdefault(id_field, key)
                    normalized[str(item[id_field])] = item
                return normalized
        return {str(key): dict(value) if isinstance(value, dict) else {"value": value} for key, value in data.items()}
    if isinstance(data, list):
        normalized = {}
        for value in data:
            if not isinstance(value, dict):
                continue
            item_id = value.get(id_field)
            if item_id is None:
                continue
            normalized[str(item_id)] = dict(value)
        return normalized
    return {}


def load_registry_map(filename: str, collection_key: Optional[str] = None, id_field: str = "id") -> Dict[str, Dict[str, Any]]:
    return _normalize_map(_load_json(filename), collection_key=collection_key, id_field=id_field)


def load_registry_list(filename: str, collection_key: Optional[str] = None) -> List[Any]:
    return _normalize_list(_load_json(filename), collection_key=collection_key)


def load_registry_map_from_path(path_like: str | Path, collection_key: Optional[str] = None, id_field: str = "id") -> Dict[str, Dict[str, Any]]:
    return _normalize_map(load_json_path(path_like), collection_key=collection_key, id_field=id_field)


def load_registry_list_from_path(path_like: str | Path, collection_key: Optional[str] = None) -> List[Any]:
    return _normalize_list(load_json_path(path_like), collection_key=collection_key)


def _normalize_lowercase_ids(registry: Dict[str, Dict[str, Any]], *, id_field: str = "id") -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for key, value in registry.items():
        item = dict(value)
        item_id = str(item.get(id_field, key) or "").strip().lower()
        if not item_id:
            continue
        item[id_field] = item_id
        normalized[item_id] = item
    return normalized


def classes_registry() -> Dict[str, Dict[str, Any]]:
    return _normalize_lowercase_ids(load_registry_map("classes.json", "classes", id_field="id"), id_field="id")


def items_registry() -> Dict[str, Dict[str, Any]]:
    return load_registry_map("items.json", "items")


def monsters_registry() -> Dict[str, Dict[str, Any]]:
    return load_registry_map("monsters.json", "monsters")


def npc_templates_registry() -> Dict[str, Dict[str, Any]]:
    return load_registry_map("npc_templates.json", "npc_templates")


def spells_registry() -> Dict[str, Dict[str, Any]]:
    return load_registry_map("spells.json", "spells")


def campaign_templates_registry() -> Dict[str, Dict[str, Any]]:
    return load_registry_map("campaign_templates.json", "campaign_templates")


def recipes_registry() -> Dict[str, Dict[str, Any]]:
    return load_registry_map("recipes.json", "recipes")


def locations_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("locations.json"), "locations") or {}


def worldgen_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("worldgen.json"), "worldgen") or {}


def social_rules_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("social_rules.json"), "social_rules") or {}


def progression_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("progression.json"), "progression") or {}


def loot_tables_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("loot_tables.json"), "loot_tables") or {}


def name_banks_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("name_banks.json"), "name_banks") or {}


def schedules_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("schedules.json"), "schedules") or {}


def creation_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("character_creation.json"), "character_creation") or {}


def consequence_rules_registry() -> List[Dict[str, Any]]:
    return _normalize_list(_load_json("consequence_rules.json"), "consequence_rules")


def campaign_runtime_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("campaign_runtime.json"), "campaign_runtime") or {}


def history_tables_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("history_tables.json"), "history_tables") or {}


def runtime_config_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("runtime_config.json"), "runtime_config") or {}


def dialog_defs_registry() -> Dict[str, Dict[str, Any]]:
    return load_registry_map("dialog_defs.json", "dialog_defs", id_field="dialog_id")


def caravans_registry() -> Dict[str, Dict[str, Any]]:
    return load_registry_map("caravans.json", "caravans")


def factions_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("factions.json"), "factions") or {}


def colony_config_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("colony_config.json"), "colony_config") or {}


def economy_config_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("economy_config.json"), "economy_config") or {}


def quest_config_registry() -> Dict[str, Any]:
    return _unwrap(_load_json("quest_config.json"), "quest_config") or {}


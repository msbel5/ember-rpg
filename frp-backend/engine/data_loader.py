"""Centralized data loader for runtime content/config registries.

All gameplay content under ``frp-backend/data`` should be read through this
module. Callers get normalized list/map access regardless of whether the
source file stores a wrapped object, wrapped list, or direct id->object map.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_json_path(path_like: str | Path) -> Any:
    """Load arbitrary JSON from a path, resolving relative paths safely."""
    path = Path(path_like)
    if not path.exists():
        candidates = [
            _DATA_DIR / path.name,
            _DATA_DIR.parent / path_like,
            Path(__file__).resolve().parents[2] / path_like,
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


# Core registries
CLASSES = load_registry_map("classes.json", "classes", id_field="id")
ITEMS = load_registry_map("items.json", "items")
MONSTERS = load_registry_map("monsters.json", "monsters")
NPC_TEMPLATES = load_registry_map("npc_templates.json", "npc_templates")
SPELLS = load_registry_map("spells.json", "spells")
CAMPAIGN_TEMPLATES = load_registry_map("campaign_templates.json", "campaign_templates")
RECIPES = load_registry_map("recipes.json", "recipes")
LOCATIONS = _unwrap(_load_json("locations.json"), "locations") or {}
WORLDGEN = _unwrap(_load_json("worldgen.json"), "worldgen") or {}
SOCIAL_RULES = _unwrap(_load_json("social_rules.json"), "social_rules") or {}
PROGRESSION = _unwrap(_load_json("progression.json"), "progression") or {}
LOOT_TABLES = _unwrap(_load_json("loot_tables.json"), "loot_tables") or {}
NAME_BANKS = _unwrap(_load_json("name_banks.json"), "name_banks") or {}
SCHEDULES = _unwrap(_load_json("schedules.json"), "schedules") or {}
CHARACTER_CREATION = _unwrap(_load_json("character_creation.json"), "character_creation") or {}


# Classes
def get_class(class_id: str) -> Dict[str, Any]:
    return dict(CLASSES.get(str(class_id or "").lower(), {}))


def list_classes() -> List[Dict[str, Any]]:
    return [dict(item) for item in CLASSES.values()]


def list_class_ids() -> List[str]:
    return list(CLASSES.keys())


def get_class_ap(class_id: str) -> int:
    return int(get_class(class_id).get("ap_per_turn", 4))


def get_class_ap_map() -> Dict[str, int]:
    return {class_id: int(data.get("ap_per_turn", 4)) for class_id, data in CLASSES.items()}


def get_class_hit_die_size(class_id: str) -> int:
    return int(get_class(class_id).get("hit_die_size", 8))


def get_class_starting_equipment(class_id: str) -> List[Dict[str, Any]]:
    return [dict(item) for item in get_class(class_id).get("starting_equipment", [])]


def get_class_starting_gold(class_id: str) -> int:
    return int(get_class(class_id).get("starting_gold", 50))


def get_class_armor_type(class_id: str) -> str:
    return str(get_class(class_id).get("armor_type", "none"))


def get_class_ability_priority(class_id: str) -> List[str]:
    return list(get_class(class_id).get("ability_priority", ["MIG", "AGI", "END", "MND", "INS", "PRE"]))


def get_class_skill_pool(class_id: str) -> List[str]:
    return list(get_class(class_id).get("skill_pool", []))


def get_class_skill_pick_count(class_id: str) -> int:
    return int(get_class(class_id).get("skill_pick_count", 2))


def get_class_default_skills(class_id: str) -> List[str]:
    return list(get_class(class_id).get("default_skills", []))


def get_class_default_stats(class_id: str) -> Dict[str, int]:
    return {
        str(key): int(value)
        for key, value in get_class(class_id).get("default_stats", {}).items()
    }


def get_class_default_hp(class_id: str) -> int:
    return int(get_class(class_id).get("default_hp", 16))


def get_class_default_spell_points(class_id: str) -> int:
    return int(get_class(class_id).get("default_spell_points", 0))


# Generic id registries
def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    item = ITEMS.get(str(item_id or ""))
    return dict(item) if item else None


def list_items() -> List[Dict[str, Any]]:
    return [dict(item) for item in ITEMS.values()]


def get_monster(monster_id: str) -> Optional[Dict[str, Any]]:
    monster = MONSTERS.get(str(monster_id or ""))
    return dict(monster) if monster else None


def list_monsters() -> List[Dict[str, Any]]:
    return [dict(monster) for monster in MONSTERS.values()]


def get_npc_template(template_id: str) -> Optional[Dict[str, Any]]:
    npc = NPC_TEMPLATES.get(str(template_id or ""))
    return dict(npc) if npc else None


def list_npc_templates() -> List[Dict[str, Any]]:
    return [dict(template) for template in NPC_TEMPLATES.values()]


def get_spell(spell_id_or_name: str) -> Optional[Dict[str, Any]]:
    query = str(spell_id_or_name or "").lower()
    if not query:
        return None
    for spell in SPELLS.values():
        if query == str(spell.get("id", "")).lower() or query == str(spell.get("name", "")).lower():
            return dict(spell)
    return None


def list_spells() -> List[Dict[str, Any]]:
    return [dict(spell) for spell in SPELLS.values()]


def get_recipe(recipe_id: str) -> Optional[Dict[str, Any]]:
    recipe = RECIPES.get(str(recipe_id or ""))
    return dict(recipe) if recipe else None


def list_recipes() -> List[Dict[str, Any]]:
    return [dict(recipe) for recipe in RECIPES.values()]


def recipes_by_skill(skill: str) -> List[Dict[str, Any]]:
    skill_lower = str(skill or "").lower()
    return [dict(recipe) for recipe in RECIPES.values() if str(recipe.get("skill", "")).lower() == skill_lower]


# Location / worldgen registries
def get_opening_scenes() -> List[Dict[str, Any]]:
    return [dict(scene) for scene in LOCATIONS.get("opening_scenes", [])]


def get_scene_anchor_offsets() -> Dict[str, List[int]]:
    return {name: list(offset) for name, offset in LOCATIONS.get("scene_anchor_offsets", {}).items()}


def get_scene_role_sets() -> Dict[str, List[Dict[str, Any]]]:
    return {name: [dict(entry) for entry in entries] for name, entries in LOCATIONS.get("scene_role_sets", {}).items()}


def get_role_anchor_map() -> Dict[str, str]:
    return dict(LOCATIONS.get("role_anchor_map", {}))


def get_npc_visuals() -> Dict[str, List[str]]:
    return {role: list(spec) for role, spec in LOCATIONS.get("npc_visuals", {}).items()}


def get_workstation_specs() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in LOCATIONS.get("workstation_specs", {}).items()}


def get_workstation_anchors() -> Dict[str, str]:
    return dict(LOCATIONS.get("workstation_anchors", {}))


def get_role_production_map() -> Dict[str, List[str]]:
    return {role: list(values) for role, values in LOCATIONS.get("role_production", {}).items()}


def get_role_skill_profiles() -> Dict[str, Dict[str, int]]:
    return {role: dict(profile) for role, profile in LOCATIONS.get("role_skill_profiles", {}).items()}


def get_role_stats() -> Dict[str, Dict[str, Any]]:
    return {role: dict(stats) for role, stats in LOCATIONS.get("role_stats", {}).items()}


def get_town_building_types() -> List[str]:
    return list(WORLDGEN.get("town_building_types", []))


def get_zone_tile_palettes() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in WORLDGEN.get("zone_tile_palettes", {}).items()}


def get_building_templates() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in WORLDGEN.get("building_templates", {}).items()}


def get_map_generator_tile_sets() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in WORLDGEN.get("map_generator_tile_sets", {}).items()}


def get_map_generator_room_templates() -> Dict[str, List[Dict[str, Any]]]:
    return {key: [dict(value) for value in values] for key, values in WORLDGEN.get("map_generator_room_templates", {}).items()}


def get_entity_templates_by_location() -> Dict[str, Dict[str, Any]]:
    return dict(WORLDGEN.get("entity_templates_by_location", {}))


def get_zone_entity_rules() -> Dict[str, Dict[str, List[str]]]:
    return {
        key: {
            "npcs": list(value.get("npcs", [])),
            "items": list(value.get("items", [])),
            "enemies": list(value.get("enemies", [])),
        }
        for key, value in WORLDGEN.get("zone_entity_rules", {}).items()
    }


def get_zone_layouts() -> Dict[str, List[Dict[str, Any]]]:
    return {
        key: [dict(value) for value in values]
        for key, values in WORLDGEN.get("zone_layouts", {}).items()
    }


def get_scene_system_prompt() -> str:
    return str(WORLDGEN.get("scene_narration", {}).get("system_prompt", ""))


def get_scene_fallback_narratives() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in WORLDGEN.get("scene_narration", {}).get("fallback_narratives", {}).items()
    }


def get_location_npc_templates() -> Dict[str, List[str]]:
    return {
        key: list(value)
        for key, value in get_entity_templates_by_location().get("npcs", {}).items()
    }


def get_location_item_templates() -> Dict[str, List[str]]:
    return {
        key: list(value)
        for key, value in get_entity_templates_by_location().get("items", {}).items()
    }


def get_location_enemy_templates() -> Dict[str, List[str]]:
    return {
        key: list(value)
        for key, value in get_entity_templates_by_location().get("enemies", {}).items()
    }


def get_context_actions() -> Dict[str, Dict[str, List[str]]]:
    return {
        bucket: {key: list(value) for key, value in entries.items()}
        for bucket, entries in get_entity_templates_by_location().get("context_actions", {}).items()
    }


# Social rules
def get_social_attitude_dcs() -> Dict[str, Dict[str, int]]:
    return {key: dict(value) for key, value in SOCIAL_RULES.get("attitude_dcs", {}).items()}


def get_default_npc_attitude_map() -> Dict[str, str]:
    return dict(SOCIAL_RULES.get("default_npc_attitude", {}))


def get_default_npc_alignment_map() -> Dict[str, str]:
    return dict(SOCIAL_RULES.get("default_npc_alignment", {}))


def get_think_topic_skills() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in SOCIAL_RULES.get("think_topic_skills", {}).items()}


def get_hostile_keywords() -> List[str]:
    return list(SOCIAL_RULES.get("hostile_keywords", []))


# Progression / loot / names / schedules
def get_xp_thresholds() -> List[int]:
    return list(PROGRESSION.get("xp_thresholds", []))


def get_hp_per_level() -> Dict[str, int]:
    return {key: int(value) for key, value in PROGRESSION.get("hp_per_level", {}).items()}


def get_sp_per_level() -> Dict[str, int]:
    return {key: int(value) for key, value in PROGRESSION.get("sp_per_level", {}).items()}


def get_stat_bonus_by_class() -> Dict[str, str]:
    return {str(key): str(value) for key, value in PROGRESSION.get("stat_bonus_by_class", {}).items()}


def get_class_abilities() -> Dict[str, List[Dict[str, Any]]]:
    return {key: [dict(value) for value in values] for key, values in PROGRESSION.get("class_abilities", {}).items()}


def get_xp_rewards() -> Dict[int, int]:
    return {int(key): int(value) for key, value in PROGRESSION.get("xp_rewards", {}).items()}


def get_loot_rarity_drop_chances() -> Dict[str, float]:
    return {key: float(value) for key, value in LOOT_TABLES.get("rarity_drop_chances", {}).items()}


def get_loot_rarity_order() -> List[str]:
    return list(LOOT_TABLES.get("rarity_order", []))


def get_base_drop_chance() -> float:
    return float(LOOT_TABLES.get("base_drop_chance", 0.4))


def get_name_banks() -> Dict[str, Dict[str, List[str]]]:
    return {key: dict(value) for key, value in NAME_BANKS.items()}


def get_default_schedules() -> Dict[str, Dict[str, str]]:
    return {key: dict(value) for key, value in SCHEDULES.get("default_schedules", {}).items()}


# Character creation
def get_creation_ability_order() -> List[str]:
    return list(CHARACTER_CREATION.get("ability_order", []))


def get_creation_class_skill_options() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in CHARACTER_CREATION.get("class_skill_options", {}).items()}


def get_creation_class_skill_counts() -> Dict[str, int]:
    return {str(key): int(value) for key, value in CHARACTER_CREATION.get("class_skill_counts", {}).items()}


def get_creation_class_default_skills() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in CHARACTER_CREATION.get("class_default_skills", {}).items()}


def get_creation_class_stat_priorities() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in CHARACTER_CREATION.get("class_stat_priorities", {}).items()}


def get_creation_questions() -> List[Dict[str, Any]]:
    return [dict(question) for question in CHARACTER_CREATION.get("questions", [])]

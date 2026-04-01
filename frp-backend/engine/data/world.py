"""World, location, social, naming, and schedule data accessors."""
from __future__ import annotations

from typing import Any, Dict, List

from engine.data._shared import (
    locations_registry,
    name_banks_registry,
    schedules_registry,
    social_rules_registry,
    worldgen_registry,
)


def get_opening_scenes() -> List[Dict[str, Any]]:
    return [dict(scene) for scene in locations_registry().get("opening_scenes", [])]


def get_default_opening_scene() -> Dict[str, Any]:
    return dict(locations_registry().get("default_opening_scene", {}))


def get_location_stock_baseline() -> Dict[str, int]:
    return {
        str(item_id): int(quantity)
        for item_id, quantity in locations_registry().get("location_stock_baseline", {}).items()
    }


def get_scene_anchor_offsets() -> Dict[str, List[int]]:
    return {name: list(offset) for name, offset in locations_registry().get("scene_anchor_offsets", {}).items()}


def get_scene_role_sets() -> Dict[str, List[Dict[str, Any]]]:
    return {name: [dict(entry) for entry in entries] for name, entries in locations_registry().get("scene_role_sets", {}).items()}


def get_role_anchor_map() -> Dict[str, str]:
    return dict(locations_registry().get("role_anchor_map", {}))


def get_npc_visuals() -> Dict[str, List[str]]:
    return {role: list(spec) for role, spec in locations_registry().get("npc_visuals", {}).items()}


def get_workstation_specs() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in locations_registry().get("workstation_specs", {}).items()}


def get_workstation_anchors() -> Dict[str, str]:
    return dict(locations_registry().get("workstation_anchors", {}))


def get_role_production_map() -> Dict[str, List[str]]:
    return {role: list(values) for role, values in locations_registry().get("role_production", {}).items()}


def get_role_skill_profiles() -> Dict[str, Dict[str, int]]:
    return {role: dict(profile) for role, profile in locations_registry().get("role_skill_profiles", {}).items()}


def get_role_stats() -> Dict[str, Dict[str, Any]]:
    return {role: dict(stats) for role, stats in locations_registry().get("role_stats", {}).items()}


def get_town_building_types() -> List[str]:
    return list(worldgen_registry().get("town_building_types", []))


def get_zone_tile_palettes() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in worldgen_registry().get("zone_tile_palettes", {}).items()}


def get_building_templates() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in worldgen_registry().get("building_templates", {}).items()}


def get_map_generator_tile_sets() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in worldgen_registry().get("map_generator_tile_sets", {}).items()}


def get_map_generator_room_templates() -> Dict[str, List[Dict[str, Any]]]:
    return {key: [dict(value) for value in values] for key, values in worldgen_registry().get("map_generator_room_templates", {}).items()}


def get_entity_templates_by_location() -> Dict[str, Dict[str, Any]]:
    return dict(worldgen_registry().get("entity_templates_by_location", {}))


def get_zone_entity_rules() -> Dict[str, Dict[str, List[str]]]:
    return {
        key: {
            "npcs": list(value.get("npcs", [])),
            "items": list(value.get("items", [])),
            "enemies": list(value.get("enemies", [])),
        }
        for key, value in worldgen_registry().get("zone_entity_rules", {}).items()
    }


def get_zone_layouts() -> Dict[str, List[Dict[str, Any]]]:
    return {
        key: [dict(value) for value in values]
        for key, values in worldgen_registry().get("zone_layouts", {}).items()
    }


def get_scene_system_prompt() -> str:
    return str(worldgen_registry().get("scene_narration", {}).get("system_prompt", ""))


def get_scene_fallback_narratives() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in worldgen_registry().get("scene_narration", {}).get("fallback_narratives", {}).items()
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


def get_social_attitude_dcs() -> Dict[str, Dict[str, int]]:
    return {key: dict(value) for key, value in social_rules_registry().get("attitude_dcs", {}).items()}


def get_default_npc_attitude_map() -> Dict[str, str]:
    return dict(social_rules_registry().get("default_npc_attitude", {}))


def get_default_npc_alignment_map() -> Dict[str, str]:
    return dict(social_rules_registry().get("default_npc_alignment", {}))


def get_think_topic_skills() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in social_rules_registry().get("think_topic_skills", {}).items()}


def get_hostile_keywords() -> List[str]:
    return list(social_rules_registry().get("hostile_keywords", []))


def get_interaction_hold_turns() -> Dict[str, int]:
    return {
        str(action): int(turns)
        for action, turns in social_rules_registry().get("interaction_hold_turns", {}).items()
    }


def get_name_banks() -> Dict[str, Dict[str, List[str]]]:
    return {key: dict(value) for key, value in name_banks_registry().items()}


def get_default_schedules() -> Dict[str, Dict[str, str]]:
    return {key: dict(value) for key, value in schedules_registry().get("default_schedules", {}).items()}


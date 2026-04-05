"""Progression, runtime configuration, and campaign-history accessors."""
from __future__ import annotations

from typing import Any, Dict, List

from engine.data._shared import (
    campaign_runtime_registry,
    consequence_rules_registry,
    history_tables_registry,
    loot_tables_registry,
    progression_registry,
    runtime_config_registry,
)


def _normalize_class_key(class_id: Any) -> str:
    return str(class_id or "").strip().lower()


def _normalize_class_value_map(raw: Dict[str, Any], caster) -> Dict[str, Any]:
    return {_normalize_class_key(key): caster(value) for key, value in raw.items()}


def get_xp_thresholds() -> List[int]:
    return list(progression_registry().get("xp_thresholds", []))


def get_hp_per_level() -> Dict[str, int]:
    return _normalize_class_value_map(progression_registry().get("hp_per_level", {}), int)


def get_sp_per_level() -> Dict[str, int]:
    return _normalize_class_value_map(progression_registry().get("sp_per_level", {}), int)


def get_stat_bonus_by_class() -> Dict[str, str]:
    return _normalize_class_value_map(progression_registry().get("stat_bonus_by_class", {}), str)


def get_class_abilities() -> Dict[str, List[Dict[str, Any]]]:
    abilities: Dict[str, List[Dict[str, Any]]] = {}
    for key, values in progression_registry().get("class_abilities", {}).items():
        class_id = _normalize_class_key(key)
        abilities[class_id] = []
        for value in values:
            entry = dict(value)
            if "class_name" in entry:
                entry["class_name"] = _normalize_class_key(entry.get("class_name"))
            abilities[class_id].append(entry)
    return abilities


def get_xp_rewards() -> Dict[int, int]:
    return {int(key): int(value) for key, value in progression_registry().get("xp_rewards", {}).items()}


def get_loot_rarity_drop_chances() -> Dict[str, float]:
    return {key: float(value) for key, value in loot_tables_registry().get("rarity_drop_chances", {}).items()}


def get_loot_rarity_order() -> List[str]:
    return list(loot_tables_registry().get("rarity_order", []))


def get_base_drop_chance() -> float:
    return float(loot_tables_registry().get("base_drop_chance", 0.4))


def get_consequence_rule_specs() -> List[Dict[str, Any]]:
    return [dict(rule) for rule in consequence_rules_registry()]


def get_campaign_arc_titles() -> List[str]:
    return list(campaign_runtime_registry().get("arc_titles", []))


def get_campaign_arc_premises() -> List[str]:
    return list(campaign_runtime_registry().get("arc_premises", []))


def get_campaign_kill_quests() -> List[Dict[str, Any]]:
    return [dict(entry) for entry in campaign_runtime_registry().get("kill_quests", [])]


def get_campaign_fetch_quests() -> List[Dict[str, Any]]:
    return [dict(entry) for entry in campaign_runtime_registry().get("fetch_quests", [])]


def get_campaign_explore_template() -> Dict[str, Any]:
    return dict(campaign_runtime_registry().get("explore_quest", {}))


def get_campaign_dialogue_template() -> Dict[str, Any]:
    return dict(campaign_runtime_registry().get("dialogue_quest", {}))


def get_campaign_world_events() -> List[Dict[str, Any]]:
    return [dict(entry) for entry in campaign_runtime_registry().get("world_events", [])]


def get_history_present_year() -> int:
    return int(history_tables_registry().get("present_year", 1000))


def get_history_all_factions() -> List[str]:
    return list(history_tables_registry().get("all_factions", []))


def get_history_scholarly_roles() -> List[str]:
    return list(history_tables_registry().get("scholarly_roles", []))


def get_history_severity_levels() -> List[str]:
    return list(history_tables_registry().get("severity_levels", []))


def get_history_table(table_name: str) -> List[str]:
    return list(history_tables_registry().get(str(table_name), []))


def get_runtime_config() -> Dict[str, Any]:
    return dict(runtime_config_registry())


def get_llm_runtime_config() -> Dict[str, Any]:
    return dict(runtime_config_registry().get("llm", {}))


def get_godot_runtime_config() -> Dict[str, Any]:
    return dict(runtime_config_registry().get("godot_client", {}))

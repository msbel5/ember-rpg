"""Class and creation-surface gameplay data accessors."""
from __future__ import annotations

from typing import Any, Dict, List

from engine.data._shared import classes_registry, creation_registry


def get_class(class_id: str) -> Dict[str, Any]:
    return dict(classes_registry().get(str(class_id or "").lower(), {}))


def _default_class_data() -> Dict[str, Any]:
    classes = classes_registry()
    creation = creation_registry()
    default_id = str(creation.get("default_class", "")).lower()
    if default_id and default_id in classes:
        return dict(classes[default_id])
    return dict(next(iter(classes.values()), {}))


def list_classes() -> List[Dict[str, Any]]:
    return [dict(item) for item in classes_registry().values()]


def list_class_ids() -> List[str]:
    return list(classes_registry().keys())


def get_class_ap(class_id: str) -> int:
    fallback = _default_class_data()
    return int(get_class(class_id).get("ap_per_turn", fallback.get("ap_per_turn", 0)))


def get_class_ap_map() -> Dict[str, int]:
    fallback = _default_class_data()
    return {
        class_id: int(data.get("ap_per_turn", fallback.get("ap_per_turn", 0)))
        for class_id, data in classes_registry().items()
    }


def get_class_hit_die_size(class_id: str) -> int:
    fallback = _default_class_data()
    return int(get_class(class_id).get("hit_die_size", fallback.get("hit_die_size", 0)))


def get_class_starting_equipment(class_id: str) -> List[Dict[str, Any]]:
    return [dict(item) for item in get_class(class_id).get("starting_equipment", [])]


def get_class_starting_gold(class_id: str) -> int:
    fallback = _default_class_data()
    return int(get_class(class_id).get("starting_gold", fallback.get("starting_gold", 0)))


def get_class_armor_type(class_id: str) -> str:
    fallback = _default_class_data()
    return str(get_class(class_id).get("armor_type", fallback.get("armor_type", "")))


def get_class_ability_priority(class_id: str) -> List[str]:
    fallback = _default_class_data()
    return list(get_class(class_id).get("ability_priority", fallback.get("ability_priority", [])))


def get_class_skill_pool(class_id: str) -> List[str]:
    return list(get_class(class_id).get("skill_pool", []))


def get_class_skill_pick_count(class_id: str) -> int:
    fallback = _default_class_data()
    return int(get_class(class_id).get("skill_pick_count", fallback.get("skill_pick_count", 0)))


def get_class_default_skills(class_id: str) -> List[str]:
    return list(get_class(class_id).get("default_skills", []))


def get_class_default_stats(class_id: str) -> Dict[str, int]:
    fallback = _default_class_data()
    return {
        str(key): int(value)
        for key, value in get_class(class_id).get("default_stats", fallback.get("default_stats", {})).items()
    }


def get_class_default_hp(class_id: str) -> int:
    fallback = _default_class_data()
    return int(get_class(class_id).get("default_hp", fallback.get("default_hp", 0)))


def get_class_default_spell_points(class_id: str) -> int:
    fallback = _default_class_data()
    return int(get_class(class_id).get("default_spell_points", fallback.get("default_spell_points", 0)))


def get_creation_default_class() -> str:
    return str(creation_registry().get("default_class", "warrior"))


def get_creation_default_adapter() -> str:
    return str(creation_registry().get("default_adapter", "fantasy_ember"))


def get_creation_default_profile() -> str:
    return str(creation_registry().get("default_profile", "standard"))


def get_creation_allocation_rules() -> Dict[str, Any]:
    return dict(creation_registry().get("allocation_rules", {}))


def get_creation_settlement_labels() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in creation_registry().get("settlement_labels", {}).items()
    }


def get_creation_faction_labels() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in creation_registry().get("faction_labels", {}).items()
    }


def get_creation_genesis_defaults() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in creation_registry().get("genesis_defaults", {}).items()
    }


def get_creation_genesis_templates() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in creation_registry().get("genesis_templates", {}).items()
    }


def get_creation_unknown_class_fallback() -> Dict[str, Any]:
    return dict(creation_registry().get("unknown_class_fallback", {}))


def get_creation_ability_order() -> List[str]:
    return list(creation_registry().get("ability_order", []))

def get_skill_stat_map() -> Dict[str, str]:
    """Return skill→governing-ability map from data (e.g. {'melee': 'MIG'})."""
    return {
        str(k): str(v)
        for k, v in creation_registry().get("skill_stat_map", {}).items()
    }


def get_creation_class_skill_options() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in creation_registry().get("class_skill_options", {}).items()}


def get_creation_class_skill_counts() -> Dict[str, int]:
    return {str(key): int(value) for key, value in creation_registry().get("class_skill_counts", {}).items()}


def get_creation_class_default_skills() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in creation_registry().get("class_default_skills", {}).items()}


def get_creation_class_stat_priorities() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in creation_registry().get("class_stat_priorities", {}).items()}


def get_creation_questions() -> List[Dict[str, Any]]:
    creation = creation_registry()
    if creation.get("question_groups") is not None:
        flattened: List[Dict[str, Any]] = []
        for group in creation.get("question_groups", []):
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("id", ""))
            for question in group.get("questions", []):
                if not isinstance(question, dict):
                    continue
                entry = dict(question)
                if group_id and not entry.get("group_id"):
                    entry["group_id"] = group_id
                flattened.append(entry)
        return flattened
    return [dict(question) for question in creation.get("questions", [])]


def get_creation_question_groups() -> List[Dict[str, Any]]:
    groups = creation_registry().get("question_groups", [])
    if not isinstance(groups, list):
        return []
    return [dict(group) for group in groups if isinstance(group, dict)]


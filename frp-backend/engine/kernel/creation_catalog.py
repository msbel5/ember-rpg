"""Static creation catalog helpers and stat-assignment utilities."""
from __future__ import annotations

import copy
import random
from functools import lru_cache
from typing import Any, Dict, List, Optional

from engine.data._shared import classes_registry, creation_registry
from engine.worldgen.registries import (
    load_adapter_ids,
    load_adapter_pack,
    load_world_profiles,
)

ABILITY_ORDER: List[str] = ["MIG", "AGI", "END", "MND", "INS", "PRE"]
MECHANICS_VERSION = "ember_hybrid_v1"
DEFAULT_CLASS_ID = "warrior"


def _creation_reg() -> Dict[str, Any]:
    """Return the cached character_creation registry dict."""
    return creation_registry()


def _default_class_id() -> str:
    return str(_creation_reg().get("default_class", "warrior"))


def _default_adapter_id() -> str:
    return str(_creation_reg().get("default_adapter", "fantasy_ember"))


def _default_profile_id() -> str:
    return str(_creation_reg().get("default_profile", "standard"))


def _class_stat_priorities() -> Dict[str, List[str]]:
    return {
        key: list(value)
        for key, value in _creation_reg().get("class_stat_priorities", {}).items()
    }


def _allocation_rules() -> Dict[str, Any]:
    return dict(_creation_reg().get("allocation_rules", {}))


def _settlement_labels() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in _creation_reg().get("settlement_labels", {}).items()
    }


def _faction_labels() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in _creation_reg().get("faction_labels", {}).items()
    }


def _genesis_defaults() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in _creation_reg().get("genesis_defaults", {}).items()
    }


def _genesis_templates() -> Dict[str, str]:
    return {
        str(key): str(value)
        for key, value in _creation_reg().get("genesis_templates", {}).items()
    }


def _label_from_id(raw_id: str) -> str:
    """Turn a snake_case or dash-case id into a Title Case label."""
    parts = [part for part in str(raw_id).replace("-", "_").split("_") if part]
    return " ".join(part.capitalize() for part in parts) if parts else str(raw_id)


def _get_class_skill_options() -> Dict[str, List[str]]:
    return {
        key: list(value)
        for key, value in _creation_reg().get("class_skill_options", {}).items()
    }


def _get_class_skill_counts() -> Dict[str, int]:
    return {
        str(key): int(value)
        for key, value in _creation_reg().get("class_skill_counts", {}).items()
    }


def _get_class_default_skills() -> Dict[str, List[str]]:
    return {
        key: list(value)
        for key, value in _creation_reg().get("class_default_skills", {}).items()
    }


CLASS_SKILL_OPTIONS: Dict[str, List[str]] = _get_class_skill_options()
CLASS_SKILL_COUNTS: Dict[str, int] = _get_class_skill_counts()
CLASS_DEFAULT_SKILLS: Dict[str, List[str]] = _get_class_default_skills()


def recommended_alignment_from_axes(axes: Dict[str, int]) -> str:
    """Derive alignment string from alignment axis weights."""
    law_chaos = int((axes or {}).get("law_chaos", 0))
    good_evil = int((axes or {}).get("good_evil", 0))
    law = "L" if law_chaos >= 30 else "C" if law_chaos <= -30 else "N"
    good = "G" if good_evil >= 30 else "E" if good_evil <= -30 else "N"
    return "TN" if law == "N" and good == "N" else f"{law}{good}"


def recommended_skills_for_class(state: Dict[str, Any], class_name: str) -> List[str]:
    """Select recommended skills for a class based on skill weights."""
    class_id = str(class_name or DEFAULT_CLASS_ID).lower()
    options = list(CLASS_SKILL_OPTIONS.get(class_id, CLASS_DEFAULT_SKILLS.get(DEFAULT_CLASS_ID, [])))
    limit = CLASS_SKILL_COUNTS.get(class_id, next(iter(CLASS_SKILL_COUNTS.values()), 2))
    weights = dict(state.get("skill_weights", {}))
    selected = sorted(options, key=lambda skill: float(weights.get(skill, 0.0)), reverse=True)[:limit]
    if len(selected) < limit:
        for skill in CLASS_DEFAULT_SKILLS.get(class_id, CLASS_DEFAULT_SKILLS.get(DEFAULT_CLASS_ID, [])):
            if skill not in selected:
                selected.append(skill)
            if len(selected) >= limit:
                break
    return selected


def roll_stat_array(rng: Optional[random.Random] = None) -> List[int]:
    """Roll 4d6-drop-lowest six times and return the six totals."""
    roller = rng or random.Random()
    values: List[int] = []
    for _ in range(6):
        dice = sorted([roller.randint(1, 6) for _ in range(4)], reverse=True)
        values.append(sum(dice[:3]))
    return values


def assign_stats_to_class(scores: List[int], class_name: str) -> Dict[str, int]:
    """Map six rolled scores onto ABILITY_ORDER using class stat priorities."""
    ordered = sorted([int(score) for score in scores], reverse=True)
    priorities_map = _class_stat_priorities()
    default_id = _default_class_id()
    priorities = priorities_map.get(
        str(class_name).lower(),
        priorities_map.get(default_id, []),
    )
    stats: Dict[str, int] = {ability: 10 for ability in ABILITY_ORDER}
    for ability, score in zip(priorities, ordered):
        stats[ability] = score
    return stats


@lru_cache(maxsize=1)
def _build_class_catalog() -> tuple[Dict[str, Any], ...]:
    entries: List[Dict[str, Any]] = []
    for class_data in classes_registry().values():
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
def _build_adapter_catalog() -> tuple[Dict[str, Any], ...]:
    entries: List[Dict[str, Any]] = []
    for adapter_id in load_adapter_ids():
        adapter_data = dict(load_adapter_pack(adapter_id))
        starter_content = dict(adapter_data.get("starter_content", {}))
        entries.append(
            {
                "id": str(adapter_id),
                "label": str(adapter_data.get("title") or adapter_data.get("name") or _label_from_id(adapter_id)),
                "allowed_species": list(adapter_data.get("allowed_species", [])),
                "species_labels": dict(adapter_data.get("species_labels", {})),
                "default_player_class": str(starter_content.get("default_player_class", _default_class_id())),
                "starting_focus": str(starter_content.get("starting_focus", "")),
            }
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def _build_profile_catalog() -> tuple[Dict[str, Any], ...]:
    entries: List[Dict[str, Any]] = []
    for profile_id, profile_data in load_world_profiles().items():
        entries.append(
            {
                "id": str(profile_id),
                "label": str(profile_data.get("title") or _label_from_id(profile_id)),
                "world_width": int(profile_data.get("world_width", 0)),
                "world_height": int(profile_data.get("world_height", 0)),
                "history_end_year": int(profile_data.get("history_end_year", 0)),
            }
        )
    return tuple(entries)


def get_creation_catalog() -> Dict[str, Any]:
    """Return the full creation catalog payload."""
    catalog = {
        "mechanics_version": MECHANICS_VERSION,
        "default_class_id": _default_class_id(),
        "default_adapter_id": _default_adapter_id(),
        "default_profile_id": _default_profile_id(),
        "ability_order": list(ABILITY_ORDER),
        "allocation_rules": _allocation_rules(),
        "settlement_labels": _settlement_labels(),
        "faction_labels": _faction_labels(),
        "genesis_defaults": _genesis_defaults(),
        "class_catalog": [dict(entry) for entry in _build_class_catalog()],
        "adapter_catalog": [dict(entry) for entry in _build_adapter_catalog()],
        "profile_catalog": [dict(entry) for entry in _build_profile_catalog()],
    }
    return copy.deepcopy(catalog)


__all__ = [
    "ABILITY_ORDER",
    "CLASS_DEFAULT_SKILLS",
    "CLASS_SKILL_COUNTS",
    "CLASS_SKILL_OPTIONS",
    "DEFAULT_CLASS_ID",
    "MECHANICS_VERSION",
    "_allocation_rules",
    "_creation_reg",
    "_default_adapter_id",
    "_default_class_id",
    "_default_profile_id",
    "_faction_labels",
    "_genesis_defaults",
    "_genesis_templates",
    "_label_from_id",
    "_settlement_labels",
    "assign_stats_to_class",
    "get_creation_catalog",
    "recommended_alignment_from_axes",
    "recommended_skills_for_class",
    "roll_stat_array",
]

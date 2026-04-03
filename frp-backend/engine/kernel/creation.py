"""Kernel-native character creation primitives.

Provides stat rolling, class-based stat assignment, and the full
creation catalog without depending on engine.core.
"""
from __future__ import annotations

import copy
import random
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

from engine.data._shared import classes_registry, creation_registry
from engine.worldgen.registries import (
    load_adapter_ids,
    load_adapter_pack,
    load_world_profiles,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ABILITY_ORDER: List[str] = ["MIG", "AGI", "END", "MND", "INS", "PRE"]

MECHANICS_VERSION = "ember_hybrid_v1"
DEFAULT_CLASS_ID = "warrior"


# ---------------------------------------------------------------------------
# Internal data helpers
# ---------------------------------------------------------------------------

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
        str(k): str(v)
        for k, v in _creation_reg().get("settlement_labels", {}).items()
    }


def _faction_labels() -> Dict[str, str]:
    return {
        str(k): str(v)
        for k, v in _creation_reg().get("faction_labels", {}).items()
    }


def _genesis_defaults() -> Dict[str, str]:
    return {
        str(k): str(v)
        for k, v in _creation_reg().get("genesis_defaults", {}).items()
    }


def _label_from_id(raw_id: str) -> str:
    """Turn a snake_case or dash-case id into a Title Case label."""
    parts = [p for p in str(raw_id).replace("-", "_").split("_") if p]
    return " ".join(p.capitalize() for p in parts) if parts else str(raw_id)


# ---------------------------------------------------------------------------
# Public class-skill data (replaces engine.core.character_creation constants)
# ---------------------------------------------------------------------------

def _get_class_skill_options() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in _creation_reg().get("class_skill_options", {}).items()}

def _get_class_skill_counts() -> Dict[str, int]:
    return {str(key): int(value) for key, value in _creation_reg().get("class_skill_counts", {}).items()}

def _get_class_default_skills() -> Dict[str, List[str]]:
    return {key: list(value) for key, value in _creation_reg().get("class_default_skills", {}).items()}

# Module-level dicts (lazy-loaded on first access via property-like pattern).
CLASS_SKILL_OPTIONS: Dict[str, List[str]] = _get_class_skill_options()
CLASS_SKILL_COUNTS: Dict[str, int] = _get_class_skill_counts()
CLASS_DEFAULT_SKILLS: Dict[str, List[str]] = _get_class_default_skills()


def recommended_alignment_from_axes(axes: Dict[str, int]) -> str:
    """Derive alignment string from alignment axis weights."""
    law_axis = int((axes or {}).get("law_chaos", 0))
    good_axis = int((axes or {}).get("good_evil", 0))
    law = "L" if law_axis >= 30 else "C" if law_axis <= -30 else "N"
    good = "G" if good_axis >= 30 else "E" if good_axis <= -30 else "N"
    alignment = f"{law}{good}"
    return "TN" if alignment == "NN" else alignment


def recommended_skills_for_class(state: Dict[str, Any], class_name: str) -> List[str]:
    """Select recommended skills for a class based on skill weights."""
    normalized_class = str(class_name or DEFAULT_CLASS_ID).lower()
    options = list(CLASS_SKILL_OPTIONS.get(normalized_class, CLASS_DEFAULT_SKILLS.get(DEFAULT_CLASS_ID, [])))
    skill_pick_default = next(iter(CLASS_SKILL_COUNTS.values()), 2)
    limit = CLASS_SKILL_COUNTS.get(normalized_class, skill_pick_default)
    skill_weights = dict(state.get("skill_weights", {}))
    ranked = sorted(options, key=lambda s: float(skill_weights.get(s, 0.0)), reverse=True)
    selected = ranked[:limit]
    if len(selected) < limit:
        for skill in CLASS_DEFAULT_SKILLS.get(normalized_class, CLASS_DEFAULT_SKILLS.get(DEFAULT_CLASS_ID, [])):
            if skill not in selected:
                selected.append(skill)
            if len(selected) >= limit:
                break
    return selected


# ---------------------------------------------------------------------------
# Stat rolling
# ---------------------------------------------------------------------------

def roll_stat_array(rng: Optional[random.Random] = None) -> List[int]:
    """Roll 4d6-drop-lowest six times and return the six totals."""
    roller = rng or random.Random()
    values: List[int] = []
    for _ in range(6):
        dice = sorted([roller.randint(1, 6) for _ in range(4)], reverse=True)
        values.append(sum(dice[:3]))
    return values


# ---------------------------------------------------------------------------
# Stat assignment
# ---------------------------------------------------------------------------

def assign_stats_to_class(scores: List[int], class_name: str) -> Dict[str, int]:
    """Map six rolled scores onto ABILITY_ORDER using class stat priorities.

    Scores are sorted highest-first and matched in order against the
    class's priority list so that the most important ability gets the
    highest roll.
    """
    ordered = sorted([int(s) for s in scores], reverse=True)
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


# ---------------------------------------------------------------------------
# Creation state
# ---------------------------------------------------------------------------

@dataclass
class CreationState:
    """Minimal kernel-side creation session state.

    Tracks the player name, dice rolls, and an auto-generated session id.
    Does *not* carry question/answer weight logic -- that stays in
    engine.core.character_creation for now.
    """

    player_name: str
    location: Optional[str] = None
    rng_seed: Optional[int] = None
    creation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    current_roll: List[int] = field(default_factory=list)
    saved_roll: Optional[List[int]] = None
    reroll_count: int = 0

    # -- RNG helpers --------------------------------------------------------

    def _roll_rng(self, offset: int = 0) -> Optional[random.Random]:
        if self.rng_seed is None:
            return None
        return random.Random(int(self.rng_seed) + int(offset))

    def ensure_roll(self, rng: Optional[random.Random] = None) -> List[int]:
        """Generate an initial stat roll if one has not been made yet."""
        if not self.current_roll:
            self.current_roll = roll_stat_array(
                rng or self._roll_rng(self.reroll_count),
            )
        return list(self.current_roll)

    def reroll(self, rng: Optional[random.Random] = None) -> List[int]:
        """Discard the current roll and generate a fresh one."""
        self.reroll_count += 1
        self.current_roll = roll_stat_array(
            rng or self._roll_rng(self.reroll_count),
        )
        return list(self.current_roll)

    def save_current_roll(self) -> List[int]:
        """Stash the current roll so the player can compare after a reroll."""
        self.saved_roll = list(self.current_roll or [])
        return list(self.saved_roll)

    def swap_rolls(self) -> Dict[str, Optional[List[int]]]:
        """Swap current and saved rolls."""
        if self.saved_roll is None:
            raise ValueError("No saved roll to swap with.")
        self.current_roll, self.saved_roll = (
            list(self.saved_roll),
            list(self.current_roll or []),
        )
        return {
            "current_roll": list(self.current_roll),
            "saved_roll": list(self.saved_roll),
        }


# ---------------------------------------------------------------------------
# Creation catalog
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _build_class_catalog() -> tuple[Dict[str, Any], ...]:
    entries: List[Dict[str, Any]] = []
    for class_data in classes_registry().values():
        class_id = str(class_data.get("id", "")).lower()
        if not class_id:
            continue
        entries.append({
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
        })
    return tuple(entries)


@lru_cache(maxsize=1)
def _build_adapter_catalog() -> tuple[Dict[str, Any], ...]:
    results: List[Dict[str, Any]] = []
    for adapter_id in load_adapter_ids():
        adapter = dict(load_adapter_pack(adapter_id))
        starter = dict(adapter.get("starter_content", {}))
        results.append({
            "id": str(adapter_id),
            "label": str(
                adapter.get("title")
                or adapter.get("name")
                or _label_from_id(adapter_id),
            ),
            "allowed_species": list(adapter.get("allowed_species", [])),
            "species_labels": dict(adapter.get("species_labels", {})),
            "default_player_class": str(
                starter.get("default_player_class", _default_class_id()),
            ),
            "starting_focus": str(starter.get("starting_focus", "")),
        })
    return tuple(results)


@lru_cache(maxsize=1)
def _build_profile_catalog() -> tuple[Dict[str, Any], ...]:
    entries: List[Dict[str, Any]] = []
    for profile_id, profile in load_world_profiles().items():
        entries.append({
            "id": str(profile_id),
            "label": str(profile.get("title") or _label_from_id(profile_id)),
            "world_width": int(profile.get("world_width", 0)),
            "world_height": int(profile.get("world_height", 0)),
            "history_end_year": int(profile.get("history_end_year", 0)),
        })
    return tuple(entries)


def get_creation_catalog() -> Dict[str, Any]:
    """Return the full creation catalog payload.

    Includes class / adapter / profile catalogs plus allocation rules and
    other static creation metadata.  Returns a deep copy so callers can
    mutate freely.
    """
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
        "class_catalog": [dict(e) for e in _build_class_catalog()],
        "adapter_catalog": [dict(e) for e in _build_adapter_catalog()],
        "profile_catalog": [dict(e) for e in _build_profile_catalog()],
    }
    return copy.deepcopy(catalog)

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
    lc = int((axes or {}).get("law_chaos", 0))
    ge = int((axes or {}).get("good_evil", 0))
    law = "L" if lc >= 30 else "C" if lc <= -30 else "N"
    good = "G" if ge >= 30 else "E" if ge <= -30 else "N"
    return "TN" if law == "N" and good == "N" else f"{law}{good}"


def recommended_skills_for_class(state: Dict[str, Any], class_name: str) -> List[str]:
    """Select recommended skills for a class based on skill weights."""
    cls = str(class_name or DEFAULT_CLASS_ID).lower()
    options = list(CLASS_SKILL_OPTIONS.get(cls, CLASS_DEFAULT_SKILLS.get(DEFAULT_CLASS_ID, [])))
    limit = CLASS_SKILL_COUNTS.get(cls, next(iter(CLASS_SKILL_COUNTS.values()), 2))
    weights = dict(state.get("skill_weights", {}))
    selected = sorted(options, key=lambda s: float(weights.get(s, 0.0)), reverse=True)[:limit]
    if len(selected) < limit:
        for s in CLASS_DEFAULT_SKILLS.get(cls, CLASS_DEFAULT_SKILLS.get(DEFAULT_CLASS_ID, [])):
            if s not in selected:
                selected.append(s)
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
    """Kernel-authoritative character creation state.

    Drives the full Q&A flow: loads questions from character_creation.json,
    accumulates weights from answers, and produces recommendations, genesis
    hints, and world seed hints used by CampaignRuntime.finalize_creation.
    """

    player_name: str
    location: Optional[str] = None
    rng_seed: Optional[int] = None
    creation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    current_roll: List[int] = field(default_factory=list)
    saved_roll: Optional[List[int]] = None
    reroll_count: int = 0

    # Weight accumulators — populated by answer_question().
    answers: List[Dict[str, Any]] = field(default_factory=list)
    class_weights: Dict[str, float] = field(default_factory=dict)
    skill_weights: Dict[str, float] = field(default_factory=dict)
    alignment_axes: Dict[str, int] = field(default_factory=lambda: {"law_chaos": 0, "good_evil": 0})
    facet_scores: Dict[str, int] = field(default_factory=dict)
    adapter_bias: Dict[str, int] = field(default_factory=dict)
    faction_bias: Dict[str, int] = field(default_factory=dict)
    settlement_bias: Dict[str, int] = field(default_factory=dict)

    # Internal caches (not serialized).
    _questions_cache: Optional[List[Dict[str, Any]]] = field(default=None, repr=False)
    _groups_cache: Optional[List[Dict[str, Any]]] = field(default=None, repr=False)

    # -- Question loading ---------------------------------------------------

    @property
    def question_groups(self) -> List[Dict[str, Any]]:
        if self._groups_cache is None:
            self._groups_cache = list(_creation_reg().get("question_groups", []))
        return self._groups_cache

    @property
    def questions(self) -> List[Dict[str, Any]]:
        if self._questions_cache is None:
            flat: List[Dict[str, Any]] = []
            for group in self.question_groups:
                flat.extend(group.get("questions", []))
            self._questions_cache = flat
        return self._questions_cache

    # -- Answer + weight accumulation ---------------------------------------

    def answer_question(self, question_id: str, answer_id: str) -> None:
        """Record an answer and accumulate its weights."""
        question = self._find_question(question_id)
        answer = self._find_answer(question, answer_id)
        self.answers.append({"question_id": question_id, "answer_id": answer_id})
        for cls, w in answer.get("class_weights", {}).items():
            self.class_weights[cls] = self.class_weights.get(cls, 0.0) + float(w)
        for skill, w in answer.get("skill_weights", {}).items():
            self.skill_weights[skill] = self.skill_weights.get(skill, 0.0) + float(w)
        for axis, delta in answer.get("alignment_axes", {}).items():
            self.alignment_axes[axis] = self.alignment_axes.get(axis, 0) + int(delta)
        for facet, w in answer.get("facet_weights", {}).items():
            self.facet_scores[facet] = self.facet_scores.get(facet, 0) + int(w)
        for aid, w in answer.get("adapter_weights", {}).items():
            self.adapter_bias[aid] = self.adapter_bias.get(aid, 0) + int(w)
        for fid, w in answer.get("faction_bias", {}).items():
            self.faction_bias[fid] = self.faction_bias.get(fid, 0) + int(w)
        for sid, w in answer.get("settlement_bias", {}).items():
            self.settlement_bias[sid] = self.settlement_bias.get(sid, 0) + int(w)

    def _find_question(self, question_id: str) -> Dict[str, Any]:
        for q in self.questions:
            if q["id"] == question_id:
                return q
        raise ValueError(f"Unknown question: {question_id}")

    def _find_answer(self, question: Dict[str, Any], answer_id: str) -> Dict[str, Any]:
        for a in question.get("answers", []):
            if a["id"] == answer_id:
                return a
        raise ValueError(f"Unknown answer: {answer_id} for question {question['id']}")

    # -- Recommendations ----------------------------------------------------

    def recommended_class(self) -> str:
        if not self.class_weights:
            return _default_class_id()
        return max(self.class_weights, key=lambda k: self.class_weights[k])

    def recommended_alignment(self) -> str:
        return recommended_alignment_from_axes(self.alignment_axes)

    def recommended_skills(self, class_name: Optional[str] = None) -> List[str]:
        effective_class = class_name or self.recommended_class()
        return recommended_skills_for_class(
            {"skill_weights": self.skill_weights}, effective_class,
        )

    # -- Genesis and hints --------------------------------------------------

    def campaign_genesis(self) -> Dict[str, Any]:
        return {
            "settlement_bias": dict(self.settlement_bias),
            "faction_bias": dict(self.faction_bias),
            "facet_scores": dict(self.facet_scores),
            "adapter_bias": dict(self.adapter_bias),
        }

    def world_seed_hints(self) -> Dict[str, Any]:
        world_tags: List[str] = []
        quest_themes: List[str] = []
        tone_tags: List[str] = []
        for entry in self.answers:
            q = self._find_question(entry["question_id"])
            a = self._find_answer(q, entry["answer_id"])
            world_tags.extend(a.get("world_tags", []))
            quest_themes.extend(a.get("quest_themes", []))
            tone_tags.extend(a.get("tone_tags", []))
        return {
            "world_tags": world_tags,
            "quest_themes": quest_themes,
            "tone_tags": tone_tags,
            "alignment_axes": dict(self.alignment_axes),
        }

    def allocation_rules(self) -> Dict[str, Any]:
        return _allocation_rules()

    # -- Serialization ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        effective_class = self.recommended_class()
        roll_pool = sorted(list(self.current_roll), reverse=True) if self.current_roll else []
        saved_pool = sorted(list(self.saved_roll), reverse=True) if self.saved_roll else None
        return {
            "creation_id": self.creation_id,
            "player_name": self.player_name,
            "question_groups": [copy.deepcopy(g) for g in self.question_groups],
            "questions": [copy.deepcopy(q) for q in self.questions],
            "answers": list(self.answers),
            "class_weights": dict(self.class_weights),
            "skill_weights": dict(self.skill_weights),
            "alignment_axes": dict(self.alignment_axes),
            "facet_scores": dict(self.facet_scores),
            "adapter_bias": dict(self.adapter_bias),
            "faction_bias": dict(self.faction_bias),
            "settlement_bias": dict(self.settlement_bias),
            "campaign_genesis": self.campaign_genesis(),
            "world_seed_hints": self.world_seed_hints(),
            "allocation_rules": self.allocation_rules(),
            "recommended_class": effective_class,
            "recommended_alignment": self.recommended_alignment(),
            "recommended_skills": self.recommended_skills(effective_class),
            "current_roll": list(self.current_roll),
            "saved_roll": list(self.saved_roll) if self.saved_roll else None,
            "roll_pool": roll_pool,
            "saved_roll_pool": saved_pool,
        }

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
    out: List[Dict[str, Any]] = []
    for cd in classes_registry().values():
        cid = str(cd.get("id", "")).lower()
        if not cid:
            continue
        out.append({"id": cid, "label": str(cd.get("name") or _label_from_id(cid)),
            "description": str(cd.get("description", "")),
            "ability_priority": list(cd.get("ability_priority", [])),
            "skill_pool": list(cd.get("skill_pool", [])),
            "default_skills": list(cd.get("default_skills", [])),
            "skill_pick_count": int(cd.get("skill_pick_count", 0)),
            "ap_per_turn": int(cd.get("ap_per_turn", 0)),
            "hit_die_size": int(cd.get("hit_die_size", 0)),
            "armor_type": str(cd.get("armor_type", ""))})
    return tuple(out)


@lru_cache(maxsize=1)
def _build_adapter_catalog() -> tuple[Dict[str, Any], ...]:
    out: List[Dict[str, Any]] = []
    for aid in load_adapter_ids():
        ad = dict(load_adapter_pack(aid))
        st = dict(ad.get("starter_content", {}))
        out.append({"id": str(aid),
            "label": str(ad.get("title") or ad.get("name") or _label_from_id(aid)),
            "allowed_species": list(ad.get("allowed_species", [])),
            "species_labels": dict(ad.get("species_labels", {})),
            "default_player_class": str(st.get("default_player_class", _default_class_id())),
            "starting_focus": str(st.get("starting_focus", ""))})
    return tuple(out)


@lru_cache(maxsize=1)
def _build_profile_catalog() -> tuple[Dict[str, Any], ...]:
    out: List[Dict[str, Any]] = []
    for pid, p in load_world_profiles().items():
        out.append({"id": str(pid), "label": str(p.get("title") or _label_from_id(pid)),
            "world_width": int(p.get("world_width", 0)),
            "world_height": int(p.get("world_height", 0)),
            "history_end_year": int(p.get("history_end_year", 0))})
    return tuple(out)


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

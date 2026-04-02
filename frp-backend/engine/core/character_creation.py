"""
Shared D&D-style character creation flow for API clients and terminal UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy
import random
import uuid

from engine.core.creation_catalog import get_creation_adapter_entry
from engine.data_loader import (
    get_creation_ability_order,
    get_creation_allocation_rules,
    get_creation_class_default_skills,
    get_creation_class_skill_counts,
    get_creation_class_skill_options,
    get_creation_class_stat_priorities,
    get_creation_default_adapter,
    get_creation_default_class,
    get_creation_faction_labels,
    get_creation_genesis_defaults,
    get_creation_genesis_templates,
    get_creation_question_groups,
    get_creation_questions,
    get_creation_settlement_labels,
)

CLASS_SKILL_OPTIONS: Dict[str, List[str]] = get_creation_class_skill_options()
CLASS_SKILL_COUNTS: Dict[str, int] = get_creation_class_skill_counts()
CLASS_DEFAULT_SKILLS: Dict[str, List[str]] = get_creation_class_default_skills()
CLASS_STAT_PRIORITIES: Dict[str, List[str]] = get_creation_class_stat_priorities()
ABILITY_ORDER = get_creation_ability_order()
CREATION_QUESTIONS: List[Dict[str, Any]] = get_creation_questions()
CREATION_QUESTION_GROUPS: List[Dict[str, Any]] = get_creation_question_groups()
ALLOCATION_RULES: Dict[str, Any] = get_creation_allocation_rules()
DEFAULT_CLASS_ID = get_creation_default_class()
DEFAULT_ADAPTER_ID = get_creation_default_adapter()
SETTLEMENT_LABELS = get_creation_settlement_labels()
FACTION_LABELS = get_creation_faction_labels()
GENESIS_DEFAULTS = get_creation_genesis_defaults()
GENESIS_TEMPLATES = get_creation_genesis_templates()


def _readable_token(token: str) -> str:
    return str(token or "").replace("_", " ").strip()


def _adapter_label(adapter_id: str) -> str:
    entry = get_creation_adapter_entry(adapter_id)
    return str(entry.get("label") or _readable_token(adapter_id))


def _skill_pick_default() -> int:
    first_value = next(iter(CLASS_SKILL_COUNTS.values()), 0)
    return int(first_value)


def roll_stat_array(rng: Optional[random.Random] = None) -> List[int]:
    roller = rng or random.Random()
    values: List[int] = []
    for _ in range(6):
        dice = sorted([roller.randint(1, 6) for _ in range(4)], reverse=True)
        values.append(sum(dice[:3]))
    return values


def assign_stats_to_class(scores: List[int], class_name: str) -> Dict[str, int]:
    ordered = sorted([int(score) for score in scores], reverse=True)
    priorities = CLASS_STAT_PRIORITIES.get(str(class_name).lower(), CLASS_STAT_PRIORITIES.get(DEFAULT_CLASS_ID, []))
    stats = {ability: 10 for ability in ABILITY_ORDER}
    for ability, score in zip(priorities, ordered):
        stats[ability] = score
    return stats


def recommended_alignment_from_axes(axes: Dict[str, int]) -> str:
    law_axis = int((axes or {}).get("law_chaos", 0))
    good_axis = int((axes or {}).get("good_evil", 0))
    law = "L" if law_axis >= 30 else "C" if law_axis <= -30 else "N"
    good = "G" if good_axis >= 30 else "E" if good_axis <= -30 else "N"
    return f"{law}{good}"


def _best_class(class_weights: Dict[str, int]) -> str:
    if not class_weights:
        return DEFAULT_CLASS_ID
    return sorted(class_weights.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]


def _merge_scores(existing: Dict[str, int], updates: Dict[str, int]) -> Dict[str, int]:
    merged = dict(existing or {})
    for key, value in (updates or {}).items():
        merged[key] = int(merged.get(key, 0)) + int(value)
    return merged


def _sorted_weight_pairs(weight_map: Dict[str, int], limit: int = 4) -> List[tuple[str, int]]:
    return sorted(
        ((str(key), int(value)) for key, value in (weight_map or {}).items() if int(value) != 0),
        key=lambda pair: (-pair[1], pair[0]),
    )[:limit]


def _dedupe_strings(values: List[str], limit: int = 4) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
        if len(ordered) >= limit:
            break
    return ordered


def _history_years(seed: Optional[int], count: int) -> List[int]:
    rng = random.Random(int(seed or 0) + 913)
    year = 1
    years: List[int] = []
    for _ in range(max(1, count)):
        years.append(year)
        year += rng.randint(11, 23)
    return years


def recommended_skills_for_class(state: Dict[str, Any], class_name: str) -> List[str]:
    normalized_class = str(class_name or DEFAULT_CLASS_ID).lower()
    options = list(CLASS_SKILL_OPTIONS.get(normalized_class, CLASS_DEFAULT_SKILLS.get(DEFAULT_CLASS_ID, [])))
    limit = CLASS_SKILL_COUNTS.get(normalized_class, _skill_pick_default())
    skill_weights = dict(state.get("skill_weights", {}))
    ranked = sorted(
        options,
        key=lambda skill: (-int(skill_weights.get(skill, 0)), options.index(skill)),
    )
    selected = ranked[:limit]
    if len(selected) < limit:
        for skill in CLASS_DEFAULT_SKILLS.get(normalized_class, CLASS_DEFAULT_SKILLS.get(DEFAULT_CLASS_ID, [])):
            if skill not in selected:
                selected.append(skill)
            if len(selected) >= limit:
                break
    return selected[:limit]


@dataclass
class CreationState:
    player_name: str
    location: Optional[str] = None
    rng_seed: Optional[int] = None
    creation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    question_groups: List[Dict[str, Any]] = field(default_factory=lambda: copy.deepcopy(CREATION_QUESTION_GROUPS))
    question_bank: List[Dict[str, Any]] = field(default_factory=lambda: copy.deepcopy(CREATION_QUESTIONS))
    answers: List[Dict[str, Any]] = field(default_factory=list)
    class_weights: Dict[str, int] = field(default_factory=dict)
    skill_weights: Dict[str, int] = field(default_factory=dict)
    alignment_axes: Dict[str, int] = field(default_factory=lambda: {"law_chaos": 0, "good_evil": 0})
    facet_scores: Dict[str, int] = field(default_factory=dict)
    adapter_bias: Dict[str, int] = field(default_factory=dict)
    faction_bias: Dict[str, int] = field(default_factory=dict)
    settlement_bias: Dict[str, int] = field(default_factory=dict)
    current_roll: List[int] = field(default_factory=list)
    saved_roll: Optional[List[int]] = None
    creation_profile: Dict[str, Any] = field(default_factory=dict)
    reroll_count: int = 0

    def _roll_rng(self, offset: int = 0) -> Optional[random.Random]:
        if self.rng_seed is None:
            return None
        return random.Random(int(self.rng_seed) + int(offset))

    def ensure_roll(self, rng: Optional[random.Random] = None) -> List[int]:
        if not self.current_roll:
            self.current_roll = roll_stat_array(rng or self._roll_rng(self.reroll_count))
        return list(self.current_roll)

    def answer_question(self, question_id: str, answer_id: str) -> None:
        question = next((item for item in self.question_bank if item["id"] == question_id), None)
        if question is None:
            raise ValueError(f"Unknown creation question: {question_id}")
        answer = next((item for item in question.get("answers", []) if item["id"] == answer_id), None)
        if answer is None:
            raise ValueError(f"Unknown answer '{answer_id}' for question '{question_id}'")
        self.answers = [entry for entry in self.answers if entry.get("question_id") != question_id]
        self.answers.append({
            "question_id": question_id,
            "answer_id": answer_id,
            "text": answer.get("text"),
        })
        self._recompute_weights()

    def _recompute_weights(self) -> None:
        self.class_weights = {}
        self.skill_weights = {}
        self.alignment_axes = {"law_chaos": 0, "good_evil": 0}
        self.facet_scores = {}
        self.adapter_bias = {}
        self.faction_bias = {}
        self.settlement_bias = {}
        answer_map = {entry["question_id"]: entry["answer_id"] for entry in self.answers}
        for question in self.question_bank:
            answer_id = answer_map.get(question["id"])
            if not answer_id:
                continue
            answer = next((item for item in question.get("answers", []) if item["id"] == answer_id), None)
            if answer is None:
                continue
            self.class_weights = _merge_scores(self.class_weights, answer.get("class_weights", {}))
            self.skill_weights = _merge_scores(self.skill_weights, answer.get("skill_weights", {}))
            self.alignment_axes = _merge_scores(self.alignment_axes, answer.get("alignment_axes", {}))
            self.facet_scores = _merge_scores(self.facet_scores, answer.get("facet_weights", {}))
            self.adapter_bias = _merge_scores(self.adapter_bias, answer.get("adapter_weights", {}))
            self.faction_bias = _merge_scores(self.faction_bias, answer.get("faction_bias", {}))
            self.settlement_bias = _merge_scores(self.settlement_bias, answer.get("settlement_bias", {}))

    def reroll(self, rng: Optional[random.Random] = None) -> List[int]:
        self.reroll_count += 1
        self.current_roll = roll_stat_array(rng or self._roll_rng(self.reroll_count))
        return list(self.current_roll)

    def save_current_roll(self) -> List[int]:
        self.saved_roll = list(self.current_roll or [])
        return list(self.saved_roll)

    def swap_rolls(self) -> Dict[str, Optional[List[int]]]:
        if self.saved_roll is None:
            raise ValueError("No saved roll to swap with.")
        self.current_roll, self.saved_roll = list(self.saved_roll), list(self.current_roll or [])
        return {
            "current_roll": list(self.current_roll),
            "saved_roll": list(self.saved_roll),
        }

    def recommended_class(self) -> str:
        return _best_class(self.class_weights)

    def recommended_alignment(self) -> str:
        return recommended_alignment_from_axes(self.alignment_axes)

    def recommended_skills(self, class_name: Optional[str] = None) -> List[str]:
        return recommended_skills_for_class(
            {"skill_weights": dict(self.skill_weights)},
            class_name or self.recommended_class(),
        )

    def selected_answers(self) -> List[Dict[str, Any]]:
        answer_map = {entry["question_id"]: entry["answer_id"] for entry in self.answers}
        selected: List[Dict[str, Any]] = []
        for question in self.question_bank:
            answer_id = answer_map.get(str(question.get("id", "")))
            if not answer_id:
                continue
            answer = next((item for item in question.get("answers", []) if item.get("id") == answer_id), None)
            if answer is None:
                continue
            selected.append(
                {
                    "question_id": str(question.get("id", "")),
                    "question_text": str(question.get("text", "")),
                    "answer_id": str(answer.get("id", "")),
                    "text": str(answer.get("text", "")),
                    "world_tags": list(answer.get("world_tags", [])),
                    "quest_themes": list(answer.get("quest_themes", [])),
                    "tone_tags": list(answer.get("tone_tags", [])),
                }
            )
        return selected

    def question_groups_payload(self) -> List[Dict[str, Any]]:
        answer_map = {entry["question_id"]: entry["answer_id"] for entry in self.answers}
        groups: List[Dict[str, Any]] = []
        for raw_group in self.question_groups:
            questions: List[Dict[str, Any]] = []
            for question in raw_group.get("questions", []):
                item = copy.deepcopy(question)
                item["selected_answer_id"] = answer_map.get(str(question.get("id", "")), "")
                questions.append(item)
            group_payload = copy.deepcopy(raw_group)
            group_payload["questions"] = questions
            groups.append(group_payload)
        return groups

    def world_seed_hints(self) -> Dict[str, Any]:
        adapter_rank = _sorted_weight_pairs(self.adapter_bias, 2)
        settlement_rank = _sorted_weight_pairs(self.settlement_bias, 2)
        facet_rank = _sorted_weight_pairs(self.facet_scores, 5)
        return {
            "preferred_adapter": adapter_rank[0][0] if adapter_rank else DEFAULT_ADAPTER_ID,
            "secondary_adapter": adapter_rank[1][0] if len(adapter_rank) > 1 else "",
            "preferred_settlement": settlement_rank[0][0] if settlement_rank else "",
            "dominant_facets": [name for name, _value in facet_rank],
        }

    def campaign_genesis(self) -> Dict[str, Any]:
        selected = self.selected_answers()
        world_tags = _dedupe_strings([tag for answer in selected for tag in answer.get("world_tags", [])], 4)
        tone_tags = _dedupe_strings([tag for answer in selected for tag in answer.get("tone_tags", [])], 4)
        quest_themes = _dedupe_strings([tag for answer in selected for tag in answer.get("quest_themes", [])], 5)
        settlement_rank = _sorted_weight_pairs(self.settlement_bias, 2)
        faction_rank = _sorted_weight_pairs(self.faction_bias, 2)
        adapter_rank = _sorted_weight_pairs(self.adapter_bias, 2)
        default_settlement = GENESIS_DEFAULTS.get("settlement_label", "")
        default_faction = GENESIS_DEFAULTS.get("faction_label", "")
        premise_default = GENESIS_DEFAULTS.get("premise_tags", "")
        top_settlement = (
            SETTLEMENT_LABELS.get(settlement_rank[0][0], _readable_token(settlement_rank[0][0]))
            if settlement_rank
            else default_settlement
        )
        top_faction = (
            FACTION_LABELS.get(faction_rank[0][0], _readable_token(faction_rank[0][0]))
            if faction_rank
            else default_faction
        )
        adapter_name = _adapter_label(adapter_rank[0][0] if adapter_rank else DEFAULT_ADAPTER_ID)
        premise_tags = ", ".join(world_tags[:2]) if world_tags else premise_default
        pressure_bits = []
        if quest_themes:
            pressure_bits.append(quest_themes[0].replace("_", " "))
        if tone_tags:
            pressure_bits.append(tone_tags[0].replace("_", " "))
        if not pressure_bits:
            pressure_bits.append(GENESIS_TEMPLATES.get("fallback_pressure", ""))
        history_events: List[str] = []
        years = _history_years(self.rng_seed, max(4, len(selected) + 2))
        history_events.append(
            "Year %d: The %s age opens around the %s." % (
                years[0],
                adapter_name.lower(),
                top_settlement.lower(),
            )
        )
        if selected:
            history_events.append(
                "Year %d: %s becomes the first law of the frontier." % (
                    years[1],
                    str(selected[0].get("text", "An old oath")).strip(),
                )
            )
        history_events.append(
            "Year %d: %s tighten their hold over the %s routes." % (
                years[min(2, len(years) - 1)],
                top_faction.title(),
                top_settlement.lower(),
            )
        )
        if quest_themes:
            history_events.append(
                "Year %d: Rumors of %s spread from watchfires to market halls." % (
                    years[min(3, len(years) - 1)],
                    quest_themes[0].replace("_", " "),
                )
            )
        if tone_tags:
            history_events.append(
                "Year %d: A %s mood settles over the marches." % (
                    years[min(4, len(years) - 1)] if len(years) > 4 else years[-1] + 13,
                    tone_tags[0].replace("_", " "),
                )
            )
        return {
            "adapter_bias": adapter_rank[0][0] if adapter_rank else DEFAULT_ADAPTER_ID,
            "adapter_label": adapter_name,
            "world_premise": GENESIS_TEMPLATES.get("world_premise", "%s %s") % (adapter_name, premise_tags),
            "commander_profile": GENESIS_TEMPLATES.get("commander_profile", "%s %s") % (
                self.recommended_class(),
                self.recommended_alignment(),
            ),
            "colony_archetype": top_settlement,
            "starting_pressure": GENESIS_TEMPLATES.get("starting_pressure", "%s %s") % (
                top_settlement,
                top_faction,
            ),
            "quest_seed_themes": quest_themes,
            "tone_tags": tone_tags,
            "world_tags": world_tags,
            "history_events": history_events,
        }

    def allocation_rules(self) -> Dict[str, Any]:
        return copy.deepcopy(ALLOCATION_RULES)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creation_id": self.creation_id,
            "player_name": self.player_name,
            "location": self.location,
            "question_groups": self.question_groups_payload(),
            "questions": copy.deepcopy(self.question_bank),
            "answers": copy.deepcopy(self.answers),
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
            "recommended_class": self.recommended_class(),
            "recommended_alignment": self.recommended_alignment(),
            "recommended_skills": self.recommended_skills(),
            "current_roll": list(self.current_roll or []),
            "saved_roll": list(self.saved_roll) if self.saved_roll is not None else None,
            "roll_pool": sorted([int(value) for value in self.current_roll or []], reverse=True),
            "saved_roll_pool": sorted([int(value) for value in self.saved_roll or []], reverse=True) if self.saved_roll is not None else [],
            "seed": self.rng_seed,
            "reroll_count": self.reroll_count,
        }

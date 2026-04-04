"""Stateful character-creation flow and genesis/history generation."""
from __future__ import annotations

import copy
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .creation_catalog import (
    _allocation_rules,
    _creation_reg,
    _default_adapter_id,
    _default_class_id,
    _default_profile_id,
    _faction_labels,
    _genesis_defaults,
    _genesis_templates,
    _settlement_labels,
    recommended_alignment_from_axes,
    recommended_skills_for_class,
    roll_stat_array,
)

_GENESIS_YEAR_MARKERS = (1, 120, 260, 410, 575, 740, 890, 1040)


@dataclass
class CreationState:
    """Kernel-authoritative character creation state."""

    player_name: str
    adapter_id: str = field(default_factory=_default_adapter_id)
    profile_id: str = field(default_factory=_default_profile_id)
    location: Optional[str] = None
    rng_seed: Optional[int] = None
    creation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    current_roll: List[int] = field(default_factory=list)
    saved_roll: Optional[List[int]] = None
    reroll_count: int = 0
    answers: List[Dict[str, Any]] = field(default_factory=list)
    class_weights: Dict[str, float] = field(default_factory=dict)
    skill_weights: Dict[str, float] = field(default_factory=dict)
    alignment_axes: Dict[str, int] = field(default_factory=lambda: {"law_chaos": 0, "good_evil": 0})
    facet_scores: Dict[str, int] = field(default_factory=dict)
    adapter_bias: Dict[str, int] = field(default_factory=dict)
    faction_bias: Dict[str, int] = field(default_factory=dict)
    settlement_bias: Dict[str, int] = field(default_factory=dict)
    _questions_cache: Optional[List[Dict[str, Any]]] = field(default=None, repr=False)
    _groups_cache: Optional[List[Dict[str, Any]]] = field(default=None, repr=False)

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

    def answer_question(self, question_id: str, answer_id: str) -> None:
        """Record an answer and accumulate its weights."""
        question = self._find_question(question_id)
        answer = self._find_answer(question, answer_id)
        self.answers.append({"question_id": question_id, "answer_id": answer_id})
        for class_id, weight in answer.get("class_weights", {}).items():
            self.class_weights[class_id] = self.class_weights.get(class_id, 0.0) + float(weight)
        for skill_id, weight in answer.get("skill_weights", {}).items():
            self.skill_weights[skill_id] = self.skill_weights.get(skill_id, 0.0) + float(weight)
        for axis, delta in answer.get("alignment_axes", {}).items():
            self.alignment_axes[axis] = self.alignment_axes.get(axis, 0) + int(delta)
        for facet, weight in answer.get("facet_weights", {}).items():
            self.facet_scores[facet] = self.facet_scores.get(facet, 0) + int(weight)
        for adapter_id, weight in answer.get("adapter_weights", {}).items():
            self.adapter_bias[adapter_id] = self.adapter_bias.get(adapter_id, 0) + int(weight)
        for faction_id, weight in answer.get("faction_bias", {}).items():
            self.faction_bias[faction_id] = self.faction_bias.get(faction_id, 0) + int(weight)
        for settlement_id, weight in answer.get("settlement_bias", {}).items():
            self.settlement_bias[settlement_id] = self.settlement_bias.get(settlement_id, 0) + int(weight)

    def _find_question(self, question_id: str) -> Dict[str, Any]:
        for question in self.questions:
            if question["id"] == question_id:
                return question
        raise ValueError(f"Unknown question: {question_id}")

    def _find_answer(self, question: Dict[str, Any], answer_id: str) -> Dict[str, Any]:
        for answer in question.get("answers", []):
            if answer["id"] == answer_id:
                return answer
        raise ValueError(f"Unknown answer: {answer_id} for question {question['id']}")

    def recommended_class(self) -> str:
        if not self.class_weights:
            return _default_class_id()
        return max(self.class_weights, key=lambda class_id: self.class_weights[class_id])

    def recommended_alignment(self) -> str:
        return recommended_alignment_from_axes(self.alignment_axes)

    def recommended_skills(self, class_name: Optional[str] = None) -> List[str]:
        effective_class = class_name or self.recommended_class()
        return recommended_skills_for_class({"skill_weights": self.skill_weights}, effective_class)

    def _seed_hint_lists(self) -> tuple[list[str], list[str], list[str]]:
        world_tags: list[str] = []
        quest_themes: list[str] = []
        tone_tags: list[str] = []
        for entry in self.answers:
            question = self._find_question(entry["question_id"])
            answer = self._find_answer(question, entry["answer_id"])
            world_tags.extend(str(tag) for tag in answer.get("world_tags", []))
            quest_themes.extend(str(tag) for tag in answer.get("quest_themes", []))
            tone_tags.extend(str(tag) for tag in answer.get("tone_tags", []))
        return world_tags, quest_themes, tone_tags

    def _preferred_adapter(self) -> str:
        if self.adapter_bias:
            winner = max(
                self.adapter_bias.items(),
                key=lambda item: (int(item[1]), str(item[0])),
            )[0]
            return str(winner)
        return str(self.adapter_id or _default_adapter_id())

    def _answer_signature(self) -> str:
        if not self.answers:
            return "unanswered"
        return "|".join(
            f"{entry.get('question_id', '')}:{entry.get('answer_id', '')}"
            for entry in self.answers
        )

    def _history_payload(
        self,
        *,
        preferred_adapter: str,
        world_tags: list[str],
        quest_themes: list[str],
        tone_tags: list[str],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        signature_seed = sum(
            ord(char)
            for char in f"{int(self.rng_seed or 0)}:{self._answer_signature()}:{preferred_adapter}"
        )
        rng = random.Random(signature_seed)
        tag_pool = world_tags or ["frontier roads"]
        theme_pool = quest_themes or ["survival"]
        tone_pool = tone_tags or ["uncertain"]
        history_events: list[str] = []
        history_timeline: list[dict[str, Any]] = []
        for index, year in enumerate(_GENESIS_YEAR_MARKERS):
            tag = tag_pool[index % len(tag_pool)]
            theme = theme_pool[
                (index + rng.randint(0, max(0, len(theme_pool) - 1))) % len(theme_pool)
            ]
            tone = tone_pool[
                (index + rng.randint(0, max(0, len(tone_pool) - 1))) % len(tone_pool)
            ]
            headline = f"{tag.title()} reshapes the frontier"
            summary = (
                f"{theme.title()} pressure defines the "
                f"{preferred_adapter.replace('_', ' ')} frontier in a {tone} age."
            )
            history_events.append(f"Year {year}: {summary}")
            history_timeline.append(
                {
                    "year": year,
                    "headline": headline,
                    "summary": summary,
                    "tags": [tag, theme, tone, preferred_adapter],
                    "importance": 1 + (index % 5),
                }
            )
        return history_events, history_timeline

    def campaign_genesis(self) -> Dict[str, Any]:
        world_tags, quest_themes, tone_tags = self._seed_hint_lists()
        preferred_adapter = self._preferred_adapter()
        history_events, history_timeline = self._history_payload(
            preferred_adapter=preferred_adapter,
            world_tags=world_tags,
            quest_themes=quest_themes,
            tone_tags=tone_tags,
        )
        defaults = _genesis_defaults()
        templates = _genesis_templates()
        settlement_choice = (
            max(
                self.settlement_bias.items(),
                key=lambda item: (int(item[1]), str(item[0])),
            )[0]
            if self.settlement_bias
            else str(defaults.get("settlement_label", "frontier settlement"))
        )
        faction_choice = (
            max(
                self.faction_bias.items(),
                key=lambda item: (int(item[1]), str(item[0])),
            )[0]
            if self.faction_bias
            else str(defaults.get("faction_label", "local power brokers"))
        )
        settlement_label = str(_settlement_labels().get(settlement_choice, settlement_choice)).replace("_", " ")
        faction_label = str(_faction_labels().get(faction_choice, faction_choice)).replace("_", " ")
        premise_tags = ", ".join(world_tags[:2]) if world_tags else str(defaults.get("premise_tags", "hard weather and thin supply lines"))
        tone_text = ", ".join(tone_tags[:2]) if tone_tags else "uncertain omens"
        return {
            "settlement_bias": dict(self.settlement_bias),
            "faction_bias": dict(self.faction_bias),
            "facet_scores": dict(self.facet_scores),
            "adapter_bias": dict(self.adapter_bias),
            "world_premise": str(templates.get("world_premise", "A %s campaign shaped by %s."))
            % (preferred_adapter.replace("_", " "), premise_tags),
            "commander_profile": str(
                templates.get(
                    "commander_profile",
                    "A %s-leaning commander whose instincts point toward %s.",
                )
            ) % (self.recommended_alignment(), self.recommended_class()),
            "starting_pressure": str(
                templates.get(
                    "starting_pressure",
                    "The opening colony leans on %s while %s tightens the screws.",
                )
            ) % (settlement_label, faction_label),
            "history_events": history_events,
            "history_timeline": history_timeline,
            "tone": tone_text,
        }

    def world_seed_hints(self) -> Dict[str, Any]:
        world_tags, quest_themes, tone_tags = self._seed_hint_lists()
        return {
            "world_tags": world_tags,
            "quest_themes": quest_themes,
            "tone_tags": tone_tags,
            "alignment_axes": dict(self.alignment_axes),
            "preferred_adapter": self._preferred_adapter(),
        }

    def allocation_rules(self) -> Dict[str, Any]:
        return _allocation_rules()

    def to_dict(self) -> Dict[str, Any]:
        effective_class = self.recommended_class()
        roll_pool = sorted(list(self.current_roll), reverse=True) if self.current_roll else []
        saved_pool = sorted(list(self.saved_roll), reverse=True) if self.saved_roll else None
        return {
            "creation_id": self.creation_id,
            "player_name": self.player_name,
            "question_groups": [copy.deepcopy(group) for group in self.question_groups],
            "questions": [copy.deepcopy(question) for question in self.questions],
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
            "saved_roll_pool": saved_pool or [],
        }

    def _roll_rng(self, offset: int = 0) -> Optional[random.Random]:
        if self.rng_seed is None:
            return None
        return random.Random(int(self.rng_seed) + int(offset))

    def ensure_roll(self, rng: Optional[random.Random] = None) -> List[int]:
        if not self.current_roll:
            self.current_roll = roll_stat_array(rng or self._roll_rng(self.reroll_count))
        return list(self.current_roll)

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


__all__ = ["CreationState"]

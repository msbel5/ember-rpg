"""
Shared D&D-style character creation flow for API clients and terminal UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import copy
import random
import uuid


CLASS_SKILL_OPTIONS: Dict[str, List[str]] = {
    "warrior": ["athletics", "intimidation", "perception", "survival"],
    "rogue": ["acrobatics", "deception", "stealth", "sleight_of_hand", "perception", "investigation"],
    "mage": ["arcana", "history", "investigation", "religion", "insight"],
    "priest": ["medicine", "insight", "persuasion", "religion", "history"],
}

CLASS_SKILL_COUNTS: Dict[str, int] = {
    "warrior": 2,
    "rogue": 4,
    "mage": 2,
    "priest": 2,
}

CLASS_DEFAULT_SKILLS: Dict[str, List[str]] = {
    "warrior": ["athletics", "perception"],
    "rogue": ["stealth", "deception", "perception", "investigation"],
    "mage": ["arcana", "investigation"],
    "priest": ["insight", "religion"],
}

CLASS_STAT_PRIORITIES: Dict[str, List[str]] = {
    "warrior": ["MIG", "END", "AGI", "PRE", "INS", "MND"],
    "rogue": ["AGI", "INS", "PRE", "MND", "END", "MIG"],
    "mage": ["MND", "INS", "AGI", "PRE", "END", "MIG"],
    "priest": ["INS", "PRE", "END", "MND", "MIG", "AGI"],
}

ABILITY_ORDER = ["MIG", "AGI", "END", "MND", "INS", "PRE"]

CREATION_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "origin",
        "text": "When your village needed help, what did you do first?",
        "answers": [
            {
                "id": "stand_guard",
                "text": "Took up a spear and stood watch.",
                "class_weights": {"warrior": 3, "priest": 1},
                "skill_weights": {"athletics": 2, "perception": 1, "survival": 1},
                "alignment_axes": {"law_chaos": 10, "good_evil": 6},
            },
            {
                "id": "work_back_alleys",
                "text": "Moved quietly, listened, and learned who was lying.",
                "class_weights": {"rogue": 3, "mage": 1},
                "skill_weights": {"stealth": 2, "deception": 1, "investigation": 2},
                "alignment_axes": {"law_chaos": -8, "good_evil": 0},
            },
            {
                "id": "study_old_records",
                "text": "Went for books, records, and old clues.",
                "class_weights": {"mage": 3, "priest": 1},
                "skill_weights": {"arcana": 1, "history": 2, "investigation": 1, "religion": 1},
                "alignment_axes": {"law_chaos": 2, "good_evil": 2},
            },
            {
                "id": "comfort_people",
                "text": "Stayed with the frightened and kept people steady.",
                "class_weights": {"priest": 3, "warrior": 1},
                "skill_weights": {"insight": 2, "medicine": 1, "persuasion": 2},
                "alignment_axes": {"law_chaos": 4, "good_evil": 10},
            },
        ],
    },
    {
        "id": "temptation",
        "text": "A powerful patron offers wealth for a dirty job. What wins out?",
        "answers": [
            {
                "id": "refuse_on_principle",
                "text": "Refuse. Some lines should not be crossed.",
                "class_weights": {"priest": 2, "warrior": 1},
                "skill_weights": {"insight": 1, "persuasion": 1},
                "alignment_axes": {"law_chaos": 8, "good_evil": 12},
            },
            {
                "id": "take_and_control",
                "text": "Take the job, but on your terms and with a plan.",
                "class_weights": {"rogue": 2, "mage": 1},
                "skill_weights": {"deception": 1, "investigation": 1, "stealth": 1},
                "alignment_axes": {"law_chaos": -2, "good_evil": -2},
            },
            {
                "id": "serve_order",
                "text": "Ask who gave the order and whether it serves stability.",
                "class_weights": {"warrior": 1, "priest": 1, "mage": 1},
                "skill_weights": {"history": 1, "persuasion": 1},
                "alignment_axes": {"law_chaos": 12, "good_evil": 0},
            },
            {
                "id": "take_the_money",
                "text": "If the pay is good enough, morals can wait.",
                "class_weights": {"rogue": 2},
                "skill_weights": {"deception": 2, "sleight_of_hand": 1, "intimidation": 1},
                "alignment_axes": {"law_chaos": -6, "good_evil": -12},
            },
        ],
    },
    {
        "id": "fear",
        "text": "What frightens you most when the night is quiet?",
        "answers": [
            {
                "id": "failing_comrades",
                "text": "Letting others die because I hesitated.",
                "class_weights": {"warrior": 2, "priest": 2},
                "skill_weights": {"medicine": 1, "perception": 1, "survival": 1},
                "alignment_axes": {"good_evil": 8},
            },
            {
                "id": "being_controlled",
                "text": "Chains, vows, and any hand trying to steer me.",
                "class_weights": {"rogue": 2, "mage": 1},
                "skill_weights": {"acrobatics": 1, "stealth": 1, "deception": 1},
                "alignment_axes": {"law_chaos": -12},
            },
            {
                "id": "ignorance",
                "text": "Not understanding what is really happening.",
                "class_weights": {"mage": 3},
                "skill_weights": {"arcana": 1, "history": 1, "investigation": 2},
                "alignment_axes": {"law_chaos": 2},
            },
            {
                "id": "losing_faith",
                "text": "Waking one day with nothing worth believing in.",
                "class_weights": {"priest": 3},
                "skill_weights": {"religion": 2, "insight": 1, "persuasion": 1},
                "alignment_axes": {"good_evil": 8, "law_chaos": 4},
            },
        ],
    },
]


def roll_stat_array(rng: Optional[random.Random] = None) -> List[int]:
    roller = rng or random.Random()
    values: List[int] = []
    for _ in range(6):
        dice = sorted([roller.randint(1, 6) for _ in range(4)], reverse=True)
        values.append(sum(dice[:3]))
    return values


def assign_stats_to_class(scores: List[int], class_name: str) -> Dict[str, int]:
    ordered = sorted([int(score) for score in scores], reverse=True)
    priorities = CLASS_STAT_PRIORITIES.get(str(class_name).lower(), CLASS_STAT_PRIORITIES["warrior"])
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
        return "warrior"
    return sorted(class_weights.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]


def _merge_scores(existing: Dict[str, int], updates: Dict[str, int]) -> Dict[str, int]:
    merged = dict(existing or {})
    for key, value in (updates or {}).items():
        merged[key] = int(merged.get(key, 0)) + int(value)
    return merged


def recommended_skills_for_class(state: Dict[str, Any], class_name: str) -> List[str]:
    normalized_class = str(class_name or "warrior").lower()
    options = list(CLASS_SKILL_OPTIONS.get(normalized_class, CLASS_DEFAULT_SKILLS["warrior"]))
    limit = CLASS_SKILL_COUNTS.get(normalized_class, 2)
    skill_weights = dict(state.get("skill_weights", {}))
    ranked = sorted(
        options,
        key=lambda skill: (-int(skill_weights.get(skill, 0)), options.index(skill)),
    )
    selected = ranked[:limit]
    if len(selected) < limit:
        for skill in CLASS_DEFAULT_SKILLS.get(normalized_class, []):
            if skill not in selected:
                selected.append(skill)
            if len(selected) >= limit:
                break
    return selected[:limit]


@dataclass
class CreationState:
    player_name: str
    location: Optional[str] = None
    creation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    question_bank: List[Dict[str, Any]] = field(default_factory=lambda: copy.deepcopy(CREATION_QUESTIONS))
    answers: List[Dict[str, Any]] = field(default_factory=list)
    class_weights: Dict[str, int] = field(default_factory=dict)
    skill_weights: Dict[str, int] = field(default_factory=dict)
    alignment_axes: Dict[str, int] = field(default_factory=lambda: {"law_chaos": 0, "good_evil": 0})
    current_roll: List[int] = field(default_factory=list)
    saved_roll: Optional[List[int]] = None
    creation_profile: Dict[str, Any] = field(default_factory=dict)

    def ensure_roll(self, rng: Optional[random.Random] = None) -> List[int]:
        if not self.current_roll:
            self.current_roll = roll_stat_array(rng)
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

    def reroll(self, rng: Optional[random.Random] = None) -> List[int]:
        self.current_roll = roll_stat_array(rng)
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creation_id": self.creation_id,
            "player_name": self.player_name,
            "location": self.location,
            "questions": copy.deepcopy(self.question_bank),
            "answers": copy.deepcopy(self.answers),
            "class_weights": dict(self.class_weights),
            "skill_weights": dict(self.skill_weights),
            "alignment_axes": dict(self.alignment_axes),
            "recommended_class": self.recommended_class(),
            "recommended_alignment": self.recommended_alignment(),
            "recommended_skills": self.recommended_skills(),
            "current_roll": list(self.current_roll or []),
            "saved_roll": list(self.saved_roll) if self.saved_roll is not None else None,
        }

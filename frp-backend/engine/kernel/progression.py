from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value


SKILL_XP_THRESHOLDS = [0, 500, 1100, 1800, 2600, 3500, 4500, 5600, 6800, 8100, 9500, 11000, 12600, 14300, 16100]
SKILL_LEVEL_NAMES = [
    "Dabbling",
    "Novice",
    "Adequate",
    "Competent",
    "Skilled",
    "Proficient",
    "Talented",
    "Adept",
    "Expert",
    "Professional",
    "Accomplished",
    "Great",
    "Master",
    "High Master",
    "Grand Master",
]


@dataclass
class ClassDef:
    class_id: str
    label: str
    hit_die: int
    bab_rate: str
    good_saves: list[str]
    proficiency_rate: int
    skill_points_per_level: int = 0
    spell_type: str = ""
    hp_after_cap: int = 0
    hit_die_cap_level: int = 20
    xp_table: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassDef":
        payload = dict(data)
        payload["good_saves"] = [str(item) for item in payload.get("good_saves", [])]
        payload["xp_table"] = [int(item) for item in payload.get("xp_table", [])]
        return cls(**payload)


@dataclass
class LevelUpResult:
    new_level: int
    hp_gained: int
    bab_new: int
    saves_new: dict[str, int]
    proficiency_points: int
    skill_points: int
    new_spell_slots: dict[int, int]
    ability_increase: bool

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class ProgressionState:
    actor_id: str
    xp: int = 0
    xp_sources: dict[str, int] = field(default_factory=dict)
    level: int = 1
    classes: list[str] = field(default_factory=list)
    class_levels: dict[str, int] = field(default_factory=dict)
    bab: int = 0
    saves: dict[str, int] = field(default_factory=dict)
    proficiency_points_available: int = 0
    skill_points_available: int = 0
    ability_increases_available: int = 0
    skill_xp: dict[str, int] = field(default_factory=dict)
    skill_levels: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgressionState":
        payload = dict(data)
        payload["xp_sources"] = {str(key): int(value) for key, value in payload.get("xp_sources", {}).items()}
        payload["classes"] = [str(item) for item in payload.get("classes", [])]
        payload["class_levels"] = {str(key): int(value) for key, value in payload.get("class_levels", {}).items()}
        payload["saves"] = {str(key): int(value) for key, value in payload.get("saves", {}).items()}
        payload["skill_xp"] = {str(key): int(value) for key, value in payload.get("skill_xp", {}).items()}
        payload["skill_levels"] = {str(key): int(value) for key, value in payload.get("skill_levels", {}).items()}
        return cls(**payload)


def award_xp(progression: ProgressionState, amount: int, source: str) -> None:
    amount = max(0, int(amount))
    source_key = str(source)
    progression.xp += amount
    progression.xp_sources[source_key] = progression.xp_sources.get(source_key, 0) + amount


def can_level_up(progression: ProgressionState, class_defs: dict[str, ClassDef]) -> bool:
    class_ids = progression.classes or list(progression.class_levels.keys())
    if not class_ids:
        return False
    shared_xp = progression.xp // max(1, len(class_ids))
    for class_id in class_ids:
        class_def = class_defs[class_id]
        current_level = int(progression.class_levels.get(class_id, 0))
        next_index = current_level
        if next_index >= len(class_def.xp_table):
            continue
        if shared_xp >= int(class_def.xp_table[next_index]):
            return True
    return False


def execute_level_up(
    progression: ProgressionState,
    class_id: str,
    class_def: ClassDef,
    hit_die_roll: int,
    end_modifier: int,
) -> LevelUpResult:
    class_ids = progression.classes or list(progression.class_levels.keys()) or [class_id]
    if class_id not in class_ids and class_id not in progression.class_levels:
        raise KeyError(class_id)
    shared_xp = progression.xp // max(1, len(class_ids))
    current_level = int(progression.class_levels.get(class_id, 0))
    next_level = current_level + 1
    if current_level >= len(class_def.xp_table):
        raise ValueError(f"{class_id} is already at cap")
    if shared_xp < int(class_def.xp_table[current_level]):
        raise ValueError(f"{class_id} does not meet next level threshold")

    hp_gained = _hp_gain_for_level(class_def, next_level, int(hit_die_roll), int(end_modifier))
    updated_levels = dict(progression.class_levels)
    updated_levels[class_id] = next_level
    bab_new = compute_bab(updated_levels, {class_id: class_def, **class_defs_without(class_id, {})})
    saves_new = compute_saves(updated_levels, {class_id: class_def, **class_defs_without(class_id, {})})
    proficiency_points = 1 if next_level % max(1, int(class_def.proficiency_rate)) == 0 else 0
    skill_points = int(class_def.skill_points_per_level)
    new_spell_slots = _spell_slots_for_level(class_def, next_level)
    ability_increase = next_level % 4 == 0

    progression.class_levels = updated_levels
    progression.classes = sorted(set(class_ids) | {class_id})
    progression.level = sum(updated_levels.values())
    progression.bab = bab_new
    progression.saves = saves_new
    progression.proficiency_points_available += proficiency_points
    progression.skill_points_available += skill_points
    progression.ability_increases_available += 1 if ability_increase else 0

    return LevelUpResult(
        new_level=next_level,
        hp_gained=hp_gained,
        bab_new=bab_new,
        saves_new=saves_new,
        proficiency_points=proficiency_points,
        skill_points=skill_points,
        new_spell_slots=new_spell_slots,
        ability_increase=ability_increase,
    )


def compute_bab(class_levels: dict[str, int], class_defs: dict[str, ClassDef]) -> int:
    best = 0
    for class_id, level in class_levels.items():
        class_def = class_defs[class_id]
        best = max(best, _bab_for_class(int(level), class_def.bab_rate))
    return best


def compute_saves(class_levels: dict[str, int], class_defs: dict[str, ClassDef]) -> dict[str, int]:
    best = {"fortitude": 0, "reflex": 0, "will": 0}
    for class_id, level in class_levels.items():
        class_def = class_defs[class_id]
        for save_name in best:
            best[save_name] = max(best[save_name], _save_for_class(int(level), save_name in class_def.good_saves))
    return best


def award_skill_xp(progression: ProgressionState, skill_id: str, amount: int) -> int:
    skill_key = str(skill_id)
    old_level = progression.skill_levels.get(skill_key, 0)
    progression.skill_xp[skill_key] = progression.skill_xp.get(skill_key, 0) + max(0, int(amount))
    new_level = get_skill_level(progression.skill_xp[skill_key])
    progression.skill_levels[skill_key] = new_level
    return new_level if new_level != old_level else -1


def get_skill_level(skill_xp: int) -> int:
    xp_value = max(0, int(skill_xp))
    level = sum(1 for threshold in SKILL_XP_THRESHOLDS if xp_value >= threshold)
    return min(len(SKILL_LEVEL_NAMES) - 1, level)


def get_skill_level_name(level: int) -> str:
    clamped = max(0, min(len(SKILL_LEVEL_NAMES) - 1, int(level)))
    return SKILL_LEVEL_NAMES[clamped]


def _hp_gain_for_level(class_def: ClassDef, next_level: int, hit_die_roll: int, end_modifier: int) -> int:
    if next_level > int(class_def.hit_die_cap_level):
        return max(1, int(class_def.hp_after_cap) + int(end_modifier))
    return max(1, int(hit_die_roll) + int(end_modifier))


def _bab_for_class(level: int, bab_rate: str) -> int:
    if bab_rate == "full":
        return int(level)
    if bab_rate == "three_quarter":
        return (int(level) * 3) // 4
    if bab_rate == "half":
        return int(level) // 2
    raise ValueError(f"Unknown BAB rate `{bab_rate}`")


def _save_for_class(level: int, good: bool) -> int:
    if good:
        return 2 + (int(level) // 2)
    return int(level) // 3


def _spell_slots_for_level(class_def: ClassDef, level: int) -> dict[int, int]:
    if not class_def.spell_type:
        return {}
    if class_def.spell_type == "wizard":
        return {1: max(1, (int(level) + 1) // 2)}
    if class_def.spell_type == "priest":
        return {1: max(1, (int(level) + 2) // 2)}
    if class_def.spell_type == "sorcerer":
        return {1: max(1, int(level))}
    return {}


def class_defs_without(class_id: str, class_defs: dict[str, ClassDef]) -> dict[str, ClassDef]:
    return {key: value for key, value in class_defs.items() if key != class_id}

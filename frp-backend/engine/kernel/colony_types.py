from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value


@dataclass
class NeedDef:
    need_id: str
    label: str
    decay_rate: float
    fulfillment_base: float
    desperate_threshold: float = 10.0
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NeedDef":
        return cls(**data)


NEED_DEFS: dict[str, NeedDef] = {
    "eat": NeedDef("eat", "Hunger", decay_rate=0.8, fulfillment_base=60.0, desperate_threshold=10.0, weight=1.5),
    "drink": NeedDef("drink", "Thirst", decay_rate=1.0, fulfillment_base=70.0, desperate_threshold=10.0, weight=1.5),
    "sleep": NeedDef("sleep", "Rest", decay_rate=0.4, fulfillment_base=80.0, desperate_threshold=15.0, weight=1.2),
    "pray": NeedDef("pray", "Spirituality", decay_rate=0.2, fulfillment_base=40.0, desperate_threshold=5.0, weight=0.6),
    "socialize": NeedDef("socialize", "Social", decay_rate=0.3, fulfillment_base=35.0, desperate_threshold=10.0, weight=0.8),
    "craft": NeedDef("craft", "Industry", decay_rate=0.15, fulfillment_base=30.0, desperate_threshold=5.0, weight=0.5),
    "train": NeedDef("train", "Training", decay_rate=0.15, fulfillment_base=30.0, desperate_threshold=5.0, weight=0.5),
    "admire_art": NeedDef("admire_art", "Aesthetics", decay_rate=0.1, fulfillment_base=25.0, desperate_threshold=5.0, weight=0.4),
}


@dataclass
class QuestSeed:
    quest_id: str
    kind: str
    title: str
    priority: int = 3
    source_pressure: str = ""

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuestSeed":
        return cls(**data)


@dataclass
class MoraleCascade:
    tier: str
    unrest_min: int
    unrest_max: int
    work_speed_mult: float
    social_hostility: bool
    task_refusal: bool
    tantrum_risk: float

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MoraleCascade":
        return cls(**data)


MORALE_CASCADE_TIERS: list[MoraleCascade] = [
    MoraleCascade("content", 0, 25, work_speed_mult=1.0, social_hostility=False, task_refusal=False, tantrum_risk=0.0),
    MoraleCascade("unhappy", 25, 50, work_speed_mult=0.8, social_hostility=False, task_refusal=False, tantrum_risk=0.0),
    MoraleCascade("miserable", 50, 75, work_speed_mult=0.5, social_hostility=True, task_refusal=True, tantrum_risk=0.02),
    MoraleCascade("breakdown", 75, 101, work_speed_mult=0.2, social_hostility=True, task_refusal=True, tantrum_risk=0.10),
]

SHORTAGE_QUEST_MAP: dict[str, dict[str, Any]] = {
    "food": {"kind": "food", "title": "Address Food Pressure", "priority": 1},
    "materials": {"kind": "materials", "title": "Address Materials Pressure", "priority": 2},
    "security": {"kind": "security", "title": "Address Security Pressure", "priority": 1},
}


@dataclass
class ProductionLedger:
    economy: dict[str, Any] = field(default_factory=dict)
    shortages: list[str] = field(default_factory=list)
    surpluses: list[str] = field(default_factory=list)
    quest_seeds: list[QuestSeed] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionLedger":
        return cls(
            economy=dict(data.get("economy", {})),
            shortages=[str(item) for item in data.get("shortages", [])],
            surpluses=[str(item) for item in data.get("surpluses", [])],
            quest_seeds=[
                item if isinstance(item, QuestSeed) else QuestSeed.from_dict(dict(item))
                for item in data.get("quest_seeds", [])
            ],
        )


@dataclass
class ColonyPressureState:
    food: int
    safety: int
    morale: int
    supply: int
    housing: int
    unrest: int
    shortages: list[str] = field(default_factory=list)
    pressure_tags: list[str] = field(default_factory=list)
    quest_seeds: list[QuestSeed] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColonyPressureState":
        return cls(
            food=int(data.get("food", 0)),
            safety=int(data.get("safety", 0)),
            morale=int(data.get("morale", 0)),
            supply=int(data.get("supply", 0)),
            housing=int(data.get("housing", 0)),
            unrest=int(data.get("unrest", 0)),
            shortages=[str(item) for item in data.get("shortages", [])],
            pressure_tags=[str(item) for item in data.get("pressure_tags", [])],
            quest_seeds=[
                item if isinstance(item, QuestSeed) else QuestSeed.from_dict(dict(item))
                for item in data.get("quest_seeds", [])
            ],
        )


__all__ = [
    "ColonyPressureState",
    "MORALE_CASCADE_TIERS",
    "MoraleCascade",
    "NEED_DEFS",
    "NeedDef",
    "ProductionLedger",
    "QuestSeed",
    "SHORTAGE_QUEST_MAP",
]

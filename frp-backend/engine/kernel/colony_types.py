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


def _load_colony_config() -> dict:
    from engine.data._shared import colony_config_registry
    return colony_config_registry()


def _build_need_defs() -> dict[str, NeedDef]:
    cfg = _load_colony_config()
    return {k: NeedDef(need_id=k, **v) for k, v in cfg.get("needs", {}).items()}


NEED_DEFS: dict[str, NeedDef] = _build_need_defs()


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


def _build_morale_tiers() -> list[MoraleCascade]:
    cfg = _load_colony_config()
    return [MoraleCascade(**t) for t in cfg.get("morale_tiers", [])]


MORALE_CASCADE_TIERS: list[MoraleCascade] = _build_morale_tiers()

SHORTAGE_QUEST_MAP: dict[str, dict[str, Any]] = _load_colony_config().get("shortage_quests", {})


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

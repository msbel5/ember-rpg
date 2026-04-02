from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value


SKILL_XP_THRESHOLDS: list[int] = [
    0,
    500,
    1100,
    1800,
    2600,
    3500,
    4500,
    5600,
    6800,
    8100,
    9500,
    11000,
    12600,
    14300,
    16100,
]

SKILL_LEVEL_NAMES: dict[int, str] = {
    0: "Dabbling",
    1: "Novice",
    2: "Adequate",
    3: "Competent",
    4: "Skilled",
    5: "Proficient",
    6: "Talented",
    7: "Adept",
    8: "Expert",
    9: "Professional",
    10: "Accomplished",
    11: "Great",
    12: "Master",
    13: "High Master",
    14: "Grand Master",
}

QUALITY_LEVELS: dict[int, str] = {
    0: "ordinary",
    1: "well-crafted",
    2: "finely-crafted",
    3: "superior",
    4: "exceptional",
    5: "masterwork",
}


@dataclass
class MaterialRequirement:
    tag: str
    quantity: int
    consumed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialRequirement":
        return cls(**data)


@dataclass
class ProductOutput:
    item_def_id: str
    material_id: str
    quantity: int = 1

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductOutput":
        return cls(**data)


@dataclass
class JobRecord:
    job_id: str
    kind: str
    priority: int
    status: str
    assignee_id: str | None = None
    skill_id: str | None = None
    worksite_id: str | None = None
    room_id: str | None = None
    input_tags: list[str] = field(default_factory=list)
    output_tags: list[str] = field(default_factory=list)
    completion_ticks: int = 100
    elapsed_ticks: int = 0
    tags: list[str] = field(default_factory=list)

    def is_complete(self) -> bool:
        return self.elapsed_ticks >= self.completion_ticks

    def progress_fraction(self) -> float:
        if self.completion_ticks <= 0:
            return 1.0
        return min(1.0, self.elapsed_ticks / self.completion_ticks)

    def transition_to(self, next_status: str) -> None:
        allowed = {
            "queued": {"assigned", "cancelled"},
            "assigned": {"active", "cancelled"},
            "active": {"completed", "cancelled"},
            "completed": set(),
            "cancelled": set(),
        }
        if next_status not in allowed.get(self.status, set()):
            raise ValueError(f"Invalid job transition: {self.status} -> {next_status}")
        self.status = str(next_status)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobRecord":
        payload = dict(data)
        payload["input_tags"] = [str(item) for item in payload.get("input_tags", [])]
        payload["output_tags"] = [str(item) for item in payload.get("output_tags", [])]
        payload["tags"] = [str(item) for item in payload.get("tags", [])]
        return cls(**payload)


@dataclass
class ReactionDef:
    reaction_id: str
    label: str
    worksite_kind: str
    input_materials: list[MaterialRequirement] = field(default_factory=list)
    output_products: list[ProductOutput] = field(default_factory=list)
    required_skill: str = ""
    base_duration_ticks: int = 100
    quality_formula: str = "weighted_random"
    input_tags: list[str] = field(default_factory=list)
    output_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReactionDef":
        payload = dict(data)
        payload["input_materials"] = [
            item if isinstance(item, MaterialRequirement) else MaterialRequirement.from_dict(dict(item))
            for item in payload.get("input_materials", [])
        ]
        payload["output_products"] = [
            item if isinstance(item, ProductOutput) else ProductOutput.from_dict(dict(item))
            for item in payload.get("output_products", [])
        ]
        payload["input_tags"] = [str(item) for item in payload.get("input_tags", [])]
        payload["output_tags"] = [str(item) for item in payload.get("output_tags", [])]
        return cls(**payload)


@dataclass
class WorksiteRecord:
    worksite_id: str
    label: str
    kind: str
    room_id: str | None = None
    supported_jobs: list[str] = field(default_factory=list)
    reaction_ids: list[str] = field(default_factory=list)
    position: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorksiteRecord":
        payload = dict(data)
        position = payload.get("position")
        payload["supported_jobs"] = [str(item) for item in payload.get("supported_jobs", [])]
        payload["reaction_ids"] = [str(item) for item in payload.get("reaction_ids", [])]
        payload["position"] = tuple(position) if position is not None else None
        return cls(**payload)


@dataclass
class SkillRecord:
    skill_id: str
    xp: int = 0
    level: int = 0
    rusty_level: int = 0
    unused_counter: int = 0

    def effective_level(self) -> int:
        return max(0, self.level - self.rusty_level)

    def rust_threshold(self) -> int:
        return 500 if self.level >= 15 else 200

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillRecord":
        return cls(**data)


@dataclass
class RoomZoneDef:
    zone_type: str
    required_furniture: list[str]
    optional_furniture: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomZoneDef":
        payload = dict(data)
        payload["required_furniture"] = [str(item) for item in payload.get("required_furniture", [])]
        payload["optional_furniture"] = [str(item) for item in payload.get("optional_furniture", [])]
        return cls(**payload)


ROOM_ZONE_DEFS: dict[str, RoomZoneDef] = {
    "bedroom": RoomZoneDef("bedroom", required_furniture=["bed"]),
    "dining": RoomZoneDef("dining", required_furniture=["table", "chair"]),
    "workshop": RoomZoneDef("workshop", required_furniture=["worksite"]),
    "hospital": RoomZoneDef("hospital", required_furniture=["bed", "table"]),
    "temple": RoomZoneDef("temple", required_furniture=["altar"]),
}


__all__ = [
    "JobRecord",
    "MaterialRequirement",
    "ProductOutput",
    "QUALITY_LEVELS",
    "ROOM_ZONE_DEFS",
    "ReactionDef",
    "RoomZoneDef",
    "SKILL_LEVEL_NAMES",
    "SKILL_XP_THRESHOLDS",
    "SkillRecord",
    "WorksiteRecord",
]

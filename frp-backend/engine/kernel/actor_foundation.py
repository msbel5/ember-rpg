from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from engine.kernel.common import serialize_value

if TYPE_CHECKING:
    from engine.kernel.effects import EffectQueue

VITAL_PART_IDS = {"head", "neck", "chest", "torso"}
BODY_PART_LABELS = {
    "head": "Head",
    "neck": "Neck",
    "chest": "Chest",
    "torso": "Torso",
    "left_arm": "Left Arm",
    "right_arm": "Right Arm",
    "left_leg": "Left Leg",
    "right_leg": "Right Leg",
}
BODY_PART_LAYER_BLUEPRINTS = {
    "head": (
        {"layer_id": "skin", "material_id": "skin", "relative_thickness": 2, "under_pressure": True},
        {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 2},
        {"layer_id": "bone", "material_id": "bone", "relative_thickness": 3, "structural": True},
        {"layer_id": "brain", "material_id": "organ", "relative_thickness": 2, "vital": True},
    ),
    "neck": (
        {"layer_id": "skin", "material_id": "skin", "relative_thickness": 1, "under_pressure": True},
        {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 2},
        {"layer_id": "spine", "material_id": "bone", "relative_thickness": 2, "structural": True},
        {"layer_id": "artery", "material_id": "organ", "relative_thickness": 1, "under_pressure": True, "vital": True},
    ),
    "chest": (
        {"layer_id": "skin", "material_id": "skin", "relative_thickness": 2, "under_pressure": True},
        {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 3},
        {"layer_id": "ribcage", "material_id": "bone", "relative_thickness": 3, "structural": True},
        {"layer_id": "lungs", "material_id": "organ", "relative_thickness": 2, "vital": True},
    ),
    "torso": (
        {"layer_id": "skin", "material_id": "skin", "relative_thickness": 2, "under_pressure": True},
        {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 3},
        {"layer_id": "spine", "material_id": "bone", "relative_thickness": 2, "structural": True},
        {"layer_id": "organs", "material_id": "organ", "relative_thickness": 2, "vital": True},
    ),
}
DEFAULT_LAYER_BLUEPRINT = (
    {"layer_id": "skin", "material_id": "skin", "relative_thickness": 2, "under_pressure": True},
    {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 2},
    {"layer_id": "bone", "material_id": "bone", "relative_thickness": 2, "structural": True},
)
DEFAULT_NEED_VALUES = {
    "eat": 100.0,
    "drink": 100.0,
    "sleep": 100.0,
    "pray": 100.0,
    "socialize": 100.0,
    "craft": 100.0,
    "train": 100.0,
    "admire_art": 100.0,
}


@dataclass
class ActorIdentity:
    actor_id: str
    display_name: str
    actor_type: str
    faction_id: str | None = None
    site_id: str | None = None
    species_id: str | None = None
    culture_id: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorIdentity":
        return cls(**data)


@dataclass
class ActorPosition:
    x: int
    y: int
    z: int = 0
    region_id: str | None = None
    site_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorPosition":
        return cls(**data)


@dataclass
class NeedState:
    values: dict[str, float] = field(default_factory=dict)
    mood: str = "steady"
    modifiers: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = {key: float(value) for key, value in self.values.items()}
        for need_id, default_value in DEFAULT_NEED_VALUES.items():
            normalized.setdefault(need_id, default_value)
        self.values = normalized

    @classmethod
    def from_legacy(cls, legacy: Any) -> "NeedState":
        if legacy is None:
            return cls()
        if hasattr(legacy, "to_dict"):
            values = {str(key): float(value) for key, value in legacy.to_dict().items()}
            mood = str(legacy.emotional_state()) if hasattr(legacy, "emotional_state") else "steady"
            modifiers = dict(legacy.behavior_modifiers()) if hasattr(legacy, "behavior_modifiers") else {}
            return cls(values=values, mood=mood, modifiers=modifiers)
        return cls(values={str(key): float(value) for key, value in dict(legacy).items()})

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NeedState":
        return cls(
            values={str(key): float(value) for key, value in data.get("values", {}).items()},
            mood=str(data.get("mood", "steady")),
            modifiers=dict(data.get("modifiers", {})),
        )


@dataclass
class ScheduleEntry:
    period: str
    location_id: str | None = None
    position: list[int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleEntry":
        payload = dict(data)
        position = payload.get("position")
        metadata = dict(payload)
        period = str(
            payload.get("period")
            or payload.get("time_period")
            or payload.get("hour")
            or payload.get("activity")
            or "unscheduled"
        )
        location_id = payload.get("location_id") or payload.get("building_kind") or payload.get("activity")
        return cls(
            period=period,
            location_id=str(location_id) if location_id is not None else None,
            position=list(position) if position is not None else None,
            metadata=metadata,
        )


@dataclass
class ScheduleState:
    owner_id: str = ""
    owner_name: str = ""
    entries: list[ScheduleEntry] = field(default_factory=list)
    patrol_route: list[list[int]] = field(default_factory=list)

    @classmethod
    def from_legacy(cls, legacy: Any) -> "ScheduleState":
        if legacy is None:
            return cls()
        data = legacy.to_dict() if hasattr(legacy, "to_dict") else dict(legacy)
        entries: list[ScheduleEntry] = []
        locations = dict(data.get("locations", {}))
        positions = dict(data.get("positions", {}))
        if not entries:
            for period, location_id in locations.items():
                entries.append(
                    ScheduleEntry(
                        period=str(period),
                        location_id=str(location_id),
                        position=list(positions.get(period)) if positions.get(period) is not None else None,
                    )
                )
        for entry in data.get("entries", []):
            if isinstance(entry, dict):
                entries.append(ScheduleEntry.from_dict(entry))
        patrol_route = [list(point) for point in (data.get("patrol_route") or [])]
        return cls(
            owner_id=str(data.get("npc_id", data.get("owner_id", ""))),
            owner_name=str(data.get("npc_name", data.get("owner_name", ""))),
            entries=entries,
            patrol_route=patrol_route,
        )

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleState":
        return cls(
            owner_id=str(data.get("owner_id", "")),
            owner_name=str(data.get("owner_name", "")),
            entries=[ScheduleEntry.from_dict(item) for item in data.get("entries", [])],
            patrol_route=[list(point) for point in data.get("patrol_route", [])],
        )


__all__ = [
    "ActorIdentity",
    "ActorPosition",
    "BODY_PART_LABELS",
    "BODY_PART_LAYER_BLUEPRINTS",
    "DEFAULT_LAYER_BLUEPRINT",
    "DEFAULT_NEED_VALUES",
    "NeedState",
    "ScheduleEntry",
    "ScheduleState",
    "VITAL_PART_IDS",
]

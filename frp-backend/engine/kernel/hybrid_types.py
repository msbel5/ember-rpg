from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.colony import ColonyPressureState
from engine.kernel.common import serialize_value
from engine.kernel.world_state import FactionRecord, RegionRecord, TravelEdge


@dataclass
class TravelState:
    status: str
    origin_region_id: str = ""
    destination_region_id: str = ""
    travel_hours_remaining: int = 0
    travel_hours_total: int = 0
    encounter_roll: float = 0.0
    encounter_triggered: bool = False
    edge_id: str = ""
    danger_level: int = 0
    encounter_checked: bool = False
    paused_for_encounter: bool = False
    encounter_resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TravelState":
        return cls(**data)


@dataclass
class MacroStateView:
    active_region_id: str
    region: RegionRecord
    factions: list[FactionRecord] = field(default_factory=list)
    travel_options: list[TravelEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MacroStateView":
        payload = dict(data)
        payload["region"] = RegionRecord.from_dict(payload["region"])
        payload["factions"] = [FactionRecord.from_dict(item) for item in payload.get("factions", [])]
        payload["travel_options"] = [TravelEdge.from_dict(item) for item in payload.get("travel_options", [])]
        return cls(**payload)


@dataclass
class PathAuthorityState:
    active_region_id: str
    active_site_id: str
    local_map_id: str = ""
    hydrated_from_region: bool = False
    travel_edge_count: int = 0
    reindex_required: bool = False
    local_map_loaded: bool = False
    spawn_point: list[int] = field(default_factory=lambda: [10, 7])

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PathAuthorityState":
        return cls(**data)


@dataclass
class LocalMapState:
    region_id: str
    site_id: str
    width: int
    height: int
    spawn_point: list[int]
    terrain_tags: list[str] = field(default_factory=list)
    biome_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocalMapState":
        return cls(**data)


@dataclass
class SquadMemberRecord:
    actor_id: str
    label: str = ""
    duty: str = "garrison"
    drafted: bool = False
    role: str = "soldier"
    equipment_policy: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SquadMemberRecord":
        return cls(**data)


@dataclass
class SquadRecord:
    squad_id: str
    label: str
    posture: str
    members: list[SquadMemberRecord] = field(default_factory=list)
    orders: list[str] = field(default_factory=list)
    equipment_policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SquadRecord":
        payload = dict(data)
        payload["members"] = [
            item if isinstance(item, SquadMemberRecord) else SquadMemberRecord.from_dict(dict(item))
            for item in payload.get("members", [])
        ]
        return cls(**payload)


@dataclass
class MilitaryState:
    squads: list[SquadRecord] = field(default_factory=list)
    defense_posture: str = "normal"
    alert_level: int = 0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MilitaryState":
        payload = dict(data)
        payload["squads"] = [
            item if isinstance(item, SquadRecord) else SquadRecord.from_dict(dict(item))
            for item in payload.get("squads", [])
        ]
        return cls(**payload)


@dataclass
class LocalActionResolution:
    actor_id: str
    action_id: str
    hours_advanced: int
    remaining_action_points: int
    colony_pressure: ColonyPressureState

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocalActionResolution":
        payload = dict(data)
        payload["colony_pressure"] = ColonyPressureState.from_dict(payload.get("colony_pressure", {}))
        return cls(**payload)


__all__ = [
    "LocalActionResolution",
    "LocalMapState",
    "MacroStateView",
    "MilitaryState",
    "PathAuthorityState",
    "SquadMemberRecord",
    "SquadRecord",
    "TravelState",
]

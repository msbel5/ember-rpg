"""Canonical data models for the world simulation kernel."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Optional


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serialize(val) for key, val in asdict(value).items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(val) for key, val in value.items()}
    return value


@dataclass
class WorldProfile:
    id: str
    title: str
    world_width: int
    world_height: int
    plate_count: int
    climate_bands: int
    region_size: int
    history_end_year: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldProfile":
        return cls(**data)


@dataclass
class TectonicPlate:
    id: str
    cells: list[tuple[int, int]]
    drift_x: float
    drift_y: float
    crust_type: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TectonicPlate":
        payload = dict(data)
        payload["cells"] = [tuple(cell) for cell in payload.get("cells", [])]
        return cls(**payload)


@dataclass
class SpeciesLineage:
    species_id: str
    species_name: str
    sapient: bool
    home_regions: list[str]
    expansion_regions: list[str]
    adapter_payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpeciesLineage":
        return cls(**data)


@dataclass
class FactionSeed:
    id: str
    culture_id: str
    species_id: str
    origin_region_id: str
    traits: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FactionSeed":
        return cls(**data)


@dataclass
class SettlementSeed:
    id: str
    faction_id: str
    region_id: str
    settlement_type: str
    population: int
    center_name: str
    building_focus: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SettlementSeed":
        return cls(**data)


@dataclass
class HistoricalEvent:
    year: int
    event_type: str
    factions: list[str]
    regions: list[str]
    summary: str
    consequences: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoricalEvent":
        return cls(**data)


@dataclass
class SimulationSnapshot:
    current_year: int
    current_hour: int
    active_region_id: Optional[str]
    region_states: dict[str, dict[str, Any]]
    faction_states: dict[str, dict[str, Any]]
    pending_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationSnapshot":
        return cls(**data)


@dataclass
class SettlementLayout:
    width: int
    height: int
    terrain_tiles: list[list[str]]
    road_tiles: list[tuple[int, int]]
    buildings: list[dict[str, Any]]
    furniture: list[dict[str, Any]]
    npc_spawns: list[dict[str, Any]]
    center_feature: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SettlementLayout":
        payload = dict(data)
        payload["road_tiles"] = [tuple(tile) for tile in payload.get("road_tiles", [])]
        return cls(**payload)


@dataclass
class RegionSnapshot:
    region_id: str
    biome_id: str
    width: int
    height: int
    layout: SettlementLayout
    typed_tiles: list[list[dict[str, Any]]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegionSnapshot":
        payload = dict(data)
        payload["layout"] = SettlementLayout.from_dict(payload["layout"])
        return cls(**payload)


@dataclass
class GlobalTickResult:
    hours: int
    updated_regions: list[str]
    generated_events: list[dict[str, Any]]
    new_snapshot: SimulationSnapshot
    active_region_snapshot: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass
class WorldBlueprint:
    seed: int
    profile_id: str
    width: int
    height: int
    history_end_year: int
    tectonic_plates: list[TectonicPlate]
    elevation: list[list[float]]
    temperature: list[list[float]]
    moisture: list[list[float]]
    drainage: list[list[float]]
    biomes: list[list[str]]
    river_paths: list[dict[str, Any]]
    regions: list[dict[str, Any]]
    species_lineages: list[SpeciesLineage] = field(default_factory=list)
    domestication_pools: dict[str, list[str]] = field(default_factory=dict)
    factions: list[FactionSeed] = field(default_factory=list)
    settlements: list[SettlementSeed] = field(default_factory=list)
    historical_events: list[HistoricalEvent] = field(default_factory=list)
    simulation_snapshot: Optional[SimulationSnapshot] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldBlueprint":
        payload = dict(data)
        payload["tectonic_plates"] = [
            TectonicPlate.from_dict(item) for item in payload.get("tectonic_plates", [])
        ]
        payload["species_lineages"] = [
            SpeciesLineage.from_dict(item) for item in payload.get("species_lineages", [])
        ]
        payload["factions"] = [FactionSeed.from_dict(item) for item in payload.get("factions", [])]
        payload["settlements"] = [
            SettlementSeed.from_dict(item) for item in payload.get("settlements", [])
        ]
        payload["historical_events"] = [
            HistoricalEvent.from_dict(item) for item in payload.get("historical_events", [])
        ]
        snapshot = payload.get("simulation_snapshot")
        if snapshot is not None:
            payload["simulation_snapshot"] = SimulationSnapshot.from_dict(snapshot)
        return cls(**payload)

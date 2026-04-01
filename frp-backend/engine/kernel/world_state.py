from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value
from engine.worldgen.models import HistoricalEvent as HistoricalEventSeed
from engine.worldgen.models import WorldBlueprint


@dataclass
class TravelEdge:
    edge_id: str
    source_region_id: str
    destination_region_id: str
    source_settlement_id: str | None = None
    destination_settlement_id: str | None = None
    travel_hours: int = 0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TravelEdge":
        return cls(**data)


@dataclass
class SettlementRecord:
    settlement_id: str
    region_id: str
    faction_id: str
    name: str
    settlement_type: str
    population: int
    biome_id: str | None = None
    primary: bool = True
    grid_position: tuple[int, int] | None = None
    building_focus: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SettlementRecord":
        payload = dict(data)
        grid_position = payload.get("grid_position")
        payload["grid_position"] = tuple(grid_position) if grid_position else None
        return cls(**payload)


@dataclass
class SiteRecord:
    site_id: str
    region_id: str
    settlement_id: str
    site_type: str
    name: str
    owner_faction_id: str | None = None
    population: int = 0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SiteRecord":
        return cls(**data)


@dataclass
class FactionRecord:
    faction_id: str
    culture_id: str
    species_id: str
    origin_region_id: str
    traits: dict[str, float] = field(default_factory=dict)
    region_presence: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FactionRecord":
        return cls(**data)


@dataclass
class HistoryFigure:
    figure_id: str
    display_name: str
    faction_id: str | None = None
    site_id: str | None = None
    species_id: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryFigure":
        return cls(**data)


@dataclass
class HistoryEvent:
    event_id: str
    year: int
    event_type: str
    factions: list[str]
    regions: list[str]
    summary: str
    consequences: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEvent":
        return cls(**data)


@dataclass
class RegionRecord:
    region_id: str
    biome_id: str
    x: int
    y: int
    width: int
    height: int
    controller_faction_id: str | None = None
    settlement_ids: list[str] = field(default_factory=list)
    site_ids: list[str] = field(default_factory=list)
    faction_ids: list[str] = field(default_factory=list)
    economy: dict[str, Any] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegionRecord":
        return cls(**data)


@dataclass
class WorldState:
    seed: int
    profile_id: str
    width: int
    height: int
    active_region_id: str | None
    regions: dict[str, RegionRecord] = field(default_factory=dict)
    settlements: dict[str, SettlementRecord] = field(default_factory=dict)
    sites: dict[str, SiteRecord] = field(default_factory=dict)
    factions: dict[str, FactionRecord] = field(default_factory=dict)
    history_figures: dict[str, HistoryFigure] = field(default_factory=dict)
    history_events: list[HistoryEvent] = field(default_factory=list)
    travel_edges: list[TravelEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldState":
        payload = dict(data)
        payload["regions"] = {
            key: RegionRecord.from_dict(value) for key, value in payload.get("regions", {}).items()
        }
        payload["settlements"] = {
            key: SettlementRecord.from_dict(value) for key, value in payload.get("settlements", {}).items()
        }
        payload["sites"] = {
            key: SiteRecord.from_dict(value) for key, value in payload.get("sites", {}).items()
        }
        payload["factions"] = {
            key: FactionRecord.from_dict(value) for key, value in payload.get("factions", {}).items()
        }
        payload["history_figures"] = {
            key: HistoryFigure.from_dict(value)
            for key, value in payload.get("history_figures", {}).items()
        }
        payload["history_events"] = [
            HistoryEvent.from_dict(item) for item in payload.get("history_events", [])
        ]
        payload["travel_edges"] = [
            TravelEdge.from_dict(item) for item in payload.get("travel_edges", [])
        ]
        return cls(**payload)


def world_state_from_blueprint(world: WorldBlueprint) -> WorldState:
    settlement_nodes = {node["id"]: dict(node) for node in world.settlement_nodes}
    settlements: dict[str, SettlementRecord] = {}
    sites: dict[str, SiteRecord] = {}
    for seed in world.settlements:
        node = settlement_nodes.get(seed.id, {})
        settlement = SettlementRecord(
            settlement_id=seed.id,
            region_id=seed.region_id,
            faction_id=seed.faction_id,
            name=str(node.get("name", seed.center_name)),
            settlement_type=str(node.get("settlement_type", seed.settlement_type)),
            population=int(node.get("population", seed.population)),
            biome_id=node.get("biome_id"),
            primary=bool(node.get("primary", True)),
            grid_position=tuple(node.get("grid_position", [])) if node.get("grid_position") else None,
            building_focus=list(node.get("building_focus", seed.building_focus)),
        )
        settlements[settlement.settlement_id] = settlement
        sites[settlement.settlement_id] = SiteRecord(
            site_id=settlement.settlement_id,
            region_id=settlement.region_id,
            settlement_id=settlement.settlement_id,
            site_type=settlement.settlement_type,
            name=settlement.name,
            owner_faction_id=settlement.faction_id,
            population=settlement.population,
            tags=["primary_site"] if settlement.primary else [],
        )

    factions: dict[str, FactionRecord] = {}
    for seed in world.factions:
        region_presence = {
            region_id: [dict(entry) for entry in entries if entry.get("faction_id") == seed.id]
            for region_id, entries in world.faction_presence.items()
            if any(entry.get("faction_id") == seed.id for entry in entries)
        }
        factions[seed.id] = FactionRecord(
            faction_id=seed.id,
            culture_id=seed.culture_id,
            species_id=seed.species_id,
            origin_region_id=seed.origin_region_id,
            traits=dict(seed.traits),
            region_presence=region_presence,
        )

    regions: dict[str, RegionRecord] = {}
    for region in world.regions:
        region_id = str(region["id"])
        settlement_ids = [
            settlement_id
            for settlement_id, settlement in settlements.items()
            if settlement.region_id == region_id
        ]
        site_ids = [site_id for site_id, site in sites.items() if site.region_id == region_id]
        faction_ids = [entry.get("faction_id", "") for entry in world.faction_presence.get(region_id, [])]
        regions[region_id] = RegionRecord(
            region_id=region_id,
            biome_id=str(region.get("biome_id", "unknown")),
            x=int(region.get("x", 0)),
            y=int(region.get("y", 0)),
            width=int(region.get("width", 0)),
            height=int(region.get("height", 0)),
            controller_faction_id=region.get("controller_faction_id"),
            settlement_ids=settlement_ids,
            site_ids=site_ids,
            faction_ids=[faction_id for faction_id in faction_ids if faction_id],
            economy=dict(world.region_economy.get(region_id, {})),
            alerts=list(world.region_alerts.get(region_id, [])),
            metadata={
                "avg_temperature": region.get("avg_temperature"),
                "avg_moisture": region.get("avg_moisture"),
                "avg_drainage": region.get("avg_drainage"),
                "avg_elevation": region.get("avg_elevation"),
                "settlement_suitability": region.get("settlement_suitability"),
                "river_present": region.get("river_present"),
                "resources": _normalize_sequence(region.get("resources", [])),
                "fauna": _normalize_sequence(region.get("fauna", [])),
            },
        )

    history_events = [
        _history_event_from_seed(index, event) for index, event in enumerate(world.historical_events)
    ]
    active_region_id = None
    if world.simulation_snapshot is not None:
        active_region_id = world.simulation_snapshot.active_region_id

    return WorldState(
        seed=world.seed,
        profile_id=world.profile_id,
        width=world.width,
        height=world.height,
        active_region_id=active_region_id,
        regions=regions,
        settlements=settlements,
        sites=sites,
        factions=factions,
        history_events=history_events,
        travel_edges=[_travel_edge_from_payload(edge) for edge in world.travel_edges],
        metadata=dict(world.metadata),
    )


def _travel_edge_from_payload(payload: dict[str, Any]) -> TravelEdge:
    return TravelEdge(
        edge_id=str(payload.get("id", "")),
        source_region_id=str(payload.get("from_region_id", "")),
        destination_region_id=str(payload.get("to_region_id", "")),
        source_settlement_id=payload.get("from_settlement_id"),
        destination_settlement_id=payload.get("to_settlement_id"),
        travel_hours=int(payload.get("travel_hours", 0)),
    )


def _history_event_from_seed(index: int, event: HistoricalEventSeed) -> HistoryEvent:
    return HistoryEvent(
        event_id=f"history_event_{index:04d}",
        year=event.year,
        event_type=event.event_type,
        factions=list(event.factions),
        regions=list(event.regions),
        summary=event.summary,
        consequences=dict(event.consequences),
    )


def _normalize_sequence(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return [{"key": key, "value": item} for key, item in value.items()]
    if value is None:
        return []
    return [value]

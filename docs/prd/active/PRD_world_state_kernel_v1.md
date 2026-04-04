# PRD: World State Kernel V1
**Project:** Ember RPG
**Phase:** 2
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the typed macro-world authority that sits above active local maps. Replaces loosely-shaped world graph payloads with a canonical `WorldState` surface owning regions, sites, settlements, factions, travel edges, and macro runtime metadata. This is the root data structure for DF M14 (World Generation), M11 (Trade), M12 (Migration), and M20 (Diplomacy).

## 2. Scope

- In scope: typed world-state records, region/site/settlement/faction/travel structures, adapter from `WorldBlueprint`, serialization, save/load round-trip, economy and alert hooks per region
- Out of scope: local tile realization internals, detailed history simulation rules (see `PRD_history_and_factions_v1`), final economy balance, Godot UI rendering

## 3. Reference Mechanism Coverage

| DF Mechanism | Coverage | Notes |
|-------------|----------|-------|
| M11 Trade | Macro hooks | Region economy with base prices; caravan schedule deferred |
| M12 Migration | Population tracking | Site population in FactionRecord; wave mechanics deferred |
| M14 World Generation | Full adapter | WorldBlueprint → WorldState typed conversion |
| M20 Diplomacy | Faction presence | Faction traits, region presence; war/peace state deferred |

## 4. Functional Requirements (FR)

FR-01: The backend must define a typed `WorldState` root record containing all macro-world data.
FR-02: `WorldState` must contain typed collections of `RegionRecord`, `SiteRecord`, `SettlementRecord`, `FactionRecord`, and `TravelEdge`.
FR-03: The active macro region must be stored as `WorldState.active_region_id`, not inferred at payload assembly time.
FR-04: An adapter from `engine.worldgen.models.WorldBlueprint` must produce a typed `WorldState`.
FR-05: Two identical seeds must produce identical typed world graph topology.
FR-06: `WorldState` must round-trip through dict serialization with no loss of graph topology, region IDs, edge endpoints, or settlement placements.
FR-07: Each `RegionRecord` must carry economy snapshot (resources, prices) and alert list for colony pressure integration.

## 5. Data Structures

```python
@dataclass
class TravelEdge:
    source_region_id: str
    target_region_id: str
    travel_hours: int = 8
    danger_level: int = 0  # 0=safe, 1=risky, 2=dangerous
    tags: list[str] = field(default_factory=list)

@dataclass
class SettlementRecord:
    settlement_id: str
    name: str
    region_id: str
    population: int = 0
    defense_posture: str = "normal"
    tags: list[str] = field(default_factory=list)

@dataclass
class SiteRecord:
    site_id: str
    name: str
    region_id: str
    site_type: str = "settlement"  # "settlement", "dungeon", "ruin", "camp"
    owning_faction_id: str = ""
    tags: list[str] = field(default_factory=list)

@dataclass
class FactionRecord:
    faction_id: str
    name: str
    culture_id: str = ""
    species_id: str = ""
    origin_region_id: str = ""
    traits: list[str] = field(default_factory=list)
    region_presence: list[str] = field(default_factory=list)
    disposition: str = "neutral"  # "allied", "neutral", "hostile", "at_war"

@dataclass
class HistoryFigure:
    figure_id: str
    name: str
    faction_id: str = ""
    role: str = ""
    birth_year: int = 0
    death_year: int = -1  # -1 = alive
    notable_events: list[str] = field(default_factory=list)

@dataclass
class HistoryEvent:
    event_id: str
    year: int
    event_type: str  # "battle", "founding", "migration", "artifact", "death"
    description: str = ""
    factions_involved: list[str] = field(default_factory=list)
    regions_involved: list[str] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)

@dataclass
class RegionRecord:
    region_id: str
    name: str
    biome_id: str = ""
    settlements: list[SettlementRecord] = field(default_factory=list)
    economy: dict = field(default_factory=dict)  # {"resources": [...], "prices": {...}, "trade_routes": [...]}
    alerts: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

@dataclass
class WorldState:
    adapter_id: str
    profile_id: str
    seed: int
    regions: list[RegionRecord] = field(default_factory=list)
    sites: list[SiteRecord] = field(default_factory=list)
    factions: list[FactionRecord] = field(default_factory=list)
    history_figures: list[HistoryFigure] = field(default_factory=list)
    history_events: list[HistoryEvent] = field(default_factory=list)
    travel_edges: list[TravelEdge] = field(default_factory=list)
    active_region_id: str = ""
```

## 6. Public API

```python
def world_state_from_blueprint(blueprint: WorldBlueprint, adapter_id: str, profile_id: str, seed: int) -> WorldState:
    """Convert a generated WorldBlueprint into a typed WorldState.
    Precondition: blueprint is a valid WorldBlueprint with regions and settlements.
    Postcondition: returned WorldState contains typed records for all regions, sites, factions, travel edges.
    """

def WorldState.to_dict(self) -> dict:
    """Serialize to JSON-compatible dict. All nested records serialized recursively."""

def WorldState.from_dict(cls, data: dict) -> WorldState:
    """Deserialize from dict. Restores all typed records."""
```

## 7. Acceptance Criteria (AC)

AC-01 [FR-01,FR-02]: Given a generated world blueprint, when adapted, then a typed `WorldState` exists with explicit region, settlement, site, faction, and edge collections — each as typed records, not raw dicts.
AC-02 [FR-03]: Given an active region id in the simulation snapshot, when adapted, `WorldState.active_region_id` preserves it.
AC-03 [FR-04,FR-05]: Given a deterministic world seed, two separate adaptations produce matching typed graph topology (same region IDs, same edge endpoints, same settlement counts).
AC-04 [FR-06]: Given a typed world state, serialization to dict and restoration produces identical region IDs, edge endpoints, settlement placements, and faction records.
AC-05 [FR-07]: Given a region with economy data, the adapted `RegionRecord.economy` dict contains resources and prices fields.

## 8. Performance Requirements

- World state adaptation from blueprint: < 500ms for a world with 20 regions
- Serialization/deserialization round-trip: < 100ms

## 9. Error Handling

- Blueprint with no regions: return WorldState with empty collections, no crash
- Region with no settlements: valid RegionRecord with empty settlements list
- Missing faction reference: log warning, use "unknown" faction placeholder

## 10. Integration Points

- `frp-backend/engine/worldgen/models.py` — WorldBlueprint source
- `frp-backend/engine/worldgen/pipeline.py` — generates blueprint
- `frp-backend/engine/api/campaign/world.py` — world state in campaign payloads
- `frp-backend/engine/kernel/colony.py` — colony pressure reads region economy
- `frp-backend/engine/kernel/hybrid.py` — travel uses TravelEdge graph
- Save/load surfaces — world state persisted with campaign

## 11. Test Coverage Target

- Deterministic world-state adaptation (seed stability)
- Save/load round-trip (all typed records survive)
- Graph connectivity preservation (edges match regions)
- Economy and alert data preservation
- 85% line coverage for adapter and serialization functions

## Changelog

- 2026-04-01: Expanded from 59-line stub to full PRD with dataclass definitions, API, 5 ACs, error handling, performance requirements. Added HistoryFigure and HistoryEvent (shared with history_and_factions PRD).

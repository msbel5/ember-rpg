# PRD: History and Factions Kernel V1
**Project:** Ember RPG
**Phase:** 2
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Promotes faction seeds and historical events into stable typed records that drive diplomacy, ownership, legends, migration pressure, and long-form quest context. History is not decoration — it determines faction disposition, site ownership, available quests, and NPC backstories.

## 2. Scope

- In scope: typed faction records, history figures, history events, ownership links, faction disposition, deterministic event ordering from seed
- Out of scope: legend browser UI, procedural prose generation, full diplomacy simulation (war/peace negotiations), religion/sect systems, NPC AI conversation

## 3. Reference Mechanism Coverage

| DF Mechanism | Coverage | Notes |
|-------------|----------|-------|
| M12 Migration/Population | Faction presence tracks population spread | Wave mechanics deferred |
| M14 World Generation | History events generated during worldgen | Year-by-year simulation |
| M20 Diplomacy | Faction disposition + ethics conflicts | Full war/peace state machine deferred |

## 4. Data Structures

```python
@dataclass
class FactionRecord:
    faction_id: str
    name: str
    culture_id: str = ""
    species_id: str = ""
    origin_region_id: str = ""
    traits: list[str] = field(default_factory=list)  # ["militant", "mercantile", "isolationist"]
    ethics: dict[str, str] = field(default_factory=dict)  # {"kill_entity": "unthinkable", "trade": "acceptable"}
    region_presence: list[str] = field(default_factory=list)
    disposition: str = "neutral"  # "allied", "neutral", "unfriendly", "hostile", "at_war"
    population_estimate: int = 100
    notable_figures: list[str] = field(default_factory=list)

@dataclass
class HistoryFigure:
    figure_id: str
    name: str
    faction_id: str = ""
    species_id: str = ""
    role: str = ""  # "king", "warlord", "sage", "hero", "villain"
    birth_year: int = 0
    death_year: int = -1  # -1 = alive
    home_region_id: str = ""
    notable_events: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    artifacts_created: list[str] = field(default_factory=list)

@dataclass
class HistoryEvent:
    event_id: str
    year: int
    event_type: str  # "battle", "founding", "migration", "artifact_creation", "death", "alliance", "betrayal", "plague", "discovery"
    description: str = ""
    factions_involved: list[str] = field(default_factory=list)
    figures_involved: list[str] = field(default_factory=list)
    regions_involved: list[str] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)
    severity: int = 1  # 1=minor, 2=notable, 3=major, 4=world-shaping

@dataclass
class OwnershipLink:
    site_id: str
    faction_id: str
    since_year: int = 0
    contested: bool = False
```

## 5. Functional Requirements (FR)

FR-01: Seeded factions must adapt into typed `FactionRecord` entries with origin, presence, traits, and ethics.
FR-02: Generated historical data must produce typed `HistoryFigure` and `HistoryEvent` records, separately addressable and serializable.
FR-03: Site ownership tracked as typed `OwnershipLink` records that round-trip through save/load.
FR-04: Faction disposition derivable from ethics compatibility (DF M20 ethics conflict rule).
FR-05: Identical world seeds produce deterministic event ordering and identifiers.
FR-06: History events carry consequences linking to system changes (faction loses region, figure dies, artifact created).
FR-07: Faction region_presence updates when ownership changes.

## 6. Public API

```python
def compute_faction_disposition(faction_a: FactionRecord, faction_b: FactionRecord) -> str:
    """Determine disposition based on ethics compatibility.
    Rule: if A.ethics[X]=="unthinkable" and B.ethics[X]=="acceptable" → "hostile"
    Returns: "allied", "neutral", "unfriendly", "hostile", "at_war"
    """

def generate_history_events(factions: list[FactionRecord], regions: list[RegionRecord], years: int, seed: int) -> tuple[list[HistoryEvent], list[HistoryFigure]]:
    """Generate year-by-year history. Deterministic for same seed."""

def apply_event_consequences(event: HistoryEvent, world_state: WorldState) -> WorldState:
    """Apply event consequences to world state. Updates ownership, presence, figure status."""

def ownership_links_from_world(world_state: WorldState) -> list[OwnershipLink]:
    """Extract typed ownership links from world state."""
```

## 7. Acceptance Criteria (AC)

AC-01 [FR-01]: Seeded factions adapt with origin_region_id, traits, and ethics populated.
AC-02 [FR-02]: HistoryFigure and HistoryEvent are separately addressable by ID and serializable.
AC-03 [FR-03]: OwnershipLink round-trips preserving site_id, faction_id, since_year.
AC-04 [FR-04]: Factions with conflicting ethics (unthinkable vs acceptable) compute as "hostile".
AC-05 [FR-05]: Identical seed → identical event_ids in identical order.
AC-06 [FR-06]: Battle event consequence "faction_X_lost_region_Y" removes Y from X.region_presence.
AC-07 [FR-07]: Site founding event adds new region to owning faction's presence.

## 8. Performance Requirements

- History generation for 250 years, 5 factions: < 2s
- Disposition computation: < 1ms per pair

## 9. Error Handling

- Faction with no ethics: treat all as "neutral"
- Figure referencing non-existent faction: use "unknown", log warning
- Event consequence referencing non-existent region: skip, log warning

## 10. Integration Points

- `engine/kernel/world_state.py` — FactionRecord and HistoryEvent inside WorldState
- `engine/worldgen/pipeline.py` — history generation during world creation
- `engine/worldgen/world_tick.py` — ongoing history events during play
- `engine/kernel/colony.py` — faction disposition affects trade/migration pressure
- `engine/kernel/hybrid.py` — travel encounters with hostile factions
- `engine/api/campaign/world.py` — history exposed in campaign payloads

## 11. Test Coverage Target

- Deterministic history generation, ethics disposition, ownership round-trip, consequence application
- 85% line coverage

## Changelog

- 2026-04-01: Expanded from 58-line stub. Added FactionRecord/HistoryFigure/HistoryEvent/OwnershipLink dataclasses, ethics disposition algorithm, 7 ACs, API signatures.

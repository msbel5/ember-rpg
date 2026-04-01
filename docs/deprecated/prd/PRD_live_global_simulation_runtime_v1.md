# PRD: Live Global Simulation Runtime v1
**Project:** Ember RPG  
**Phase:** 6  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Draft  

---

## 1. Purpose
Define how the generated world continues to evolve during gameplay using always-global simulation, multiresolution ticking, and snapshot-safe runtime state that integrates with sessions, save/load, and client map consumption.

## 2. Scope
- In scope: simulation snapshots, global ticking, active vs inactive region resolution, session bootstrap hooks, save/load boundaries, and route-facing outputs.
- Out of scope: rendering, client animation, and narrative generation style.

## 3. Functional Requirements (FR)
FR-01: Runtime world state must be stored in a serializable `SimulationSnapshot` embedded in `WorldBlueprint`.
FR-02: `tick_global` must update every region on each tick using coarse resolution for inactive regions and fine resolution for the active region.
FR-03: Region activation must promote a region from coarse state to fine state without re-generating the macro world.
FR-04: Session bootstrap must derive the first playable region from a realized snapshot produced by the world kernel.
FR-05: Save/load must restore the exact simulation snapshot without re-rolling RNG or replaying history.
FR-06: Runtime outputs must expose generated events, changed regions, and updated active-region snapshots.
FR-07: The runtime must support incremental world-state APIs for map, factions, history, and present-day world effects.

## 4. Data Structures
```python
@dataclass
class SimulationSnapshot:
    current_year: int
    current_hour: int
    active_region_id: str | None
    region_states: dict[str, dict]
    faction_states: dict[str, dict]
    pending_events: list[dict]

@dataclass
class GlobalTickResult:
    hours: int
    updated_regions: list[str]
    generated_events: list[dict]
    active_region_snapshot: dict | None
    new_snapshot: SimulationSnapshot
```

## 5. Public API
```python
def initialize_simulation(world: WorldBlueprint, start_region_id: str | None = None) -> WorldBlueprint
def tick_global(world: WorldBlueprint, hours: int) -> GlobalTickResult
def activate_region(world: WorldBlueprint, region_id: str) -> WorldBlueprint
def snapshot_world(world: WorldBlueprint) -> dict
def load_world_snapshot(data: dict) -> WorldBlueprint
```
- Preconditions: `world` must already be simulated through history.
- Postconditions: `tick_global` returns a new authoritative snapshot.
- Exceptions: invalid region IDs, negative tick values, or malformed snapshots raise `ValueError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: `initialize_simulation` creates a serializable snapshot with region and faction state maps.
AC-02 [FR-02]: A 24-hour tick reports updates for both the active region and at least one inactive region.
AC-03 [FR-03]: Activating a different region preserves macro world identity and history while updating fine-state focus.
AC-04 [FR-05]: A snapshot round-trip preserves current time, active region, and pending events.
AC-05 [FR-06]: `tick_global` returns event and region-delta information without requiring the caller to diff snapshots manually.
AC-06 [FR-07]: Runtime-facing world data can be derived from the snapshot without consulting legacy history tables or standalone map generators.

## 7. Performance Requirements
- `tick_global(world, 1)` must complete in under 50 ms for the standard profile.
- `tick_global(world, 24)` must complete in under 250 ms for the standard profile.
- Snapshot serialization or load must complete in under 100 ms.

## 8. Error Handling
- Snapshot schema mismatches must raise structured validation errors.
- Region activation on an unknown region must fail deterministically.
- Coarse-state update failures must identify the failing region and subsystem in the tick result or raised exception.

## 9. Integration Points
- Session creation and `/scene/enter` flow consume realized active-region snapshots.
- Save/load stores and restores the kernel snapshot instead of legacy ad hoc world state.
- `/world-state`, `/history`, `/factions`, and `/map` routes read from the kernel snapshot and realized snapshots.

## 10. Test Coverage Target
- Minimum 95% coverage on snapshot and global tick helpers.
- Required targeted suites: `test_global_tick_runtime.py` and `test_world_snapshot_save_load.py`.

## Changelog
- 2026-03-27: Initial PRD for live always-global runtime behavior.

# PRD: World Simulation Architecture v1
**Project:** Ember RPG  
**Phase:** 0-1  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Draft  

---

## 1. Purpose
Define the canonical world simulation kernel for Ember RPG. The kernel must generate and evolve deterministic procedural worlds from macro geology down to playable regions, while remaining genre-agnostic through content adapters and supporting a fantasy-medieval Ember adapter as the first shipped pack.

## 2. Scope
- In scope: deterministic pipeline stages, canonical world datatypes, adapter architecture, region realization contract, global ticking contract, and snapshot/save boundaries.
- Out of scope: Godot presentation, DM narration prose, and a sci-fi adapter implementation in v1.

## 3. Functional Requirements (FR)
FR-01: The world kernel must expose a staged deterministic pipeline: `generate_world`, `seed_species`, `seed_civilizations`, `simulate_history`, `realize_region`, and `tick_global`.
FR-02: Each pipeline stage must accept and return canonical world datatypes without mutating unrelated stage outputs.
FR-03: The same `seed` and `profile_id` must produce identical canonical world outputs across runs on the same code revision.
FR-04: The kernel must support content adapters that map kernel-native species, cultures, tags, and institutions into setting-specific content without modifying kernel logic.
FR-05: The runtime must support always-global advancement through multiresolution simulation: active regions resolve fine state, inactive regions resolve coarse state.
FR-06: The kernel must produce serializable snapshots suitable for save/load without re-running worldgen RNG.
FR-07: Region realization must consume macro state and produce a playable `RegionSnapshot` rather than independent handcrafted map logic.
FR-08: The first adapter pack must target fantasy-medieval Ember while keeping kernel interfaces neutral enough to support a later sci-fi adapter.

## 4. Data Structures
```python
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

@dataclass
class WorldBlueprint:
    seed: int
    profile_id: str
    width: int
    height: int
    tectonic_plates: list[dict]
    elevation: list[list[float]]
    temperature: list[list[float]]
    moisture: list[list[float]]
    drainage: list[list[float]]
    biomes: list[list[str]]
    regions: list[dict]
    species_lineages: list[dict]
    factions: list[dict]
    settlements: list[dict]
    historical_events: list[dict]
    simulation_snapshot: dict

@dataclass
class RegionSnapshot:
    region_id: str
    biome_id: str
    width: int
    height: int
    terrain: list[list[str]]
    structures: list[dict]
    entities: list[dict]
    metadata: dict

@dataclass
class GlobalTickResult:
    hours: int
    updated_regions: list[str]
    generated_events: list[dict]
    new_snapshot: dict
```

## 5. Public API
```python
def generate_world(seed: int, profile_id: str) -> WorldBlueprint
def seed_species(world: WorldBlueprint) -> WorldBlueprint
def seed_civilizations(world: WorldBlueprint) -> WorldBlueprint
def simulate_history(world: WorldBlueprint, end_year: int | None = None) -> WorldBlueprint
def realize_region(world: WorldBlueprint, region_id: str, detail_level: str = "settlement") -> RegionSnapshot
def tick_global(world: WorldBlueprint, hours: int) -> GlobalTickResult
```
- Preconditions: `profile_id` must resolve to a valid registry entry; `world` must be a valid output of the previous stage; `region_id` must exist in `world.regions`.
- Postconditions: outputs remain JSON-serializable and deterministic for their inputs.
- Exceptions: invalid profile IDs, invalid stage ordering, unknown region IDs, and negative tick hours must raise `ValueError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: The canonical six-stage pipeline exists in code and is importable from a single `engine.worldgen` package.
AC-02 [FR-03]: Two calls to `generate_world(42, "standard")` produce identical `WorldBlueprint` serializations.
AC-03 [FR-04]: The fantasy Ember adapter can map at least humans, dwarves, elves, and dragons from kernel-native tags without changing kernel logic.
AC-04 [FR-05]: `tick_global` updates both active and inactive regions in one call and records which regions changed.
AC-05 [FR-06]: A `WorldBlueprint` can round-trip through a dict snapshot without re-running generation.
AC-06 [FR-07]: `realize_region` returns a `RegionSnapshot` whose metadata references the originating macro region and settlement.

## 7. Performance Requirements
- `generate_world` for a standard profile must complete in under 500 ms on developer hardware.
- `seed_species` plus `seed_civilizations` must complete in under 300 ms combined for the standard profile.
- `simulate_history` for the standard profile must complete in under 2 seconds for the default `history_end_year`.
- `tick_global(world, 24)` must complete in under 250 ms for the standard profile using multiresolution simulation.

## 8. Error Handling
- Invalid registries or malformed adapter data must fail fast during load.
- Realization failures must surface a deterministic error with the offending `region_id` and stage name.
- Snapshot loading must reject missing required fields instead of silently re-generating them.
- Unsupported adapter tags must degrade to neutral kernel tags only if the adapter explicitly declares a fallback.

## 9. Integration Points
- Session creation uses `generate_world` through `simulate_history` before the first playable region is entered.
- Save/load uses `WorldBlueprint` and `simulation_snapshot` as authoritative world state.
- Map and world-state API routes expose `RegionSnapshot` and global event data derived from the kernel.
- Terminal and Godot clients consume realized region snapshots rather than legacy standalone town generators.

## 10. Test Coverage Target
- Minimum 95% coverage on the new `engine.worldgen` package entrypoints.
- Required targeted suites: `test_world_profiles.py`, `test_world_snapshot_save_load.py`, and any stage-specific API tests.

## Changelog
- 2026-03-27: Initial architecture PRD created as the master document for the world simulation rewrite.

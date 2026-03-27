# PRD: Geology and Climate World Generation v1
**Project:** Ember RPG  
**Phase:** 2  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Draft  

---

## 1. Purpose
Generate a deterministic macro world from tectonic and climate rules so that mountains, oceans, coasts, wetlands, rivers, deserts, glaciers, and temperate belts emerge from explainable inputs rather than ad hoc stamped patterns.

## 2. Scope
- In scope: world profiles, tectonic plates, elevation fields, hydrology, latitude-driven temperature, moisture transport, drainage, and biome precursor fields.
- Out of scope: species placement, civilizations, local furniture/building placement, and presentation logic.

## 3. Functional Requirements (FR)
FR-01: The geology stage must partition the world into tectonic plates with deterministic motion vectors derived from `seed` and `profile_id`.
FR-02: Plate boundaries must influence elevation so convergent edges bias mountains and divergent edges bias rifts, coasts, and inland basins.
FR-03: The climate stage must compute temperature from latitude, elevation, and profile modifiers.
FR-04: The moisture stage must compute humidity from water adjacency, prevailing winds, and rain-shadow effects.
FR-05: Drainage and runoff must derive rivers and wetlands from elevation and moisture fields rather than random placement.
FR-06: The geology stage must produce explainability metadata for each region, including dominant plate interaction, water access, and climate drivers.
FR-07: The macro stage must output values needed by downstream biome, ecology, and settlement stages without re-derivation.
FR-08: Generation must remain deterministic and bounded by the chosen world profile dimensions.

## 4. Data Structures
```python
@dataclass
class TectonicPlate:
    id: str
    cells: list[tuple[int, int]]
    drift_x: float
    drift_y: float
    crust_type: str

@dataclass
class MacroRegionClimate:
    elevation: float
    temperature: float
    moisture: float
    drainage: float
    water_access: str
    boundary_type: str
```

## 5. Public API
```python
def build_tectonic_plates(seed: int, profile: WorldProfile) -> list[TectonicPlate]
def compute_elevation(profile: WorldProfile, plates: list[TectonicPlate]) -> list[list[float]]
def compute_temperature(profile: WorldProfile, elevation: list[list[float]]) -> list[list[float]]
def compute_moisture(profile: WorldProfile, elevation: list[list[float]], temperature: list[list[float]]) -> list[list[float]]
def compute_drainage(elevation: list[list[float]], moisture: list[list[float]]) -> tuple[list[list[float]], list[dict]]
```
- Preconditions: profile dimensions must be positive; plate count must be at least 2.
- Postconditions: all returned grids match profile dimensions.
- Exceptions: invalid profile values raise `ValueError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: For a fixed seed and profile, the generated plate IDs and motion vectors are identical across runs.
AC-02 [FR-02]: A standard-profile world contains both high-elevation mountainous cells and low-elevation basin or coastal cells caused by boundary logic.
AC-03 [FR-03]: Polar or high-latitude cells are colder than equatorial cells in the same elevation band.
AC-04 [FR-04]: Leeward regions behind high mountain bands have lower moisture than equivalent windward regions.
AC-05 [FR-05]: River origin cells occur on higher ground than their terminal destination cells.
AC-06 [FR-06]: Every region includes explainability metadata naming at least one terrain and one climate driver.

## 7. Performance Requirements
- Standard-profile tectonic, climate, and drainage generation must complete in under 500 ms combined.
- No stage may allocate unbounded data relative to `world_width * world_height`.

## 8. Error Handling
- Profiles with zero dimensions, invalid plate counts, or impossible wind definitions must raise `ValueError`.
- Drainage cycles detected in river tracing must break deterministically and record a repair note in metadata.
- If a profile cannot produce minimum ocean coverage, the generator must fail with a deterministic validation error rather than silently mutating the profile.

## 9. Integration Points
- Supplies `WorldBlueprint` macro fields for biome classification.
- Supplies explainability metadata for DM context, debug tools, and QA.
- Supplies terrain drivers used by region realization and settlement viability scoring.

## 10. Test Coverage Target
- Minimum 95% coverage on geology/climate generation helpers.
- Required targeted suite: `test_geology_climate.py`.

## Changelog
- 2026-03-27: Initial PRD for the macro geology and climate stage.

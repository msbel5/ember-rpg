# PRD: Biomes and Ecology Distribution v1
**Project:** Ember RPG  
**Phase:** 3  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Draft  

---

## 1. Purpose
Transform geology and climate outputs into ecological layers: biomes, resource fields, habitat suitability, fauna ranges, apex pressure, and domestication pools that can later feed civilizations and local region realization.

## 2. Scope
- In scope: biome classification, ecological suitability, fauna placement, resource availability, species distribution inputs, and domestication candidates.
- Out of scope: cultural adaptation, historical institutions, or local building layouts.

## 3. Functional Requirements (FR)
FR-01: Biome assignment must derive from temperature, moisture, elevation, drainage, and water access rather than random tags.
FR-02: Each biome registry entry must define terrain weights, renewable resources, fauna pools, climate bounds, and settlement modifiers.
FR-03: Ecology must compute habitat suitability for each species template against each macro region.
FR-04: Wildlife distribution must respect biome suitability, travel corridors, and apex-prey balance.
FR-05: Domestication pools must identify species suitable for food, labor, transport, companionship, or magical use.
FR-06: Resource abundance must vary by biome and geology, enabling later industry and settlement differences.
FR-07: The output must be deterministic and directly consumable by species and civilization seeding.

## 4. Data Structures
```python
@dataclass
class BiomeDefinition:
    id: str
    temperature_range: tuple[float, float]
    moisture_range: tuple[float, float]
    elevation_range: tuple[float, float]
    terrain_weights: dict[str, int]
    resources: list[str]
    fauna: list[str]
    settlement_weight: float

@dataclass
class HabitatScore:
    species_id: str
    region_id: str
    score: float
    reasons: list[str]
```

## 5. Public API
```python
def assign_biomes(world: WorldBlueprint, biome_registry: dict[str, BiomeDefinition]) -> WorldBlueprint
def score_species_habitats(world: WorldBlueprint, species_registry: dict[str, dict]) -> dict[str, list[HabitatScore]]
def distribute_wildlife(world: WorldBlueprint, habitat_scores: dict[str, list[HabitatScore]]) -> WorldBlueprint
def identify_domestication_pools(world: WorldBlueprint) -> WorldBlueprint
```
- Preconditions: macro world fields and biome registries must be loaded.
- Postconditions: every region receives a valid biome and resource/fauna payload.
- Exceptions: unknown biome IDs and impossible suitability calculations must raise `ValueError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Hot, dry inland regions classify differently from cool, wet coastal regions under the same profile.
AC-02 [FR-02]: Every biome used in a generated world resolves to a registry definition with terrain, resources, and fauna.
AC-03 [FR-03]: A species with incompatible climate bounds receives a non-positive habitat score outside its viable regions.
AC-04 [FR-04]: Apex fauna do not occupy every viable region when prey support is absent.
AC-05 [FR-05]: The standard fantasy pack identifies at least one mount species and one livestock species when the ecology supports them.
AC-06 [FR-06]: Resource output differs between at least two biome families in the same world.

## 7. Performance Requirements
- Biome assignment plus habitat scoring for the standard profile must complete in under 400 ms.
- Wildlife distribution must scale linearly with region count and species count.

## 8. Error Handling
- Missing biome definitions must abort generation with the unresolved biome ID.
- Invalid climate bounds in registries must fail registry validation before runtime generation.
- Empty fauna/resource results are allowed only if the biome definition explicitly declares them.

## 9. Integration Points
- Uses outputs from the geology/climate stage.
- Feeds species seeding, civilization viability, and region realization terrain/resource choices.
- Supplies data for crafting, economy, and encounter tables downstream.

## 10. Test Coverage Target
- Minimum 95% coverage on biome assignment and ecology distribution helpers.
- Required targeted suite: `test_biome_distribution.py`.

## Changelog
- 2026-03-27: Initial PRD for biome and ecology distribution.

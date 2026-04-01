# PRD: Region Realization and Settlement Generation v1
**Project:** Ember RPG  
**Phase:** 5  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Draft  

---

## 1. Purpose
Realize a macro region into a playable 80x60 snapshot by translating biome, ecology, settlement history, and faction ownership into terrain, roads, buildings, furniture, NPC placement, and typed local map data.

## 2. Scope
- In scope: 80x60 settlement/wilderness realization, organic road networks, town square generation, door placement, furniture placement, building-to-NPC linking, and typed tile output.
- Out of scope: client rendering, combat effects, and off-region world simulation.

## 3. Functional Requirements (FR)
FR-01: `realize_region` must generate an 80x60 playable map for settlement and wilderness detail levels.
FR-02: Settlement road networks must be organic, consisting of a main road, branches, and local paths rather than a fixed grid.
FR-03: Every building must originate from a building template and include at least one door facing an adjacent road or path.
FR-04: Furniture placement must honor building templates and required workstation/furnishing positions.
FR-05: NPCs and interactable anchors must spawn inside or directly adjacent to their linked building or site.
FR-06: Settlement centers must include a town square with a well, fountain, or equivalent center feature.
FR-07: Terrain typing must reflect macro biome context, including vegetation, water, rough terrain, and developed ground.
FR-08: The realized output must be deterministic for the same world, region ID, and detail level.

## 4. Data Structures
```python
@dataclass
class SettlementLayout:
    width: int
    height: int
    terrain_tiles: list[list[str]]
    road_tiles: list[tuple[int, int]]
    buildings: list[dict]
    furniture: list[dict]
    npc_spawns: list[dict]
    center_feature: dict

@dataclass
class RegionSnapshot:
    region_id: str
    biome_id: str
    layout: SettlementLayout
    typed_tiles: list[list[dict]]
    metadata: dict
```

## 5. Public API
```python
def realize_region(world: WorldBlueprint, region_id: str, detail_level: str = "settlement") -> RegionSnapshot
def generate_settlement_layout(world: WorldBlueprint, region_id: str) -> SettlementLayout
def validate_region_snapshot(snapshot: RegionSnapshot) -> list[str]
```
- Preconditions: the region must exist and, for settlement detail, contain at least one settlement seed.
- Postconditions: every typed tile is serializable and references valid terrain/structure identifiers.
- Exceptions: unknown region IDs or invalid building templates raise `ValueError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: A settlement realization returns an 80x60 snapshot with typed tiles.
AC-02 [FR-02]: The road network is not a regular every-Nth-row/every-Nth-column grid.
AC-03 [FR-03]: Every building has at least one door tile adjacent to a road or path tile.
AC-04 [FR-04]: A blacksmith-style building contains forge/anvil/workbench furniture when the template requires them.
AC-05 [FR-05]: NPC spawns reference valid buildings and do not land inside blocking walls.
AC-06 [FR-06]: The town center contains a center feature and open square footprint.
AC-07 [FR-07]: A swamp or coast region yields different terrain typing from a mountain or plains region.
AC-08 [FR-08]: Re-realizing the same region with the same inputs produces identical snapshot serialization.

## 7. Performance Requirements
- Settlement realization for a single region must complete in under 300 ms.
- Snapshot validation must complete in under 50 ms.

## 8. Error Handling
- If building placement cannot satisfy door/road constraints, realization must fail deterministically and report the building template ID.
- Invalid furniture anchors must fail validation before snapshot output.
- If no settlement exists in a region requested at settlement detail, `realize_region` must raise `ValueError` instead of generating a fake town.

## 9. Integration Points
- Consumes macro region, settlement, faction, and biome outputs from earlier stages.
- Produces local map data for `/map` APIs and both terminal and Godot clients.
- Replaces the standalone legacy `TownGenerator` path over time.

## 10. Test Coverage Target
- Minimum 95% coverage on settlement realization and validation helpers.
- Required targeted suites: `test_region_realization.py` and `test_settlement_layout.py`.

## Changelog
- 2026-03-27: Initial PRD for macro-to-local region realization.

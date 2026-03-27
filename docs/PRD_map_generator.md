# PRD: Tile Map Generator (Legacy Reference)
**Project:** Ember RPG  
**Phase:** Legacy  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-27  
**Status:** Legacy Reference  

---

## 1. Purpose
This document describes the legacy dungeon/town/wilderness generator that remains in the repo as a temporary implementation anchor. It is no longer the forward-looking map generation specification.

## 2. Scope
- In scope: documenting the current legacy `engine.map` behavior until migration completes.
- Out of scope: defining the new macro-to-region realization pipeline.

## 3. Functional Requirements (FR)
FR-01: The active forward design for world and settlement generation must come from the new world simulation PRDs.
FR-02: Legacy `engine.map` tests may remain as temporary anchors only until the hard-replace migration is complete.

## 4. Data Structures
```python
class LegacyMapGeneratorReference:
    module: str = "engine.map"
    superseded_runtime: str = "engine.worldgen"
```

## 5. Public API
The legacy API remains:
- `DungeonGenerator.generate(width, height)`
- `TownGenerator.generate(width, height)`
- `WildernessGenerator.generate(width, height)`

The replacement canonical API is specified in:
- `docs/PRD_world_simulation_architecture_v1.md`
- `docs/PRD_region_realization_and_settlement_generation_v1.md`

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: A reader can locate the replacement PRDs from this document.
AC-02 [FR-02]: The file clearly states that legacy map tests are temporary anchors, not long-term contracts.

## 7. Performance Requirements
Legacy only. See the replacement PRDs for future budgets.

## 8. Error Handling
If the legacy map generator behavior conflicts with the replacement worldgen PRDs, the replacement PRDs govern new implementation work.

## 9. Integration Points
- Temporary anchor for `frp-backend/tests/test_map.py`
- Replaced over time by `engine.worldgen` pipeline outputs

## 10. Test Coverage Target
Maintain current legacy coverage until migration removes the old generator.

## Changelog
- 2026-03-27: Narrowed to a legacy reference. New development should target the world simulation PRD pack.

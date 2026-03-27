# PRD: Procedural World Generation v2 (Superseded)
**Project:** Ember RPG  
**Phase:** Legacy  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-27  
**Status:** Superseded  

---

## 1. Purpose
This document is retained only as a historical note for the previous town/world generation direction. The active procedural world generation design now lives in the 2026-03-27 world simulation PRD pack.

## 2. Scope
- In scope: pointing readers to the replacement PRDs.
- Out of scope: defining new town generation or macro world generation behavior.

## 3. Functional Requirements (FR)
FR-01: New world generation work must use the replacement module PRDs instead of this document.
FR-02: Legacy grid-town assumptions are not normative after 2026-03-27.

## 4. Data Structures
```python
class LegacyWorldgenReference:
    replaced_by: list[str]
    legacy_scope: str
```

## 5. Public API
Use these replacement specifications:
- `docs/PRD_geology_climate_worldgen_v1.md`
- `docs/PRD_biomes_ecology_distribution_v1.md`
- `docs/PRD_region_realization_and_settlement_generation_v1.md`

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: The replacement PRDs exist and cover macro generation, ecology, and realization.
AC-02 [FR-02]: This file does not present legacy town generation as the active direction.

## 7. Performance Requirements
Not applicable.

## 8. Error Handling
If any statement in this file conflicts with the replacement PRDs, the replacement PRDs take precedence.

## 9. Integration Points
- Superseded by the world simulation architecture and module PRDs dated 2026-03-27.

## 10. Test Coverage Target
No runtime coverage target.

## Changelog
- 2026-03-27: Marked superseded by the world simulation PRD pack.

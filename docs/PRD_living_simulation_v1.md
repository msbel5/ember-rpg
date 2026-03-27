# PRD: Living World Simulation v1 (Superseded)
**Project:** Ember RPG  
**Phase:** Legacy  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-27  
**Status:** Superseded  

---

## 1. Purpose
This document remains as a legacy reference for the first living-world slice. It is no longer the source of truth for new world simulation work.

## 2. Scope
- In scope: historical context for the old living-world plan.
- Out of scope: current implementation guidance.

## 3. Functional Requirements (FR)
FR-01: New work must not use this document as the implementation source of truth.
FR-02: The canonical replacement set must live in the `PRD_world_*_v1.md` module family created on 2026-03-27.

## 4. Data Structures
```python
class LegacyReference:
    superseded_by: list[str]
    retained_for: str
```

## 5. Public API
There is no public runtime API in this legacy reference. Use:
- `docs/PRD_world_simulation_architecture_v1.md`
- `docs/PRD_live_global_simulation_runtime_v1.md`
- `docs/PRD_region_realization_and_settlement_generation_v1.md`

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Engineers can identify this document as superseded from the header and Purpose section.
AC-02 [FR-02]: The replacement PRD family exists and is discoverable from this file.

## 7. Performance Requirements
Not applicable. This document is not executable guidance.

## 8. Error Handling
If this file conflicts with the new module PRDs, the new module PRDs win.

## 9. Integration Points
- Superseded by the 2026-03-27 world simulation PRD pack.

## 10. Test Coverage Target
No direct runtime coverage target. Documentation review only.

## Changelog
- 2026-03-27: Marked superseded by the world simulation PRD pack.

# PRD: Implementation Matrix
**Project:** Ember RPG  
**Phase:** 0  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Active  

---

## 1. Purpose
Define which product docs are authoritative for the shipable demo recovery effort, which legacy docs are superseded, and which docs are non-blocking reference material. This prevents overlapping PRDs from quietly competing with the recovery plan.

## 2. Scope
- In scope: demo-blocking PRDs, onboarding/creation docs, campaign/runtime docs, client UX docs, and save/load docs.
- Out of scope: code changes, runtime data migrations, and feature work not required to resolve the demo blocker.

## 3. Functional Requirements
FR-01: Every demo-blocking PRD SHALL be classified as `Authoritative`, `Superseded`, or `Non-blocking`.
FR-02: Authoritative docs SHALL describe the active implementation target for the demo recovery plan.
FR-03: Superseded docs SHALL remain readable but SHALL NOT be used as the source of truth for implementation.
FR-04: Non-blocking docs SHALL be explicitly allowed to drift relative to the demo recovery plan.
FR-05: The matrix SHALL include the current Godot client, character system, game flow, save/load, and campaign runtime docs.
FR-06: The matrix SHALL note the implementation owner area for each authoritative doc.

## 4. Data Structures
```python
class DocStatus(str):
    AUTHORITATIVE = "Authoritative"
    SUPERSEDED = "Superseded"
    NON_BLOCKING = "Non-blocking"

@dataclass
class DocEntry:
    path: str
    status: DocStatus
    owner: str
    note: str
```

## 5. Public API
This document has no runtime API. The operational contract is manual:
- Read this matrix before changing any demo-facing doc.
- Update this matrix whenever a PRD is rewritten, retired, or promoted to authoritative.

## 6. Acceptance Criteria
AC-01 [FR-01]: The matrix contains an explicit status for each demo-blocking doc.
AC-02 [FR-02]: The active client, character, game flow, save/load, and campaign docs are marked authoritative where they support the recovery plan.
AC-03 [FR-03]: Legacy world/living-simulation docs are marked superseded when they conflict with the recovery plan.
AC-04 [FR-04]: Non-blocking reference docs are listed separately and are not treated as implementation blockers.
AC-05 [FR-05]: The matrix includes `PRD_godot_client.md`, `PRD_character_system.md`, `PRD_game_flow_architecture.md`, `PRD_save_load.md`, and the campaign/world docs.
AC-06 [FR-06]: Each authoritative entry states the subsystem it owns.

## 7. Performance Requirements
- Doc lookup should be immediate during planning and implementation reviews.
- The matrix must stay short enough to read in one pass.

## 8. Error Handling
- If a doc is missing from the matrix, treat it as non-authoritative until classified.
- If two docs claim the same authoritative behavior, prefer the newer recovery-plan-aligned doc and mark the older one superseded.

## 9. Integration Points
- `docs/PRD_godot_client.md`
- `docs/PRD_game_flow_architecture.md`
- `docs/PRD_character_system.md`
- `docs/PRD_save_load.md`
- `docs/PRD_campaign_generator.md`
- `docs/PRD_living_simulation_v1.md`
- `docs/PRD_world_generation_v2.md`

## 10. Test Coverage Target
- Manual review only. The matrix is validated by doc consistency checks during implementation review.

## Changelog
- 2026-03-27: Initial implementation matrix for the shipable demo recovery plan.

## Doc Classifications

### Authoritative
- `docs/PRD_godot_client.md` - current client recovery target, including creation wizard, gameplay panels, and clickability.
- `docs/PRD_character_system.md` - canonical character creation, stats, alignment, proficiencies, and character sheet shape.
- `docs/PRD_game_flow_architecture.md` - player-facing onboarding, scene reveal, and interaction model for the playable demo.
- `docs/PRD_save_load.md` - current save/load persistence contract.
- `docs/PRD_campaign_generator.md` - quest and campaign progression logic that remains active in the demo stack.
- `docs/PRD_rimworld_benchmark_v1.md` - benchmark rubric for the final demo review.

### Superseded
- `docs/PRD_living_simulation_v1.md` - legacy high-level world simulation draft.
- `docs/PRD_world_generation_v2.md` - legacy worldgen draft superseded by the newer world simulation PRDs.
- `docs/PRD_map_generator.md` - legacy map layout draft superseded by region realization PRDs.
- `docs/PRD_topdown_living_world_v1.md` - legacy top-down world draft.
- `docs/PRD_living_world_v1.md` - legacy living-world draft.

### Non-blocking
- `docs/PRD_dm_agent.md`
- `docs/PRD_npc_memory.md`
- `docs/PRD_magic_system.md`
- `docs/PRD_combat_engine.md`
- `docs/PRD_item_system.md`
- `docs/PRD_progression_system.md`
- `docs/PRD_websocket.md`
- `docs/PRD_world_state.md`
- `docs/PRD_consequence_system.md`
- `docs/PRD_biomes_ecology_distribution_v1.md`
- `docs/PRD_geology_climate_worldgen_v1.md`
- `docs/PRD_world_simulation_architecture_v1.md`
- `docs/PRD_world_data_registries_v1.md`

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
- In scope: demo-blocking PRDs, onboarding/creation docs, campaign/runtime docs, client UX docs, save/load docs, recovery checklists, and canonical kernel PRDs.
- Out of scope: code changes, runtime data migrations, and feature work not required to resolve the demo blocker.

## 3. Functional Requirements
FR-01: Every demo-blocking PRD SHALL be classified as `Authoritative`, `Superseded`, or `Non-blocking`.
FR-02: Authoritative docs SHALL describe the active implementation target for the demo recovery plan.
FR-03: Superseded docs SHALL remain readable but SHALL NOT be used as the source of truth for implementation.
FR-04: Non-blocking docs SHALL be explicitly allowed to drift relative to the demo recovery plan.
FR-05: The matrix SHALL include the current Godot client, character system, game flow, save/load, campaign runtime docs, and canonical kernel PRDs.
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
- `docs/PRD_creation_surface_v2.md`
- `docs/PRD_automation_authority_v1.md`
- `docs/PRD_actor_kernel_v1.md`
- `docs/PRD_material_item_kernel_v1.md`
- `docs/PRD_body_injury_combat_v1.md`
- `docs/PRD_world_state_kernel_v1.md`
- `docs/PRD_history_and_factions_v1.md`
- `docs/PRD_job_reaction_kernel_v1.md`
- `docs/PRD_colony_simulation_v1.md`
- `docs/PRD_hybrid_commander_loop_v1.md`
- `docs/architecture/runtime_authority.md`
- `docs/architecture/creation_state_machine.md`
- `docs/architecture/automation_stack.md`
- `docs/architecture/reference_notes.md`
- `docs/qa/recovery_checklist.md`
- `docs/qa/df_mechanism_checklist.md`
- `docs/PRD_living_simulation_v1.md`
- `docs/PRD_world_generation_v2.md`

## 10. Test Coverage Target
- Manual review only. The matrix is validated by doc consistency checks during implementation review.

## Changelog
- 2026-04-01c: Synced authoritative runtime docs with the canonical `kernel_world_state` / `kernel_game_state` save/load contract, promoted creation and automation authority docs after fresh headless and automation proof, and refreshed the recovery/DF checklists.
- 2026-04-01b: Added 10 GemRB-synthesis PRDs: spell_system, projectile_system, item_system_kernel, store_trade, level_progression, dialog_system, gamescript_ai, pathfinding, area_map, game_state. All 16 GemRB mechanisms now have authoritative PRDs.
- 2026-04-01a: Added 7 new authoritative PRDs (effect_system, combat_resolution, medical_system, systems_closure, colony_v2, job_v2). Superseded colony_v1 and job_v1. Updated all sparse kernel PRDs with dataclass definitions and algorithms.
- 2026-03-27: Initial implementation matrix for the shipable demo recovery plan.

## Doc Classifications

### Authoritative
- `docs/PRD_godot_client.md` - current client recovery target, including creation wizard, gameplay panels, and clickability.
- `docs/PRD_character_system.md` - canonical character creation, stats, alignment, proficiencies, and character sheet shape.
- `docs/PRD_game_flow_architecture.md` - player-facing onboarding, scene reveal, and interaction model for the playable demo.
- `docs/PRD_save_load.md` - current save/load persistence contract.
- `docs/PRD_campaign_generator.md` - quest and campaign progression logic that remains active in the demo stack.
- `docs/PRD_rimworld_benchmark_v1.md` - benchmark rubric for the final demo review.
- `docs/PRD_creation_surface_v2.md` - authoritative Sprint 0 creation-unblock contract for the title-screen creation workspace.
- `docs/PRD_automation_authority_v1.md` - authoritative QA and automation contract for Godot bridge vs Win32 fallback.
- `docs/PRD_actor_kernel_v1.md` - authoritative root actor model for player, NPC, and creature unification.
- `docs/PRD_material_item_kernel_v1.md` - authoritative typed material, item, equipment, and wear baseline.
- `docs/PRD_body_injury_combat_v1.md` - authoritative typed body, wound, and early deterministic combat baseline.
- `docs/PRD_world_state_kernel_v1.md` - authoritative typed macro-world graph and region/site/faction state baseline.
- `docs/PRD_history_and_factions_v1.md` - authoritative typed history and faction linkage baseline.
- `docs/PRD_job_reaction_kernel_v1.md` - authoritative typed work, recipe, and worksite baseline.
- `docs/PRD_colony_simulation_v1.md` - authoritative typed need, schedule, supply, and pressure baseline.
- `docs/PRD_hybrid_commander_loop_v1.md` - authoritative contract for macro travel and local commander play sharing one world tick.
- `docs/PRD_effect_system_v1.md` - authoritative unified buff/debuff/condition pipeline synthesizing GemRB opcodes and DF syndromes.
- `docs/PRD_combat_resolution_v1.md` - authoritative complete combat pipeline synthesizing GemRB THAC0/AC and DF tissue/material physics.
- `docs/PRD_medical_system_v1.md` - authoritative medical treatment pipeline from DF M05 (diagnosis, treatment, infection, recovery).
- `docs/PRD_systems_closure_v1.md` - authoritative Sprint 5 baseline for syndromes, power networks, traps, fluids, temperature, strange moods.
- `docs/PRD_colony_simulation_v2.md` - authoritative colony pressure, morale cascades, production workflows, quest hook generation.
- `docs/PRD_job_reaction_kernel_v2.md` - authoritative job/reaction pipeline, skill XP, skill rust, labor assignment.
- `docs/PRD_spell_system_v1.md` - authoritative spell casting pipeline (GemRB M05): memorization, casting time, interruption, spell failure, magic resistance.
- `docs/PRD_projectile_system_v1.md` - authoritative projectile/missile system (GemRB M12): 6 types (arrow, fireball, cone, bounce, traveling), AoE, friend/foe.
- `docs/PRD_item_system_kernel_v1.md` - authoritative item system (GemRB M07): weapon headers, equip effects, requirements, wear, identification, stacking.
- `docs/PRD_store_trade_v1.md` - authoritative store/trade system (GemRB M13): buy/sell, CHA pricing, depreciation, steal, temple/inn services, colony trade.
- `docs/PRD_level_progression_v1.md` - authoritative level/progression system (GemRB M15): XP, class tables, HP, BAB, saves, proficiency, ability increase, DF skill learning.
- `docs/PRD_dialog_system_v1.md` - authoritative dialog system (GemRB M09): state/transition trees, conditions, actions, journal, CHA gates, multi-dialog jump.
- `docs/PRD_gamescript_ai_v1.md` - authoritative AI scripting system (GemRB M08): trigger/action blocks, 30 core triggers, 30 core actions, script slots, shout.
- `docs/PRD_pathfinding_v1.md` - authoritative pathfinding system (GemRB M11 + DF M15): A*, actor size, terrain cost, bumping, random walk, doors.
- `docs/PRD_area_map_v1.md` - authoritative area/map system (GemRB M10 + DF M16): regions, containers, doors, spawns, day/night, rooms, fog of war.
- `docs/PRD_game_state_v1.md` - authoritative game state system (GemRB M16): party, areas, variables, journal, time, reputation, difficulty, save/load.
- `docs/architecture/runtime_authority.md` - authoritative runtime boundary between macro world graph, active local map, campaign runtime, and client state.
- `docs/architecture/creation_state_machine.md` - authoritative creation flow from identity through questionnaire, rolled pool assignment, summary, and finalize.
- `docs/architecture/automation_stack.md` - authoritative QA/tooling stack for Godot automation, recording, and desktop fallback.
- `docs/architecture/reference_notes.md` - authoritative high-level reference translation notes for Dwarf Fortress and RimWorld concepts.
- `docs/qa/recovery_checklist.md` - authoritative sprint-state and evidence tracker for the recovery program.
- `docs/qa/df_mechanism_checklist.md` - authoritative DF-inspired mechanism coverage map and dependency guardrail checklist.

### Superseded
- `docs/PRD_living_simulation_v1.md` - legacy high-level world simulation draft.
- `docs/PRD_world_generation_v2.md` - legacy worldgen draft superseded by the newer world simulation PRDs.
- `docs/PRD_map_generator.md` - legacy map layout draft superseded by region realization PRDs.
- `docs/PRD_topdown_living_world_v1.md` - legacy top-down world draft.
- `docs/PRD_living_world_v1.md` - legacy living-world draft.
- `docs/PROMPT_deterministic_world_v1.md` - historical planning prompt; no longer authoritative after the tooling-first architecture reset docs landed.
- `docs/PRD_colony_simulation_v1.md` - superseded by v2 which adds full pressure algorithms, morale cascades, production workflows.
- `docs/PRD_job_reaction_kernel_v1.md` - superseded by v2 which adds ReactionDef schema, skill XP formulas, labor assignment.

### Superseded (by new GemRB synthesis PRDs)
- `docs/PRD_magic_system.md` - superseded by PRD_spell_system_v1.md
- `docs/PRD_combat_engine.md` - superseded by PRD_combat_resolution_v1.md
- `docs/PRD_item_system.md` - superseded by PRD_item_system_kernel_v1.md
- `docs/PRD_progression_system.md` - superseded by PRD_level_progression_v1.md

### Non-blocking
- `docs/PRD_dm_agent.md`
- `docs/PRD_npc_memory.md`
- `docs/PRD_websocket.md`
- `docs/PRD_world_state.md`
- `docs/PRD_consequence_system.md`
- `docs/PRD_biomes_ecology_distribution_v1.md`
- `docs/PRD_geology_climate_worldgen_v1.md`
- `docs/PRD_world_simulation_architecture_v1.md`
- `docs/PRD_world_data_registries_v1.md`

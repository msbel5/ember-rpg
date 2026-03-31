# DF-Inspired Mechanism Checklist
**Date:** 2026-04-01  
**Status:** Active  

This checklist translates the supplied DF-style mechanism framework into Ember RPG's recovery program. It is a coverage map and rollout contract, not a copy plan. Every mechanism below must be implemented in a genre-agnostic Ember form while preserving the dependency graph between systems.

## Completion Rule
A mechanism is not complete until all four are true:
- a PRD exists
- a typed canonical runtime surface exists
- targeted tests exist
- its upstream and downstream mechanism links are preserved in code or adapter notes

## Mechanism Rollout Matrix
| ID | Mechanism | Primary Sprint | Authoritative Surface | Key Runtime Types | Depends On | Feeds | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M01 | Combat | Sprint 1 | `docs/PRD_body_injury_combat_v1.md`, `docs/PRD_material_item_kernel_v1.md` | `BodyState`, `WoundRecord`, `MaterialDef`, `EquipmentLoadout`, `StrikeResolution` | M02, M17, actor kernel | M03, M05, M06 | Typed runtime plus live strike-path integration |
| M02 | Skill / Learning | Sprint 3 | `docs/PRD_actor_kernel_v1.md`, `docs/PRD_job_reaction_kernel_v1.md` | actor skill state, future learning ledger | M04 | M01, M04, M13 | PRD seed |
| M03 | Need / Happiness / Stress | Sprint 3 | `docs/PRD_colony_simulation_v1.md`, `docs/PRD_actor_kernel_v1.md` | `NeedState`, future stress/thought state | M01, M05, M12, M17, colony loop | M04, M13, breakdown behavior | PRD written |
| M04 | Job / Task Assignment | Sprint 3 | `docs/PRD_job_reaction_kernel_v1.md` | `JobRecord`, `ReactionDef`, `WorksiteRecord` | M02, M15, item availability | M02, M05, M16, M19 | PRD written |
| M05 | Medical | Sprint 1 then Sprint 3 | `docs/PRD_body_injury_combat_v1.md`, later job/colony PRDs | `WoundRecord`, future treatment records | M01, M04 | M03, actor recovery | Wound hooks live, treatment pending |
| M06 | Syndrome / Poison | Post Sprint 1 expansion | `docs/PRD_body_injury_combat_v1.md` plus future condition PRD | `ConditionRecord`, future syndrome defs | M01, M09 | M01, M03 | Planned |
| M07 | Machine / Power | Post Sprint 3 | future infra PRD | power network records | M04, M16 | M08, M09, M19 | Planned |
| M08 | Traps | Post Sprint 3 | future infra/combat PRD | trap defs, trigger records | M01, M07 | combat, security loops | Planned |
| M09 | Fluid Simulation | Post Sprint 2 | future environment PRD | fluid cells, flow state | M07, map authority | M06, M10, M19 | Planned |
| M10 | Temperature | Post Sprint 2 | future environment/material PRD | temperature field, thermal material state | M09, material kernel | M01, M17, M19 | Planned |
| M11 | Trade | Sprint 2 then Sprint 3 | `docs/PRD_world_state_kernel_v1.md`, `docs/PRD_colony_simulation_v1.md` | faction/site trade state, value hooks | M20, item kernel | M12, diplomacy, supply | PRD seed |
| M12 | Migration / Population | Sprint 2 | `docs/PRD_world_state_kernel_v1.md`, `docs/PRD_history_and_factions_v1.md` | `HistoryFigure`, `FactionRecord`, future migration events | world generation, faction kernel | M03, site pressure | PRD written |
| M13 | Strange Mood | Post Sprint 3 | future colony/crafting pressure PRD | mood event defs, artifact hooks | M02, M03, M04 | M11, colony incidents | Planned |
| M14 | World Generation | Sprint 2 | `docs/PRD_world_state_kernel_v1.md`, `docs/PRD_history_and_factions_v1.md` | `WorldState`, `RegionRecord`, `HistoryEvent` | worldgen pipeline | all higher systems | PRD written, initial runtime slice |
| M15 | Pathfinding | Sprint 4 local authority | `docs/PRD_hybrid_commander_loop_v1.md` plus future local map/path PRD | travel graph, local path authority | world state, local map | M04, M18, local actions | PRD seed |
| M16 | Building / Room Assignment | Sprint 3 | `docs/PRD_job_reaction_kernel_v1.md`, `docs/PRD_colony_simulation_v1.md` | `WorksiteRecord`, room/zone state | M04, item/material kernel | M03, M07, M11 | PRD seed |
| M17 | Wear / Degradation | Sprint 1 then later expansion | `docs/PRD_material_item_kernel_v1.md` | `ItemStack`, material durability, wear state | M01, M10 | M03, item upkeep | Initial combat wear integration |
| M18 | Military | Sprint 4 | `docs/PRD_hybrid_commander_loop_v1.md`, future squad PRD | squad state, duty schedule, equipment policy | M01, M02, M15 | combat, raids, defense | PRD seed |
| M19 | Farming | Sprint 3 | `docs/PRD_job_reaction_kernel_v1.md`, `docs/PRD_colony_simulation_v1.md` | crop jobs, seed economy, food pressure | M04, M10 | M03, supply, trade | PRD seed |
| M20 | Diplomacy | Sprint 2 then Sprint 3 | `docs/PRD_history_and_factions_v1.md`, `docs/PRD_world_state_kernel_v1.md` | faction relations, diplomacy events | M11, M14 | M11, war/travel pressure | PRD written |

## Dependency Guardrails
- M01 Combat must still create wounds that feed M05 Medical, contaminants that feed M06 Syndrome, and witness/death events that feed M03 Stress.
- M02 Skill progression must be driven by M04 Job completion and must feed combat, crafting quality, and M13 eligibility.
- M03 Stress must still be affected by wounds, loss, deprivation, and wear; breakdown behavior must still be able to disrupt M04 jobs or spill back into M01 combat.
- M04 Jobs must still require pathing, item access, and worksites; outputs must still feed items, XP, construction, and colony supply.
- M07 Power must remain an enabling layer for M08 Traps, M09 Fluid routing, and M19 Milling or other powered production.
- M09 Fluid must still interact with M10 Temperature and M19 Farming, not become a visual-only effect.
- M11 Trade must still modify M20 Diplomacy and future migration/supply surfaces.
- M14 World Generation must remain the root creator of geography, factions, history, and off-map continuity for every higher system.

## Sprint Checkpoints
- Sprint 0 may only touch UI and automation authority. It must not fake later kernel work.
- Sprint 1 must deliver the typed actor, body, material, and wound baseline needed for M01, M05, and M17.
- Sprint 2 must deliver the typed world, faction, site, history, and diplomacy baseline needed for M11, M12, M14, and M20.
- Sprint 3 must deliver the typed job, colony, need, schedule, room, and farming baseline needed for M02, M03, M04, M16, and M19.
- Sprint 4 must deliver the hybrid commander loop, travel, local map authority, and military framing needed for M15 and M18.

## Notes
- "PRD seed" means the owning PRD family exists but the mechanism still needs a dedicated implementation slice and tests.
- "Initial runtime slice" means typed structures or adapters exist, but the mechanism is not yet integrated end-to-end.
- This checklist should be updated whenever a mechanism moves from PRD-only to typed runtime, or from typed runtime to tested integration.

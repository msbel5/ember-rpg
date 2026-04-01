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
| M01 | Combat | Sprint 1 | `docs/deprecated/prd/PRD_body_injury_combat_v1.md`, `docs/prd/active/PRD_material_item_kernel_v1.md` | `BodyState`, `WoundRecord`, `MaterialDef`, `EquipmentLoadout`, `StrikeResolution` | M02, M17, actor kernel | M03, M05, M06 | Typed runtime plus live strike-path integration |
| M02 | Skill / Learning | Sprint 3 | `docs/prd/active/PRD_actor_kernel_v1.md`, `docs/deprecated/prd/PRD_job_reaction_kernel_v1.md` | actor skill state, colony/job ledgers | M04 | M01, M04, M13 | Typed colony/job runtime and tests |
| M03 | Need / Happiness / Stress | Sprint 3 | `docs/deprecated/prd/PRD_colony_simulation_v1.md`, `docs/prd/active/PRD_actor_kernel_v1.md` | `NeedState`, `ColonyPressureState`, quest seeds | M01, M05, M12, M17, colony loop | M04, M13, breakdown behavior | Typed runtime and payload integration |
| M04 | Job / Task Assignment | Sprint 3 | `docs/deprecated/prd/PRD_job_reaction_kernel_v1.md` | `JobRecord`, `ReactionDef`, `WorksiteRecord` | M02, M15, item availability | M02, M05, M16, M19 | Typed runtime and campaign/save surfaces |
| M05 | Medical | Sprint 1 then Sprint 3 | `docs/deprecated/prd/PRD_body_injury_combat_v1.md`, later job/colony PRDs | `WoundRecord`, future treatment records | M01, M04 | M03, actor recovery | Wound hooks live, treatment pending |
| M06 | Syndrome / Poison | Sprint 5 baseline | `docs/deprecated/prd/PRD_body_injury_combat_v1.md` plus systems closure slice | `ConditionRecord`, `SyndromeDef`, `SyndromeEffect` | M01, M09 | M01, M03 | Initial typed registry and tests |
| M07 | Machine / Power | Sprint 5 baseline | systems closure slice | `PowerNetworkState`, `PowerNodeState` | M04, M16 | M08, M09, M19 | Initial typed runtime and payload tests |
| M08 | Traps | Sprint 5 baseline | systems closure slice | `TrapState` | M01, M07 | combat, security loops | Initial typed runtime and payload tests |
| M09 | Fluid Simulation | Sprint 5 baseline | systems closure slice | `FluidState` | M07, map authority | M06, M10, M19 | Initial typed runtime and payload tests |
| M10 | Temperature | Sprint 5 baseline | systems closure slice | `TemperatureState` | M09, material kernel | M01, M17, M19 | Initial typed runtime and payload tests |
| M11 | Trade | Sprint 2 then Sprint 3 | `docs/prd/active/PRD_world_state_kernel_v1.md`, `docs/deprecated/prd/PRD_colony_simulation_v1.md` | faction/site trade state, value hooks | M20, item kernel | M12, diplomacy, supply | Typed macro payload hooks live, colony economics pending |
| M12 | Migration / Population | Sprint 2 | `docs/prd/active/PRD_world_state_kernel_v1.md`, `docs/prd/active/PRD_history_and_factions_v1.md` | `HistoryFigure`, `FactionRecord`, future migration events | world generation, faction kernel | M03, site pressure | Typed runtime and save/load coverage |
| M13 | Strange Mood | Sprint 5 baseline | systems closure slice | `StrangeMoodIncident` | M02, M03, M04 | M11, colony incidents | Initial typed runtime and payload tests |
| M14 | World Generation | Sprint 2 | `docs/prd/active/PRD_world_state_kernel_v1.md`, `docs/prd/active/PRD_history_and_factions_v1.md` | `WorldState`, `RegionRecord`, `HistoryEvent` | worldgen pipeline | all higher systems | Typed payload and save/load integration |
| M15 | Pathfinding | Sprint 4 local authority | `docs/prd/active/PRD_hybrid_commander_loop_v1.md` plus future local map/path PRD | travel graph, `PathAuthorityState`, `LocalMapState` | world state, local map | M04, M18, local actions | Typed runtime and command/path tests |
| M16 | Building / Room Assignment | Sprint 3 | `docs/deprecated/prd/PRD_job_reaction_kernel_v1.md`, `docs/deprecated/prd/PRD_colony_simulation_v1.md` | `WorksiteRecord`, room/zone state | M04, item/material kernel | M03, M07, M11 | Typed room/worksite runtime and tests |
| M17 | Wear / Degradation | Sprint 1 then later expansion | `docs/prd/active/PRD_material_item_kernel_v1.md` | `ItemStack`, material durability, wear state | M01, M10 | M03, item upkeep | Initial combat wear integration |
| M18 | Military | Sprint 4 | `docs/prd/active/PRD_hybrid_commander_loop_v1.md`, future squad PRD | `MilitaryState`, `SquadRecord`, duty schedule, equipment policy | M01, M02, M15 | combat, raids, defense | Typed runtime and command tests |
| M19 | Farming | Sprint 3 | `docs/deprecated/prd/PRD_job_reaction_kernel_v1.md`, `docs/deprecated/prd/PRD_colony_simulation_v1.md` | crop jobs, seed economy, food pressure | M04, M10 | M03, supply, trade | Typed colony-pressure and quest-seed baseline |
| M20 | Diplomacy | Sprint 2 then Sprint 3 | `docs/prd/active/PRD_history_and_factions_v1.md`, `docs/prd/active/PRD_world_state_kernel_v1.md` | faction relations, diplomacy events | M11, M14 | M11, war/travel pressure | Typed faction/history payload links live |

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
- Sprint 5 must deliver the typed systems-closure baseline for M06, M07, M08, M09, M10, and M13.

## Implementation Reality Audit (2026-04-01)

Honest assessment of what exists as running simulation vs metadata-only typed structures:

| ID | Mechanism | Dataclass Coverage | Logic Coverage | Reality |
|----|-----------|-------------------|----------------|---------|
| M01 | Combat | 90% | 50% | Strike resolution works (material physics, armor, wounds). MISSING: to-hit/dodge rolls, saving throws, pain cascade, backstab. Auto-hits. |
| M02 | Skill/Learning | 70% | 20% | Skills stored on actor. MISSING: XP gain from jobs, skill rust, quality formula from skill rating. |
| M03 | Need/Happiness/Stress | 80% | 35% | NeedState and ColonyPressureState exist with numeric formulas. MISSING: morale cascades (tantrum/berserk), need decay per tick. |
| M04 | Job/Task Assignment | 85% | 35% | JobRecord, ReactionDef, WorksiteRecord exist. MISSING: actual labor simulation, material gathering pathfinding, work execution ticks. |
| M05 | Medical | 30% | 0% | Wound hooks exist. MISSING: entire treatment pipeline (diagnosis, clean, suture, dress, recovery). No healing mechanics. |
| M06 | Syndrome/Poison | 85% | 15% | SyndromeDef/SyndromeEffect exist. MISSING: resistance checks, transmission, tick progression, actual effects on actor. |
| M07 | Machine/Power | 80% | 20% | PowerNetworkState counts nodes. MISSING: distribution algorithm, connected components, mechanism chains. |
| M08 | Traps | 70% | 10% | TrapState exists, hardcoded for fortified settlements only. MISSING: trigger pipeline, damage resolution, rearm logic. |
| M09 | Fluid Simulation | 60% | 5% | FluidState counts tiles. MISSING: flow spreading, drowning, magma damage, obsidian creation. |
| M10 | Temperature | 60% | 5% | TemperatureState tracks ambient band. MISSING: heat source radiation, freeze/burn effects, material state changes. |
| M11 | Trade | 40% | 15% | Region economy with base prices. MISSING: caravan simulation, barter values, CHA effect, faction trade agreements. |
| M12 | Migration | 50% | 10% | HistoryFigure, FactionRecord, population field. MISSING: wave mechanics, family trees, skill-based distribution. |
| M13 | Strange Mood | 70% | 10% | StrangeMoodIncident exists. MISSING: material demand phase, artifact creation, skill boost, mood failure consequences. |
| M14 | World Generation | 95% | 80% | Excellent terrain gen (tectonics, erosion, biomes). History generation exists. Settlement layout works. |
| M15 | Pathfinding | 60% | 25% | Travel graph with PathAuthorityState. MISSING: local A* on search map, multi-tile pathfinding. |
| M16 | Building/Room | 70% | 20% | WorksiteRecord exists. MISSING: room value calculation, zone assignment, furniture happiness bonus. |
| M17 | Wear/Degradation | 60% | 15% | ItemStack.wear field, combat wear increments. MISSING: wear threshold breakage, sharpness decay. |
| M18 | Military | 70% | 15% | SquadRecord, MilitaryState exist. MISSING: squad movement, engagement, order execution, coordination. |
| M19 | Farming | 50% | 10% | Crop job references in colony. MISSING: growth cycles, seed economy, harvest mechanics. |
| M20 | Diplomacy | 50% | 10% | Faction disposition field. MISSING: ethics conflict computation, war/peace state machine, tribute demands. |

**Overall: ~72% dataclass coverage, ~22% logic coverage. The kernel is typed metadata, not a running simulation.**

### New PRDs Added to Close Logic Gaps
- `PRD_effect_system_v1.md` — unified buff/debuff pipeline (spine for M01, M05, M06)
- `PRD_combat_resolution_v1.md` — complete d20 + physics combat (M01 upgrade)
- `PRD_medical_system_v1.md` — treatment pipeline (M05)
- `PRD_systems_closure_v1.md` — full Sprint 5 spec (M06-M10, M13)
- `PRD_colony_simulation_v2.md` — full colony spec (M03, M04, M16, M19)
- `PRD_job_reaction_kernel_v2.md` — full job/reaction spec (M02, M04)

## Notes
- "PRD seed" means the owning PRD family exists but the mechanism still needs a dedicated implementation slice and tests.
- "Initial typed runtime" means canonical structures, payload wiring, and targeted tests exist, but the mechanic may still need deeper simulation depth or balance cleanup.
- Campaign save/load and Godot client handoff now persist and consume canonical `kernel_world_state` / `kernel_game_state` roots explicitly; remaining mechanism gaps are about deeper logic, not the primary campaign payload contract.
- This checklist should be updated whenever a mechanism moves from PRD-only to typed runtime, or from typed runtime to tested integration.

## Changelog
- 2026-04-01b: Noted that campaign save/load and Godot client handoff now use canonical kernel roots explicitly.
- 2026-04-01: Added Implementation Reality Audit with honest dataclass vs logic coverage percentages. Added 6 new PRDs to close logic gaps.

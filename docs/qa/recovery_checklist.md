# Ember RPG Recovery Checklist
**Date:** 2026-04-01  
**Status:** Active

This checklist is the anti-context-loss surface for the recovery program. Update it whenever a recovery sprint changes state.

## Sprint 0: Creation Unblock
- [x] Define creation unblock strategy and acceptance criteria
- [x] Define automation authority and rejection of Windows `computer_use` as primary QA path
- [x] Replace small centered creation modal with a readable full-shell layout
- [x] Keep all questionnaire groups visible on one scrollable surface
- [x] Keep live campaign genesis preview visible during questionnaire/build flow
- [x] Make rolled-pool save/swap state explicit
- [x] Remove freeform stat entry from the effective allocation flow
- [x] Keep dossier summary readable and stable
- [x] Prove title/creation flow with screenshot artifacts
- [x] Keep targeted backend tests green for creation/kernel changes
- [x] Keep Godot headless tests green
- [x] Keep desktop automation fallback honest about capability and dependency gaps

## Sprint 1: Canonical Actor Kernel
- [x] Decide actor-kernel-first sequencing
- [x] Write canonical actor kernel PRD
- [x] Write material/item kernel PRD
- [x] Write body/injury/combat PRD
- [x] Introduce `ActorRecord` and related canonical types
- [x] Introduce initial typed `WorldState` adapter and tests so Sprint 2 work has a real landing zone
- [x] Reduce current `Entity` to canonical root or façade across runtime consumers
- [x] Replace `BodyPartTracker` as authoritative injury state in the live strike path while preserving tracker sync for compatibility
- [x] Add deterministic combat tests against typed body/material state
- [x] Integrate typed actor/item/body surfaces into live command handlers

## Sprint 2: World State / History / Faction
- [x] Write world-state kernel PRD
- [x] Write history/factions PRD
- [x] Type macro world graph as authoritative `WorldState` in campaign/runtime payloads
- [x] Type site/faction/history links end-to-end
- [x] Ensure save/load round-trip for typed macro state
- [x] Prove travel graph integrity with targeted tests
- [x] Preserve DF-style M11, M12, M14, and M20 dependency links in runtime code

## Sprint 3: Jobs / Reactions / Colony Simulation
- [x] Write jobs/reactions PRD
- [x] Write colony simulation PRD
- [ ] Unify workstation, recipe, and need/schedule logic under typed job records
- [ ] Route quests from deterministic colony pressure
- [ ] Add shortage / production / schedule tests
- [ ] Preserve DF-style M02, M03, M04, M16, and M19 dependency links in runtime code

## Sprint 4: Hybrid Commander Loop
- [x] Write hybrid commander loop PRD
- [ ] Bind macro travel and local commander exploration to one authoritative world tick
- [ ] Keep AI out of core gameplay authority
- [ ] Add targeted map/travel/local-loop integration tests
- [ ] Preserve DF-style M15 and M18 dependency links in runtime code

## Global Rules
- [x] PRD first
- [ ] AC written before each new implementation chunk
- [x] TDD for Sprint 1 combat/body cutover
- [x] TDD for Sprint 2 campaign/world payload cutover
- [x] Screenshot or video proof for the current UI-facing recovery slice
- [x] No full chaos suite by default
- [x] No regression to hidden-tab or one-question wizard UX
- [x] Maintain DF-inspired mechanism coverage map in `docs/qa/df_mechanism_checklist.md`

## Current Evidence
- [x] Backend targeted suite passed on 2026-03-31 for actor/world-state plus campaign regression tests
- [x] Backend targeted suite passed on 2026-04-01 for canonical world-state payload, save/load, command bus, and travel graph coverage
- [x] Godot headless suite passed on 2026-03-31 after creation-shell and automation-bridge changes
- [x] Python automation suite passed on 2026-03-31 including atomic command-file fallback coverage
- [x] Desktop smoke scenario produced title and questionnaire screenshots on 2026-03-31

## Current Risks
- [ ] Win32 keyboard injection is still weaker than the headless bridge path
- [ ] Sprint 1 still leaves legacy save/load and some non-combat runtime surfaces on compatibility shims
- [ ] Sprint 3 through Sprint 4 are documented but not yet integrated end-to-end

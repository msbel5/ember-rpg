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
- [x] Unify workstation, recipe, and need/schedule logic under typed job records
- [x] Route quests from deterministic colony pressure
- [x] Add shortage / production / schedule tests
- [x] Preserve DF-style M02, M03, M04, M16, and M19 dependency links in runtime code

## Sprint 4: Hybrid Commander Loop
- [x] Write hybrid commander loop PRD
- [x] Bind macro travel and local commander exploration to one authoritative world tick
- [x] Keep AI out of core gameplay authority
- [x] Add targeted map/travel/local-loop integration tests
- [x] Preserve DF-style M15 and M18 dependency links in runtime code

## Sprint 5: Systems Closure
- [x] Introduce typed syndrome and condition registry surfaces
- [x] Introduce typed power-network and trap surfaces
- [x] Introduce typed fluid and temperature surfaces
- [x] Introduce typed strange-mood incident surface
- [x] Expose Sprint 5 systems through campaign payloads and save metadata
- [x] Add targeted systems tests and payload regression coverage
- [x] Preserve DF-style M06, M07, M08, M09, M10, and M13 dependency links in runtime code

## Wave 2: Runtime / Save-Load Cutover
- [x] Expose `GameState` in campaign payloads as the canonical runtime/save-load projection root
- [x] Persist `kernel_game_state` inside `campaign_v2` metadata
- [x] Validate `GameState.from_dict()` during campaign load for fail-fast kernel save compatibility
- [x] Keep campaign API and campaign client save/load regression tests green after `GameState` cutover
- [x] Persist canonical `kernel_world_state` and `kernel_game_state` aliases at the top level of serialized session state for campaign saves
- [x] Fail fast during strict campaign load when `kernel_world_state` or `kernel_game_state` is invalid
- [x] Keep Godot-ready campaign payload shape tests green while migrating the client toward canonical slices

## Wave 3: Authoritative Runtime Alignment
- [x] Reconcile save/load docs with canonical kernel save roots and strict validation behavior
- [x] Reconcile Godot client docs with canonical `world_state` / `game_state` consumption
- [x] Update runtime authority notes to describe canonical kernel save roots and remaining shim boundaries
- [x] Keep implementation checklists aligned with the actual runtime/save/load contract

## Wave 4: Godot / Creation / Automation Closure
- [x] Keep Godot headless suite green while storing canonical `campaign.world_state` and `campaign.game_state` in `GameState`
- [x] Keep Python automation suite green for headless bridge and Win32 fallback capability handling
- [x] Produce fresh headless scenario proof for title/creation through `title_creation_bridge`
- [x] Keep creation-shell keyboard/mouse flow, preview, roll/save/swap, and dossier steps covered in headless tests
- [x] Keep automation docs aligned with headless-primary, Win32-fallback policy and synthetic-capture labeling

## Global Rules
- [x] PRD first
- [ ] AC written before each new implementation chunk
- [x] TDD for Sprint 1 combat/body cutover
- [x] TDD for Sprint 2 campaign/world payload cutover
- [x] TDD for Sprint 3 colony/job payload cutover
- [x] TDD for Sprint 4 hybrid/path/military payload cutover
- [x] TDD for Sprint 5 systems-closure payload cutover
- [x] Screenshot or video proof for the current UI-facing recovery slice
- [x] No full chaos suite by default
- [x] No regression to hidden-tab or one-question wizard UX
- [x] Maintain DF-inspired mechanism coverage map in `docs/qa/df_mechanism_checklist.md`

## Current Evidence
- [x] Backend targeted suite passed on 2026-03-31 for actor/world-state plus campaign regression tests
- [x] Backend targeted suite passed on 2026-04-01 for canonical world-state payload, save/load, command bus, and travel graph coverage
- [x] Backend targeted suite passed on 2026-04-01 for colony, hybrid, and systems kernel coverage
- [x] Backend targeted suite passed on 2026-04-01 for campaign API/client `GameState` cutover and save/load metadata validation
- [x] Backend targeted suite passed on 2026-04-01 for strict invalid-kernel save rejection and Godot payload-shape regression coverage
- [x] Godot headless suite passed on 2026-03-31 after creation-shell and automation-bridge changes
- [x] Godot headless suite passed on 2026-04-01 after canonical `world_state` / `game_state` client normalization changes
- [x] Python automation suite passed on 2026-03-31 including atomic command-file fallback coverage
- [x] Python automation suite passed on 2026-04-01 after Wave 4 contract verification (`27 passed`)
- [x] Desktop smoke scenario produced title and questionnaire screenshots on 2026-03-31
- [x] Headless automation scenario `title_creation_bridge` passed on 2026-04-01 and produced deterministic viewport artifacts

## Current Risks
- [ ] Win32 keyboard injection is still weaker than the headless bridge path
- [ ] Some non-campaign legacy session/runtime surfaces still rely on compatibility shims and remain a follow-up cleanup target
- [ ] Full backend suite merge gate still needs either one bounded green run or an explicitly maintained sharded equivalent
- [ ] Sprint closure is typed-authority complete, but deeper simulation balance and wider UX cleanup still need manual cleanup

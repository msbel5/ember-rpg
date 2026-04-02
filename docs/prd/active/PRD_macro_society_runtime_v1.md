# PRD: Macro Society Runtime V1
**Project:** Ember RPG
**Phase:** 6
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Approved

---

## 1. Purpose

Macro Society Runtime closes the gap between typed world-state records and a
living frontier simulation. It makes trade, migration, diplomacy, caravan flow,
and ownership/history consequences execute inside the same deterministic
campaign runtime as the rest of Ember's kernel. This is the authoritative
runtime layer for DF-inspired trade/migration/diplomacy loops and GemRB-style
faction pressure and regional continuity.

**Synthesis:** Combines DF `M11`, `M12`, `M20` with GemRB `M13`, `M14` into an
Ember-specific macro-society tick that operates on canonical `WorldState`,
settlement economy state, and store inventories.

## 2. Scope

### In scope
- colony shortage/surplus propagation into store price drift
- caravan arrival flow and stock mutation
- faction relation drift from settlement prosperity or shortage
- migration wave generation from colony pressure and housing/morale conditions
- world ownership/history consequence records written into canonical `WorldState`
- persistence of active caravans, migration waves, ownership changes, and
  faction relations through `kernel_world_state`

### Out of scope
- deep diplomacy UI
- strategic war AI
- full off-map civ simulation replacement
- non-deterministic merchant haggling

## 3. Runtime Authority

Macro society logic is authoritative only when it runs inside the campaign tick.
On every world advance or commander command, the runtime must execute this
deterministic sequence:

1. recompute `ProductionLedger` from the active settlement
2. update store price multipliers from shortage/surplus conditions
3. advance caravans and apply arrived goods to stores and settlement economy
4. drift faction relations based on current colony pressure
5. create migration waves when prosperity thresholds are satisfied
6. append ownership/history consequences into canonical `WorldState`

Authoritative runtime surfaces:
- `frp-backend/engine/api/campaign/live_kernel.py`
- `frp-backend/engine/api/campaign/runtime_macro_society.py`
- `frp-backend/engine/api/campaign/runtime_settlement.py`
- `frp-backend/engine/kernel/world_state.py`
- `frp-backend/engine/kernel/store.py`

## 4. Functional Requirements

**FR-01:** `WorldState` must persist live `active_caravans`, `migration_waves`,
`ownership_changes`, and per-faction `relations`.

**FR-02:** Store prices must shift each runtime tick from the current
`ProductionLedger`. Shortages raise local prices; surpluses create local
discount pressure.

**FR-03:** Caravan arrivals must mutate both store inventory and settlement
resource state in the same tick they are observed.

**FR-04:** Faction relations must drift deterministically each tick from colony
pressure and shortage/surplus state. No hidden random diplomacy branch is
allowed.

**FR-05:** A settlement with `housing > 80`, `morale > 70`, and `food > 60`
must generate a migration wave unless an identical wave already exists for the
current region/day.

**FR-06:** Unrest-driven ownership pressure must write a typed history
consequence into canonical `WorldState`.

**FR-07:** Godot campaign payloads must expose live `stores` and `world_state`
data that reflect the latest macro-society tick, not a stale projection.

**FR-08:** Save/load must preserve macro-society runtime state through canonical
kernel payloads without falling back to legacy compatibility structures.

## 5. Acceptance Criteria

**AC-01:** Given a colony with shortages, when a campaign tick runs, then at
least one store item price multiplier changes from its prior value.

**AC-02:** Given a caravan arrival event, when the tick completes, then both
store stock and settlement economy resources increase deterministically.

**AC-03:** Given a prosperous colony with `migration_candidate`, when the tick
runs, then `world_state.migration_waves` gains a new typed entry and settlement
population increases.

**AC-04:** Given two factions in the active world, when the macro tick runs,
then their relations are present and updated in canonical `WorldState`.

**AC-05:** Given high unrest in a controlled region, when the macro tick runs,
then `world_state.ownership_changes` records the pressure consequence.

**AC-06:** Given a save/load round-trip, the restored campaign payload must
preserve stores, caravans, migration waves, ownership changes, and faction
relations.

## 6. Evidence

Primary runtime evidence:
- `frp-backend/tests/test_campaign_logic_live.py`
- `frp-backend/tests/test_campaign_save_load_v2.py`
- `frp-backend/tests/test_command_bus.py`
- `godot-client/tests/automation/scenarios/resume_and_command.toml`

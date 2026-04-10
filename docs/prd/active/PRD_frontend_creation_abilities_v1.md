# PRD: Frontend Creation — Ability Score Rolling (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **ability score rolling stage** of character creation — BG1's 3d6 roll with reroll + store/swap mechanic. The player rolls STR, DEX, CON, INT, WIS, CHA. If STR is 18, the player also rolls 1d100 for percentile. The player can reroll the entire pool unlimited times, save a rolled pool to a "stored" slot, or swap the active and stored pools. The minimum qualifying total for some classes is enforced (e.g. Paladin requires CHA 17+, Ranger requires STR/DEX/CON/WIS mins). Bonus points may be distributed above the roll in some BG1 variants (ember-rpg backend is authoritative here).

### Reference sources
- **GemRB behavior:** Ability roll logic lives across `gemrb/GUIScripts/bg1/GUICG2.py` (may contain the roll window), `GUICG4.py` (general overview), and the AC2DA / STATS table loaders. Backend-side, `CharGen.next()` advances here after class selection because class determines the minimums.
- **GemRB roll formula:** 3d6 per stat, with racial mods applied as `applyracial()` helper. STR 18 gets a percentile `d100`.
- **Ember backend:** The existing creation API already supports reroll via `/game/campaigns/creation/reroll` and save-roll via `/game/campaigns/creation/save-roll` plus `/game/campaigns/creation/swap-roll` (per `title_screen.gd` existing wire-up).
- **Ember client existing code:** `godot-client/scripts/ui/creation_step_history_roll.gd` is probably the closest existing step file; may need to rename to `creation_step_abilities.gd` for clarity

## 2. Scope

**In scope:**
- Six ability score labels (STR / DEX / CON / INT / WIS / CHA) showing current rolled values
- STR percentile display (e.g. "18/77") when applicable
- +/- buttons per ability to redistribute bonus points (if ember rules allow; optional)
- Total sum display
- Reroll button (unlimited)
- Save (store) button — saves the current pool to a second slot
- Swap button — swaps active pool with stored pool
- Minimum-met indicator per class (green checkmark / red x)
- Racial modifiers displayed as "+1 CON (Dwarf)" style annotations
- Next/Back buttons integrated with parent wizard's state machine

**Out of scope:**
- Race/class restriction enforcement (backend authority — client just displays feedback)
- Point-buy systems (optional BG rule variants not in BG1)
- Ability score cap enforcement at the UI level (backend clamps)

## 3. Functional Requirements (FR)

**FR-01:** The stage MUST render 6 rows (STR/DEX/CON/INT/WIS/CHA), each with: label, value display, (optional) +/- buttons, racial mod annotation, minimum-met indicator.

**FR-02:** The initial roll MUST be fetched from the backend via `Backend.start_campaign_creation(...)` which returns the initial ability pool. The stage MUST NOT roll dice client-side.

**FR-03:** The Reroll button MUST call `Backend.reroll_campaign_creation(creation_id, callback)` which returns a new pool. The UI MUST re-render on the callback.

**FR-04:** The Save (store) button MUST call `Backend.save_campaign_creation_roll(creation_id, callback)`. On success, the UI MUST display the stored pool alongside the active pool in a small "stored" preview.

**FR-05:** The Swap button MUST call `Backend.swap_campaign_creation_roll(creation_id, callback)`. On success, active and stored pools swap display positions.

**FR-06:** The Total label MUST compute `sum(active pool values)` and display it. Color-coded: ≥80 green, 70-79 yellow, <70 red.

**FR-07:** Each ability label MUST show a class-minimum check: if `value >= class_min[ability]`, show a green checkmark; else a red x with tooltip "Paladin requires WIS 13+" style.

**FR-08:** Racial modifiers MUST be fetched from the backend creation response and shown as e.g. "+1 CON" next to the affected stat.

**FR-09:** When STR == 18 and the creation response includes a `percentile` subfield, the display MUST show "18/NN" where NN is the percentile. Backend provides the percentile.

**FR-10:** The Next button MUST be disabled until all class minimums are met. It MUST become enabled when the backend confirms minimums are met (include a `minimums_met: bool` flag in the response).

**FR-11:** The Back button MUST unset the roll and return to the previous stage (class selection) without losing the stored pool (backend preserves it).

**FR-12:** The stage MUST refresh on `GameState.creation_state_updated` signal (fired when the backend responds to any roll operation).

## 4. Data Structures

Per-ability row state:

    # Part of CharGenState.ability_scores per the parent PRD
    {
        "str": {"value": 18, "percentile": 77, "racial_mod": 0, "min_met": true},
        "dex": {"value": 14, "percentile": 0, "racial_mod": 0, "min_met": true},
        "con": {"value": 16, "percentile": 0, "racial_mod": 1, "min_met": true},
        ...
    }

Creation reroll response (backend shape — existing):

    {
        "creation_id": "...",
        "ability_pool": {active: {...}, stored: {...}},
        "racial_mods": {"str": 0, "dex": 0, "con": 1, ...},
        "class_minimums": {"str": 9, "dex": 6, "con": 9, ...},
        "minimums_met": true,
        "total_active": 82,
        "total_stored": 76
    }

## 5. Public API — methods that MUST exist

    # ---- construction ----
    func _ready() -> void
    
    # ---- roll operations ----
    func roll_abilities() -> void                                                # triggers start (first entry)
    func reroll_abilities() -> void                                              # calls Backend.reroll_campaign_creation
    func save_current_roll() -> void                                             # calls Backend.save_campaign_creation_roll
    func swap_active_and_stored() -> void                                        # calls Backend.swap_campaign_creation_roll
    
    # ---- response handlers ----
    func on_abilities_rolled(data) -> void
    func on_abilities_rerolled(data) -> void
    func on_abilities_saved(data) -> void
    func on_abilities_swapped(data) -> void
    
    # ---- rendering ----
    func render_active_pool() -> void
    func render_stored_pool() -> void
    func render_ability_row(ability_id: String, row_data: Dictionary) -> void
    func render_total() -> void
    func render_minimum_indicators() -> void
    func render_racial_mods() -> void
    
    # ---- formatting ----
    func format_ability_value(value: int, percentile: int = 0) -> String         # "18/77" or "15"
    func format_racial_mod(mod: int) -> String                                   # "+1" or "-2" or ""
    func total_color_for(total: int) -> Color                                    # green/yellow/red
    
    # ---- validation ----
    func are_all_minimums_met() -> bool                                          # reads GameState
    func get_class_minimum(ability_id: String) -> int                            # reads backend data
    func tooltip_for_minimum(ability_id: String) -> String                       # "Paladin requires WIS 13+"
    
    # ---- state machine hooks ----
    func set_fn() -> void                                                        # called by parent wizard on stage entry
    func comment_fn(text_area: RichTextLabel) -> void                            # appends summary to overview
    func unset_fn() -> void                                                      # clears stage state on back
    func guard_fn() -> bool                                                      # returns true (always active)
    
    # ---- signals ----
    signal abilities_rolled(pool: Dictionary)
    signal reroll_requested()
    signal save_roll_requested()
    signal swap_roll_requested()
    signal minimums_met_changed(met: bool)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The stage has exactly 6 rows, one per ability. Verified by counting children of the `AbilitiesContainer`.

**AC-02 [FR-02]:** On `_ready()`, the stage MUST NOT invoke any client-side random roll; it MUST wait for backend data. Verified by spying on `Backend.start_campaign_creation` call.

**AC-03 [FR-03]:** Clicking Reroll MUST call `Backend.reroll_campaign_creation` exactly once.

**AC-04 [FR-04]:** Clicking Save MUST call `Backend.save_campaign_creation_roll` exactly once. After the response, the stored pool preview MUST be visible.

**AC-05 [FR-05]:** Clicking Swap MUST call `Backend.swap_campaign_creation_roll`. After the response, the active pool values MUST equal what was previously stored.

**AC-06 [FR-06]:** Given active values summing to 82, the Total label shows "82" and its color MUST be green. Summing to 72: yellow. Summing to 68: red.

**AC-07 [FR-07]:** With `class_minimums.wis = 13` and active `wis.value = 10`, the minimum indicator for WIS MUST show a red X and the tooltip MUST contain "13".

**AC-08 [FR-09]:** Given `str.value == 18` and `str.percentile == 77`, the STR label MUST display exactly "18/77".

**AC-09 [FR-10]:** With `minimums_met == false`, the Next button MUST be disabled. When a reroll brings `minimums_met == true`, Next MUST become enabled within the same refresh.

**AC-10 [reflection]:** Every method in §5 MUST exist on the script.

## 7. Performance Requirements

- Reroll round-trip → render: **< 300ms** (backend-bound, client render should be <16ms)
- Render all 6 rows: **< 10ms**

## 8. Error Handling

- Backend reroll fails: show error toast, keep previous pool
- Missing `ability_pool.active` in response: log at WARNING, render empty state
- Swap called with no stored pool: disable Swap button, tooltip "No stored pool to swap"
- Invalid ability id: skip, log at DEBUG

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_step_history_roll.gd` — rename / extend to `creation_step_abilities.gd` per §5 OR keep name for backward compat
- `godot-client/scripts/ui/creation_wizard.gd` — wire the stage into the parent state machine (parent PRD)
- `godot-client/tests/automation/godot/test_frontend_creation_abilities.gd` — NEW

**Backend (consumed, NOT modified):**
- `/game/campaigns/creation/start` (existing)
- `/game/campaigns/creation/reroll` (existing)
- `/game/campaigns/creation/save-roll` (existing)
- `/game/campaigns/creation/swap-roll` (existing)

**Forbidden:**
- No client-side dice rolling
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file (parent PRD's §12 roadmap table may be updated — that's fine)

## 10. Test Coverage Target

- `test_frontend_creation_abilities.gd` MUST cover AC-01..AC-10
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_abilities.gd

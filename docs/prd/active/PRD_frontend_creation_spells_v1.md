# PRD: Frontend Creation — Mage Spell Selection (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **mage spell selection stage** of character creation. When the player has picked the Mage class (or a specialist school, or a multi-class containing Mage), the wizard presents a grid of level-1 arcane spells from which the player must pick a fixed number (default `4` plus the INT learning bonus from the backend's creation response). Each selected spell is added to the character's starting spellbook. Non-mage classes skip this stage entirely via `guard_fn() -> false`. This is the BG1 rules subset of GemRB's `LUSpellSelection.py` — ember-rpg does not implement specialist school bonus spells or sorcerer mechanics in this PRD.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\LUSpellSelection.py` (713 LOC — `OpenSpellsWindow`, `ShowSpells`, `SpellsSelectPress`, `SpellsDonePress`, `SpellsPickPress`, `MarkButton`, `ShowSelectedSpells`, `UpdateScrollBar`, `RowIndex`, `HasSpecialistSpell`, `SpellsCancelPress`). The window shows 24 spell icons in a grid, with a scroll bar when there are more spells than slots, a description text area, and a "points remaining" label.
- **GemRB behavior (helpers):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\Spellbook.py` (830 LOC — `GetMageSpells`, `GetSpellLearningTable`, `HasSpell`, `RemoveKnownSpells`, `GetKnownSpellsDescription`). These functions resolve which spells are eligible for a given kit, alignment, and level.
- **GemRB behavior (BG1 kit window):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\GUICG22.py` (128 LOC — `KitPress`, `NextPress`). This is the specialist-school choice window that feeds the kit mask into the spell selection flow.
- **Ember backend:** Existing creation endpoints return a `spell_catalog` array in the creation response shape once the class is set. No new backend endpoint is introduced by this PRD.
- **Ember client existing code:** `godot-client/scripts/ui/creation_wizard.gd` (state machine host), `godot-client/scripts/ui/creation_wizard_state.gd` (`CharGenState`), sibling step files for existing stages.

**Clean-room rule:** Read GemRB only for *what* the spell selection window displays and *what* user actions it supports. Do not port the code. All GDScript is newly written.

## 2. Scope

**In scope:**
- A spell-selection sub-scene shown during the `spells_memorize` stage of the creation wizard
- Grid rendering of level-1 arcane spells (names, icons, hover-to-describe)
- Click-to-toggle selection, with points-remaining label
- Done button enabled only when `points_remaining == 0`
- Description text area updates on hover / select
- Back button routes back through the parent wizard's `back()` method
- `guard_fn()` skips this stage for non-mage classes
- Writing selected spells to `CharGenState.memorized_spells`
- State machine hooks (set/comment/unset/guard) per the parent PRD contract
- Reflection acceptance test enumerating every method in §5

**Out of scope:**
- Higher-level spell selection (level 2 and beyond — BG1 mages start at level 1)
- Specialist school bonus picks (specialist kits exist but all get 1 pick total in this MVP)
- Auto-pick / "recommend" button (GemRB feature; optional future enhancement)
- Level-up spell selection (separate PRD `PRD_frontend_level_up_v1.md`)
- Divine spell memorization (clerics/druids get priest spells auto-granted by the backend)
- Priest-school restrictions (not a BG1 concern at level 1 in ember rules)

## 3. Functional Requirements (FR)

**FR-01:** The stage MUST render a grid of spell slots populated from the backend creation response's `spell_catalog.mage.level_1` field. Each slot shows: an icon (or a placeholder if the icon slug is unknown to the client art pipeline), a short name tooltip on hover, a visual selected/unselected state.

**FR-02:** The stage MUST NOT compute the list of eligible spells client-side. The eligible spell list is supplied by the backend per the character's class, kit, and alignment.

**FR-03:** The number of picks available MUST come from the backend response field `spell_catalog.mage.picks_available_level_1`. This value is `4 + INT_learning_bonus` for a standard mage in BG1 rules; the backend is authoritative.

**FR-04:** A "points remaining" label MUST display `picks_available - len(selected)` and MUST update on every toggle.

**FR-05:** Clicking on an unselected spell slot with `points_remaining > 0` MUST mark the slot selected and decrement `points_remaining`. Clicking a selected slot MUST unselect it and increment `points_remaining`. Clicking on an unselected slot with `points_remaining == 0` MUST NOT change state and SHOULD display a tooltip or toast "No spell picks remaining".

**FR-06:** Hovering over any slot (selected or not) MUST update the description text area with the spell's full description from `spell_catalog.mage.level_1[i].description`. Clicking also updates the description.

**FR-07:** The Done button MUST be disabled while `points_remaining > 0` and enabled when `points_remaining == 0`. Pressing Done MUST write the selected spell ids to `CharGenState.memorized_spells` and call the parent wizard's `next()`.

**FR-08:** The Back button MUST call `unset_fn()` (clear `CharGenState.memorized_spells`) and then the parent wizard's `back()`.

**FR-09:** The stage's `guard_fn()` MUST return `false` when `CharGenState.class_id` is not one of the mage-capable classes. Mage-capable class ids in BG1 scope: `"mage"`, `"fighter_mage"`, `"mage_thief"`, `"fighter_mage_thief"`, `"cleric_mage"`. For any other class the stage MUST be skipped.

**FR-10:** The stage's `comment_fn(text_area)` MUST append a line to the overview text area listing the selected spell names, one per line, under a header like "Mage spells learned:". If no spells are selected, append nothing.

**FR-11:** If the backend's `spell_catalog.mage.level_1` is empty or missing while the guard still returns `true`, the stage MUST log a WARNING once, render an empty grid with an explanatory message in the description area, and leave the Done button disabled. The player MUST be able to Back out.

**FR-12:** The stage MUST refresh its grid when the `CharGenState` changes via the parent wizard's `creation_state_updated` signal — specifically when `class_id` changes upstream (e.g. the player backed out of this stage, changed class, and returned).

## 4. Data Structures

Relevant `CharGenState` field (defined in the parent PRD):

    CharGenState.memorized_spells: Array[String] = []
        # On entry: [] (cleared by unset_fn when backing into the stage)
        # On exit: list of spell ids chosen this stage, e.g. ["magic_missile", "sleep", "armor", "identify"]

Spell catalog entry (backend-supplied shape, client consumes read-only):

    {
        "spell_id": "magic_missile",             # stable identifier
        "display_name": "Magic Missile",
        "description": "A bolt of...",            # full rich-text description
        "icon_slug": "spell_magic_missile",       # art pipeline slug (optional)
        "level": 1,                                # arcane level
        "school": "evocation",                    # mage school name (optional)
        "eligible": true                           # false = locked (displayed but unclickable)
    }

Creation response shape consumed by this stage:

    {
        "creation_id": "...",
        "spell_catalog": {
            "mage": {
                "picks_available_level_1": 4,
                "level_1": [ {spell entry}, {spell entry}, ... ]
            }
        }
    }

Internal per-slot widget state (not persisted):

    var _slot_state: Array[Dictionary] = []
        # Each: {"spell_id", "selected": bool, "button_node": Button}

## 5. Public API — methods that MUST exist

The implementation MUST provide Godot equivalents for every method below on `creation_step_spells.gd`. Method names MAY adapt to idiomatic GDScript but responsibilities MUST be covered one-to-one. The acceptance test enumerates every method via reflection.

    class_name CreationStepSpells extends Control

    # ---- construction ----
    func _ready() -> void
    func _exit_tree() -> void

    # ---- state machine hooks (parent wizard contract) ----
    func set_fn() -> void                                                        # called on stage entry
    func comment_fn(text_area: RichTextLabel) -> void                            # overview summary
    func unset_fn() -> void                                                      # clear memorized_spells
    func guard_fn() -> bool                                                      # skip for non-mages

    # ---- data loading ----
    func load_spell_catalog(catalog: Dictionary) -> void                         # from backend response
    func get_picks_available() -> int
    func get_eligible_spells() -> Array[Dictionary]
    func is_mage_capable_class(class_id: String) -> bool

    # ---- grid rendering ----
    func render_spell_grid() -> void
    func render_spell_slot(index: int, spell_entry: Dictionary) -> void
    func refresh_slot_visuals() -> void                                          # re-paint after selection change
    func clear_grid() -> void

    # ---- selection handling ----
    func on_spell_slot_pressed(index: int) -> void                               # toggle
    func on_spell_slot_hovered(index: int) -> void                               # update description
    func select_spell(index: int) -> bool                                        # returns false if no picks remain
    func deselect_spell(index: int) -> void
    func is_spell_selected(index: int) -> bool
    func count_selected() -> int
    func get_selected_spell_ids() -> Array[String]

    # ---- description panel ----
    func update_description_area(text: String) -> void
    func clear_description_area() -> void
    func show_default_description_hint() -> void                                 # on grid load

    # ---- points label ----
    func update_points_remaining_label() -> void
    func points_remaining() -> int                                               # picks_available - count_selected()

    # ---- done / back button state ----
    func refresh_done_button_state() -> void
    func set_done_button_enabled(enabled: bool) -> void
    func on_done_pressed() -> void
    func on_back_pressed() -> void

    # ---- writeback to CharGenState ----
    func commit_to_char_gen_state() -> void                                      # called by on_done_pressed
    func restore_from_char_gen_state() -> void                                   # called by set_fn on re-entry

    # ---- error handling ----
    func handle_empty_catalog() -> void
    func log_warning_once(message: String) -> void

    # ---- signals ----
    signal spell_selection_changed(selected_ids: Array[String])
    signal spells_stage_completed(selected_ids: Array[String])
    signal spells_stage_aborted()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** Given a non-empty `spell_catalog.mage.level_1` of N entries, the stage renders N spell slots. Verified by counting children under the `SpellGridContainer` node.

**AC-02 [FR-02]:** The stage MUST NOT call any backend "list spells" endpoint from within this script — it MUST only read `CharGenState._last_creation_response`. Verified by spy on `Backend` autoload: no calls originate from `creation_step_spells.gd`.

**AC-03 [FR-03]:** Given `picks_available_level_1 == 4`, the points-remaining label initially reads "4". Verified by querying the `PointsRemainingLabel` node text.

**AC-04 [FR-04, FR-05]:** Clicking an unselected slot while `points_remaining == 4` results in `points_remaining == 3`. Clicking the same slot again results in `points_remaining == 4`. Verified by automation bridge.

**AC-05 [FR-05]:** Clicking an unselected slot while `points_remaining == 0` MUST NOT select the slot (`count_selected()` unchanged). A toast or tooltip "No spell picks remaining" MUST be reachable via automation bridge query.

**AC-06 [FR-06]:** Hovering over a slot updates the `DescriptionArea` text to match `spell_entry.description`. Verified by simulated hover event and text query.

**AC-07 [FR-07]:** With `points_remaining > 0` the `DoneButton.disabled == true`. After selecting enough to reach `points_remaining == 0`, `DoneButton.disabled == false` within the same refresh frame.

**AC-08 [FR-07]:** Pressing Done emits `spells_stage_completed(selected_ids)` AND writes those ids into `CharGenState.memorized_spells`. Verified by signal spy + state inspection.

**AC-09 [FR-09]:** With `CharGenState.class_id == "fighter"`, `guard_fn()` returns `false`. With `CharGenState.class_id == "mage"`, `guard_fn()` returns `true`. Verified by direct call.

**AC-10 [FR-10]:** Calling `comment_fn(text_area)` after selecting "Magic Missile" and "Sleep" appends two lines containing those display names. Verified by text area content inspection.

**AC-11 [FR-11]:** Given an empty `level_1` array but a truthy guard, `handle_empty_catalog()` runs: an informational message appears in `DescriptionArea`, the Done button remains disabled, and exactly one WARNING log entry is produced.

**AC-12 [FR-08]:** Pressing Back calls `unset_fn()` which clears `CharGenState.memorized_spells` to an empty array. Verified by inspection.

**AC-13 [reflection]:** A headless test enumerates every method listed in §5 and asserts `script.has_method(name) == true` for each. Any missing method fails the test with the specific name printed.

## 7. Performance Requirements

- Full grid render for 40 eligible spells: **< 30ms**
- Toggle-select → visual refresh → points label update: **< 8ms** (one frame at 120Hz)
- Description area update on hover: **< 4ms**
- State machine hook (`set_fn`, `unset_fn`): **< 5ms** each

## 8. Error Handling

- **Missing backend `spell_catalog`:** Treat as empty; call `handle_empty_catalog()`; log once; do not crash.
- **`level_1` entry missing required fields (`spell_id`, `display_name`):** Skip that entry, log once at DEBUG with the offending index; continue rendering the rest.
- **Backend marks `eligible == false`:** Render the slot greyed out / locked; clicking does nothing; tooltip reads "Not available to this class/alignment".
- **`picks_available_level_1 <= 0`:** Render the grid in read-only mode; DoneButton enabled immediately (no picks required); `comment_fn` appends nothing.
- **`CharGenState.memorized_spells` contains ids not present in the current catalog** (e.g. after backing into the stage and changing class): drop the unknown ids silently; restore only the still-valid selections; log once at DEBUG.
- **Unknown icon slug:** Fall back to a generic "arcane spell" placeholder icon; log once per unique missing slug.
- **Rapid toggle spam:** All per-slot handlers MUST be idempotent; repeated calls with the same value MUST be no-ops after the first.

## 9. Integration Points

**Godot (editable by this PRD):**
- `godot-client/scripts/ui/creation_step_spells.gd` — NEW (the stage script)
- `godot-client/scenes/creation_step_spells.tscn` — NEW scene with `SpellGridContainer`, `DescriptionArea`, `PointsRemainingLabel`, `DoneButton`, `BackButton`
- `godot-client/scripts/ui/creation_wizard.gd` — wire the stage into the parent state machine; parent PRD already reserves the slot
- `godot-client/tests/automation/godot/test_frontend_creation_spells.gd` — NEW headless acceptance test covering AC-01..AC-13

**Backend (consumed, NOT modified by this PRD):**
- `/game/campaigns/creation/start` — existing; returns `spell_catalog` in the creation response when class is mage-capable
- `/game/campaigns/creation/answer` — existing; may return an updated `spell_catalog` after class selection

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_spells.gd` MUST exercise AC-01 through AC-13 in order in a single run.
- Existing `run_headless_tests.gd` MUST stay green after this stage lands.
- Coverage goal: at least 80% of branches in `creation_step_spells.gd` exercised by the new test.

## 11. Verification

    # 1. Headless regression
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd

    # 2. New spell selection acceptance
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_spells.gd

Both MUST be green.

## 12. Implementation notes (non-binding)

- Use `GridContainer` with `columns = 6` to match the BG1 feel. Spell buttons are square (64×64) with an overlay label showing the school if known.
- Keep `_slot_state` as a parallel array to the catalog. Do NOT mutate catalog entries — they are shared read-only data from the backend response.
- The description area is a `RichTextLabel` with `bbcode_enabled = true` so that backend descriptions with inline formatting render correctly.
- For automation-bridge friendliness, every spell button MUST have `name = "Spell_%d" % index` so the automation test can target a specific slot by name.
- The "points remaining" label MUST be named `PointsRemainingLabel` (not `Points` or `Remaining`) so reflection tests can find it reliably.
- When the parent wizard's `creation_state_updated` signal fires, the stage refreshes the grid from the catalog — do NOT refresh if the stage is not currently active (guard with a `_is_active` flag set by `set_fn`/`unset_fn`).
- Do not memoize the spell catalog across stage re-entries; each time the player backs into the stage, call `load_spell_catalog()` fresh from the current backend response.

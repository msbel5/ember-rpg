# PRD: Frontend Creation — Gender (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **gender selection stage** of the BG1 character creation wizard — a minimal, first-stage widget that renders two radio buttons (Male / Female), updates a description text area on selection, enables the Done button only when a choice is made, writes the result to the shared `CharGenState.gender` field (1 = Male, 2 = Female mirroring BG1's IE_SEX convention), and hands control back to the parent wizard via its `next()` method. This stage has no backend call of its own — gender is carried forward in `CharGenState` and folded into the creation finalize payload at the end of the flow.

### Reference sources

- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\GUICG1.py` (79 LOC — `OnLoad`, `ClickedMale`, `ClickedFemale`, `NextPress`; uses `IE_GUI_BUTTON_RADIOBUTTON` flag pattern, `SetVarAssoc("Gender", n)`, `MakeDefault()` on Done, `SetPlayerStat(MyChar, IE_SEX, Gender)` on confirm)
- **GemRB behavior (parent state machine):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\CharGenCommon.py` (for `back()` and `next()` control flow)
- **Godot target (NEW):** `C:\Users\msbel\projects\ember-rpg\godot-client\scripts\ui\creation_step_gender.gd`
- **Companion scene (NEW):** `C:\Users\msbel\projects\ember-rpg\godot-client\scenes\creation_step_gender.tscn`

**Clean-room rule:** Read the GemRB source listed above to understand the behavior of each button and the control flow, but DO NOT copy, transliterate, or machine-translate any of its code. All GDScript in this PRD's implementation is newly authored. Per-PRD quote budget is at most 15 consecutive words from GemRB source, in quotation marks, and only when strictly necessary to anchor a behavior reference.

## 2. Scope

**In scope:**

- Two mutually-exclusive radio buttons labeled "Male" and "Female"
- A description `RichTextLabel` that updates on each selection with a flavor description
- A Done button that is disabled until a gender has been chosen and then advances via `parent_wizard.next()`
- A Back button that is visually present but disabled on this stage (gender is stage 0 per parent PRD §3 FR-05)
- Writing the chosen value to the parent wizard's `CharGenState.gender` via `update_state("gender", value)`
- The four state-machine hook methods demanded by the parent wizard (`set_fn`, `comment_fn`, `unset_fn`, `guard_fn`)
- Keyboard accessibility: `M` selects Male, `F` selects Female, `Enter` presses Done when enabled, `Escape` is forwarded to the parent wizard as cancel/back

**Out of scope:**

- Gender-dependent portrait filtering (handled later by the portrait stage sibling PRD)
- Gender-dependent sound set filtering (handled later by the sound stage sibling PRD)
- Any backend round-trip for gender alone (backend receives gender only as part of finalize payload)
- Transgender / non-binary expansion of the gender axis (parent PRD fixes BG1 semantics at two values; any expansion is a separate PRD)
- Body-type or voice-pitch sub-selections (not present in BG1)

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render exactly two buttons configured as a radio group such that selecting one deselects the other. The buttons MUST carry the labels "Male" and "Female" respectively and MUST be reachable by keyboard focus order (`MaleButton` before `FemaleButton`).

**FR-02:** On first render, neither button MUST be selected, the description area MUST show a neutral prompt (the string constant `PROMPT_SELECT_GENDER`), and the Done button MUST be disabled.

**FR-03:** Selecting the Male radio button MUST update the description area to `DESCRIPTION_MALE` and enable the Done button. The internal `_pending_gender` field MUST become `1`.

**FR-04:** Selecting the Female radio button MUST update the description area to `DESCRIPTION_FEMALE` and enable the Done button. The internal `_pending_gender` field MUST become `2`.

**FR-05:** Re-selecting the currently selected radio button MUST NOT emit a duplicate `gender_selected` signal and MUST be idempotent (no state churn).

**FR-06:** Pressing the Done button while the widget is in a non-disabled state MUST call `_commit_and_advance()`, which MUST (a) write `_pending_gender` to `CharGenState.gender` via `wizard.update_state("gender", _pending_gender)`, (b) emit `gender_confirmed(gender)`, and (c) invoke `wizard.next()` on the parent wizard reference supplied during `set_fn()`.

**FR-07:** The Back button MUST be rendered but MUST remain in the disabled state for the entire lifetime of this widget, because gender is stage 0 and the parent wizard forbids back-navigation from stage 0 (parent PRD §3 FR-05).

**FR-08:** Pressing `Escape` while the widget is focused MUST forward the event to `wizard.cancel()` (parent wizard handles the confirm-cancel UX). Pressing `Enter` MUST be equivalent to pressing Done when Done is enabled, and MUST be a no-op when Done is disabled.

**FR-09:** The widget MUST accept keyboard mnemonic `M` to select Male and `F` to select Female without any modifier keys. These keys MUST also update the description area to match FR-03 and FR-04.

**FR-10:** The `comment_fn(text_area)` hook MUST append a single human-readable line summarizing the chosen gender to the parent wizard's overview text area. If no gender has been chosen yet, `comment_fn` MUST be a no-op (the parent wizard only calls `comment_fn` after `set_fn` has seen at least one confirmed selection, but the implementation MUST be defensive).

**FR-11:** The `unset_fn()` hook MUST reset `_pending_gender` to `0`, clear the radio selection so that neither button is pressed, disable the Done button, and reset the description area to `PROMPT_SELECT_GENDER`. `unset_fn` MUST also call `wizard.update_state("gender", 0)` so the shared state reflects the cleared choice.

**FR-12:** The `guard_fn()` hook MUST always return `true` for this stage — gender is never skipped. This is explicit so the wizard's guard machinery does not accidentally skip stage 0.

**FR-13:** The `set_fn()` hook MUST accept the parent wizard reference (stored as `_wizard`), install button callbacks, render the initial neutral state (per FR-02), and focus the Male button so the first arrow-key press does not fall through to the wizard chrome.

## 4. Data Structures

Widget class and internal fields:

    class_name CreationStepGender extends PanelContainer

    # --- constants ---
    const GENDER_NONE: int = 0
    const GENDER_MALE: int = 1
    const GENDER_FEMALE: int = 2

    const PROMPT_SELECT_GENDER: String = "Choose a gender for your character."
    const DESCRIPTION_MALE: String = "Male characters begin with the BG1 male portrait set and male sound set."
    const DESCRIPTION_FEMALE: String = "Female characters begin with the BG1 female portrait set and female sound set."
    const SUMMARY_LINE_MALE: String = "Gender: Male"
    const SUMMARY_LINE_FEMALE: String = "Gender: Female"

    # --- nodes (set by _ready from scene children) ---
    var _male_button: Button
    var _female_button: Button
    var _done_button: Button
    var _back_button: Button
    var _description: RichTextLabel

    # --- state ---
    var _pending_gender: int = GENDER_NONE
    var _wizard: Object = null    # weak parent reference, holds next()/update_state()/cancel()

    # --- signals ---
    signal gender_selected(gender: int)       # fires on every change (1 or 2), not on idempotent re-clicks
    signal gender_confirmed(gender: int)      # fires once, when Done commits
    signal back_requested()                   # forwarded if Back were ever enabled (stage 0: never)

No new persistent datastructures in `GameState` — this stage writes to `CharGenState.gender` only, which already exists in the parent PRD §4.

## 5. Public API — methods that MUST exist

    # ---- construction ----
    func _ready() -> void
    func _input(event: InputEvent) -> void

    # ---- selection ----
    func select_male() -> void                    # called by radio button press or "M" key
    func select_female() -> void                  # called by radio button press or "F" key
    func clear_selection() -> void                # internal helper used by unset_fn

    # ---- commit / advance ----
    func on_done_pressed() -> void                # button callback -> _commit_and_advance
    func on_back_pressed() -> void                # button callback; stage 0: asserts false
    func _commit_and_advance() -> void            # writes state, emits gender_confirmed, calls wizard.next()

    # ---- rendering ----
    func render_initial_state() -> void           # used by set_fn and unset_fn to reset UI
    func render_description(text: String) -> void # updates the RichTextLabel
    func set_done_enabled(enabled: bool) -> void

    # ---- summary ----
    func build_summary_line(gender: int) -> String   # returns SUMMARY_LINE_MALE or SUMMARY_LINE_FEMALE or ""

    # ---- state machine hooks (parent wizard calls these) ----
    func set_fn() -> void                         # called by parent wizard on stage entry
    func comment_fn(text_area: RichTextLabel) -> void   # appends stage summary to overview
    func unset_fn() -> void                       # clears stage state on back
    func guard_fn() -> bool                       # returns whether stage is active (always true for gender)

    # ---- wizard plumbing ----
    func bind_wizard(wizard_ref: Object) -> void  # set _wizard; validates it exposes next/update_state/cancel
    func get_pending_gender() -> int              # accessor used by tests

    # ---- signals ----
    signal gender_selected(gender: int)
    signal gender_confirmed(gender: int)
    signal back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** On `_ready()`, the widget's child tree contains exactly one node named `MaleButton` and one node named `FemaleButton`, both of type `Button`. The two buttons are mutually exclusive (verified by programmatically pressing Male then Female and asserting `MaleButton.button_pressed == false` after `FemaleButton` is pressed).

**AC-02 [FR-02]:** Immediately after `_ready()`, `_pending_gender == 0`, `_done_button.disabled == true`, and the `_description.text` (or `get_parsed_text()`) exactly equals `PROMPT_SELECT_GENDER`.

**AC-03 [FR-03]:** After calling `select_male()`, `_pending_gender == 1`, `_done_button.disabled == false`, and the description equals `DESCRIPTION_MALE`. The `gender_selected` signal emitted exactly once with argument `1`.

**AC-04 [FR-04]:** After calling `select_female()`, `_pending_gender == 2`, `_done_button.disabled == false`, and the description equals `DESCRIPTION_FEMALE`. The `gender_selected` signal emitted exactly once with argument `2`.

**AC-05 [FR-05]:** Calling `select_male()` twice in succession emits `gender_selected` only once. Calling `select_male()` then `select_female()` then `select_female()` emits exactly two signals (one for each transition).

**AC-06 [FR-06]:** With a mock wizard bound that spies on `next()` and `update_state()`, calling `on_done_pressed()` after `select_male()` invokes `wizard.update_state("gender", 1)` exactly once and `wizard.next()` exactly once, in that order.

**AC-07 [FR-07]:** `_back_button.disabled == true` at all times during this widget's lifetime; after `select_male()`, `select_female()`, `on_done_pressed()`, and `unset_fn()`, Back remains disabled in every snapshot.

**AC-08 [FR-08]:** Sending an `InputEventKey` with `keycode == KEY_ESCAPE` to `_input()` causes the mock wizard's `cancel()` spy to fire exactly once. Sending `KEY_ENTER` while Done is disabled does NOT fire `wizard.next()`. Sending `KEY_ENTER` while Done is enabled fires `wizard.next()` exactly once.

**AC-09 [FR-09]:** Sending `InputEventKey` with `keycode == KEY_M` invokes the same state transitions as `select_male()` (verified by asserting `_pending_gender == 1` and description change). Same for `KEY_F` → female.

**AC-10 [FR-10]:** After `select_female()` followed by `on_done_pressed()`, calling `comment_fn(text_area)` appends `SUMMARY_LINE_FEMALE` to `text_area` via `append_text` (or `add_text` for plain `TextEdit`). Before any selection is committed, `comment_fn` MUST be a no-op (`text_area.get_parsed_text()` unchanged).

**AC-11 [FR-11]:** After `select_male()` then `unset_fn()`, `_pending_gender == 0`, `_male_button.button_pressed == false`, `_female_button.button_pressed == false`, `_done_button.disabled == true`, `_description.text == PROMPT_SELECT_GENDER`, and the mock wizard's `update_state` spy shows `update_state("gender", 0)` as the last call.

**AC-12 [FR-12]:** `guard_fn()` returns `true` unconditionally. Verified by calling it once before any selection and once after `select_male()`.

**AC-13 [FR-13]:** After calling `set_fn()` on a freshly instantiated widget (with a bound mock wizard), `_wizard` is non-null, the Male button callback is connected, the initial UI state matches AC-02, and `_male_button.has_focus() == true` (or the widget's focus target equals `_male_button`).

**AC-14 [reflection]:** Every method in §5 MUST exist on the script. Verified by reflection:

    for name in [
        "_ready", "_input",
        "select_male", "select_female", "clear_selection",
        "on_done_pressed", "on_back_pressed", "_commit_and_advance",
        "render_initial_state", "render_description", "set_done_enabled",
        "build_summary_line",
        "set_fn", "comment_fn", "unset_fn", "guard_fn",
        "bind_wizard", "get_pending_gender",
    ]:
        assert script.has_method(name) == true

## 7. Performance Requirements

- Radio button click → description repaint: **< 16 ms** (one 60 Hz frame).
- `set_fn()` cold entry (instantiation to first visible frame): **< 30 ms**.
- `_commit_and_advance()` to `wizard.next()` invocation: **< 5 ms** (no backend call, no I/O).
- `unset_fn()` full reset: **< 8 ms**.
- Memory: the widget MUST NOT leak nodes on repeated `set_fn` / `unset_fn` cycles. Verified by running 50 cycles and asserting child count returns to the post-`_ready` baseline.

## 8. Error Handling

- **Wizard reference missing:** If `on_done_pressed()` is invoked before `bind_wizard()` has stored a non-null reference, the widget MUST log `[creation_step_gender] wizard not bound; refusing to advance` at WARNING and NOT advance. This avoids hard crashes in isolation tests.
- **Wizard missing `next` / `update_state` / `cancel`:** `bind_wizard(wizard_ref)` MUST inspect the reference using `has_method` and log `[creation_step_gender] wizard missing required method <name>` at ERROR for each missing method, then still store the reference (so tests can supply partial mocks).
- **Invalid `_pending_gender` at commit time:** If `_commit_and_advance()` is invoked with `_pending_gender == GENDER_NONE`, the method MUST log at WARNING and return without calling `wizard.next()`. This is a defensive guard in case Done is reachable via an unknown input path.
- **Missing description RichTextLabel:** If `_description` is null at render time, `render_description()` MUST log once at WARNING and return without raising. The Done button state MUST still update correctly.
- **Back button accidentally clicked on stage 0:** `on_back_pressed()` MUST log `[creation_step_gender] back button pressed on stage 0 (no-op)` at INFO and do nothing. The button is disabled per FR-07; this handler is a safety net only.
- **Repeated `set_fn()` calls:** Calling `set_fn()` twice without `unset_fn()` in between MUST be idempotent — the second call MUST re-run `render_initial_state()` and return without duplicating signal connections. Verified by snapshotting Godot's connection count before and after.

## 9. Integration Points

**Godot (editable by this PRD):**

- `godot-client/scripts/ui/creation_step_gender.gd` — NEW script containing the widget class and all methods in §5
- `godot-client/scenes/creation_step_gender.tscn` — NEW scene defining the node layout (two Buttons, Done Button, Back Button, RichTextLabel description, VBoxContainer root)
- `godot-client/tests/automation/godot/test_frontend_creation_gender.gd` — NEW headless test covering AC-01..AC-14
- `docs/prd/active/PRD_frontend_character_creation_v1.md` — the parent PRD's §12 roadmap table may be updated to mark `gender` as `draft (this batch)` — this is advisory only, not required

**Backend (consumed, NOT modified):**

- This stage reads NO backend endpoints directly. The only persistent effect is on `CharGenState.gender`, which is folded into the eventual `/game/campaigns/creation/finalize` request assembled by the parent wizard.
- The parent wizard may consult `/game/campaigns/creation/catalog` for display strings, but that call is the parent wizard's concern and is out of scope for this PRD.

**Forbidden:**

- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `godot-client/tests/automation/godot/test_frontend_creation_gender.gd` MUST exercise AC-01 through AC-14 in a single headless run.
- Branch coverage: **≥ 80 %** of the new `creation_step_gender.gd` source. The only branches that may be excluded from the target are the error-handling early returns in §8, which MUST still be hit at least once each via an explicit negative-path test (missing wizard reference, null description node, `_pending_gender == GENDER_NONE` at commit).
- Existing `run_headless_tests.gd` MUST remain green (regression gate).
- No backend test changes are required because this stage has no backend round-trip.

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_gender.gd

Both runs MUST be green. If the second command fails with a "method not found" error, inspect the failing method name — that method is missing from `creation_step_gender.gd` and must be added before the PRD can be marked Implemented.

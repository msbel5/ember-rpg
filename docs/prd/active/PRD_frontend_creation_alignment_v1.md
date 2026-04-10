# PRD: Frontend Creation — Alignment (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **alignment selection stage**. A 3×3 grid of the nine classic D&D alignments (LG/NG/CG / LN/TN/CN / LE/NE/CE). Alignments disallowed by the chosen class are greyed out (e.g. Paladin only LG, Ranger only Good, Druid only True Neutral). Selecting writes to `CharGenState.alignment` using ember canonical keys ("lg", "ng", "cg", "ln", "tn", "cn", "le", "ne", "ce").

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\GUICG4.py` (357 LOC — shared alignment picker across BG1/BG2/IWD)
- **Godot target:** NEW `godot-client/scripts/ui/creation_step_alignment.gd` + NEW `godot-client/scenes/creation_step_alignment.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- 3×3 grid of 9 alignment buttons
- Class-based eligibility filter (greyed-out for disallowed)
- Description panel updates on hover/selection
- Done button gated on selection
- Writes to `CharGenState.alignment`
- State machine hooks

**Out of scope:**
- Alignment change during gameplay (backend narrative authority)
- Alignment impact on reputation (backend)

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render 9 alignment buttons in a 3×3 grid layout.

**FR-02:** On stage entry, `CharGenState.class_id` MUST be read to determine which alignments are allowed. Disallowed cells MUST be visually dimmed and disabled.

**FR-03:** Hovering a cell MUST update a side description panel with the alignment's flavor text.

**FR-04:** Clicking an allowed cell MUST select it (visual highlight), enable Done, and update the description to the selected alignment.

**FR-05:** Clicking a disallowed cell MUST be a no-op with a toast "Your class does not allow this alignment".

**FR-06:** Pressing Done MUST call parent `update_state("alignment", alignment_id)` and `next()`.

**FR-07:** Paladin MUST only allow LG. Ranger MUST only allow LG, NG, CG. Druid MUST only allow TN. Monk MUST only allow LG, LN, LE (if present). All other classes allow all 9.

**FR-08:** `unset_fn()` MUST clear `CharGenState.alignment` on back.

**FR-09:** `comment_fn(text_area)` MUST append "Alignment: <Alignment Name>" to the overview.

**FR-10:** Keyboard hotkeys: `1..9` for the 9 cells (1=LG, 2=NG, 3=CG, 4=LN, 5=TN, 6=CN, 7=LE, 8=NE, 9=CE).

## 4. Data Structures

    class_name CreationStepAlignment extends PanelContainer
    
    const ALIGNMENTS := [
        {"id": "lg", "name": "Lawful Good",    "desc": "A lawful good character acts with compassion and upholds order."},
        {"id": "ng", "name": "Neutral Good",   "desc": "A neutral good character does the best a good person can."},
        {"id": "cg", "name": "Chaotic Good",   "desc": "A chaotic good character acts as conscience directs, with little regard for what others expect."},
        {"id": "ln", "name": "Lawful Neutral", "desc": "A lawful neutral character acts by law, tradition, or code."},
        {"id": "tn", "name": "True Neutral",   "desc": "A true neutral character keeps the balance in all things."},
        {"id": "cn", "name": "Chaotic Neutral","desc": "A chaotic neutral character follows whim, freedom above all."},
        {"id": "le", "name": "Lawful Evil",    "desc": "A lawful evil character takes what he wants, within the limits of his code."},
        {"id": "ne", "name": "Neutral Evil",   "desc": "A neutral evil character does whatever he can get away with."},
        {"id": "ce", "name": "Chaotic Evil",   "desc": "A chaotic evil character does whatever greed, hatred, and lust for destruction drive him to do."},
    ]
    
    const CLASS_ALIGNMENT_RESTRICTIONS := {
        "paladin": ["lg"],
        "ranger":  ["lg", "ng", "cg"],
        "druid":   ["tn"],
        "monk":    ["lg", "ln", "le"],
    }
    
    const HOTKEYS := {
        KEY_1: "lg", KEY_2: "ng", KEY_3: "cg",
        KEY_4: "ln", KEY_5: "tn", KEY_6: "cn",
        KEY_7: "le", KEY_8: "ne", KEY_9: "ce",
    }
    
    var _pending_alignment: String = ""
    var _cell_buttons: Dictionary = {}
    var _description_label: RichTextLabel
    var _done_button: Button
    var _back_button: Button
    var _parent_wizard: Object = null

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # parent wiring
    func bind_parent_wizard(wizard: Object) -> void
    func open_stage() -> void
    
    # grid rendering
    func build_alignment_grid() -> void
    func apply_class_restrictions() -> void
    func refresh_cell_states() -> void
    
    # selection
    func select_alignment(alignment_id: String) -> void
    func get_selected_alignment() -> String
    func clear_selection() -> void
    func is_alignment_selected() -> bool
    func is_alignment_allowed(alignment_id: String) -> bool
    func get_allowed_alignments_for_class(class_id: String) -> Array
    
    # description
    func update_description_for(alignment_id: String) -> void
    func on_cell_hover(alignment_id: String) -> void
    func on_cell_hover_end(alignment_id: String) -> void
    
    # confirm / back
    func on_done_pressed() -> void
    func on_back_pressed() -> void
    
    # state machine hooks
    func set_fn() -> void
    func comment_fn(text_area: RichTextLabel) -> void
    func unset_fn() -> void
    func guard_fn() -> bool                                                      # always true
    
    # signals
    signal alignment_selected(alignment_id: String)
    signal stage_advanced()
    signal stage_back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `open_stage()`, `_cell_buttons.size() == 9`.

**AC-02 [FR-07]:** With class="paladin", `get_allowed_alignments_for_class("paladin") == ["lg"]`.

**AC-03 [FR-02]:** After `apply_class_restrictions()` with class="druid", cells for all alignments except "tn" are disabled.

**AC-04 [FR-04]:** Clicking the LG cell with class="fighter" sets `_pending_alignment == "lg"` and enables Done.

**AC-05 [FR-05]:** Clicking LE with class="paladin" MUST NOT change `_pending_alignment` and MUST emit no `alignment_selected` signal.

**AC-06 [FR-06]:** Pressing Done after selecting NG calls parent `update_state("alignment", "ng")` and `next()`.

**AC-07 [FR-10]:** Pressing `5` via `_input` calls `select_alignment("tn")` if allowed.

**AC-08 [FR-08]:** `unset_fn()` clears `CharGenState.alignment`.

**AC-09 [FR-09]:** `comment_fn(text_area)` after selecting CG appends "Alignment: Chaotic Good".

**AC-10 [is_alignment_allowed]:** `is_alignment_allowed("lg") == true` for Paladin, `is_alignment_allowed("ce") == false` for Paladin.

**AC-11 [reflection]:** Every method in §5 MUST exist on the script:
`["_ready", "_input", "bind_parent_wizard", "open_stage", "build_alignment_grid", "apply_class_restrictions", "refresh_cell_states", "select_alignment", "get_selected_alignment", "clear_selection", "is_alignment_selected", "is_alignment_allowed", "get_allowed_alignments_for_class", "update_description_for", "on_cell_hover", "on_cell_hover_end", "on_done_pressed", "on_back_pressed", "set_fn", "comment_fn", "unset_fn", "guard_fn"]`

## 7. Performance Requirements

- `open_stage()`: **< 20ms**
- Grid build + class restrictions: **< 10ms**
- Selection + description update: **< 10ms**

## 8. Error Handling

- Missing class_id: assume all alignments allowed, log at WARNING
- Unknown alignment_id in `select_alignment`: no-op, log at DEBUG
- Hotkey press on disabled cell: show toast, do not select

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_step_alignment.gd` — NEW
- `godot-client/scenes/creation_step_alignment.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_creation_alignment.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_alignment.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_alignment.gd

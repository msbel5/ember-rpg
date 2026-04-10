# PRD: Frontend Dual-Class Panel (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **dual-class panel** — used at runtime from the character record screen to switch a human character's class to a second class, retaining the old class's abilities at current level but from then on advancing in the new class. BG1/AD&D 2e rules: only humans can dual-class; requires ability score minimums for both classes; old class abilities locked until new class exceeds old class level. This is NOT a creation stage — it's a runtime panel opened from `character_panel.gd` via the Dual Class button.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\DualClass.py` (639 LOC — full dual-class flow)
- **Godot target:** NEW `godot-client/scripts/ui/dual_class_panel.gd` + NEW `godot-client/scenes/dual_class_panel.tscn`
- **Integration:** Opened from `character_panel.gd` via `panel_requested.emit("dual_class")` (per `PRD_frontend_character_record_v1.md` FR-10)

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- List of eligible new classes filtered by PC's stats
- Per-row eligibility info (ability minimums, race check)
- Description panel showing selected class details
- Confirm dual-class button with backend call
- Cancel button closes panel without changes
- Error display (race not human, minimums not met, already multi-class)

**Out of scope:**
- Triple-classing (not in BG1/AD&D 2e)
- Un-dualing (irreversible in BG1)
- Class abilities at each intermediate level

## 3. Functional Requirements (FR)

**FR-01:** The panel MUST check `GameState.character_sheet.race == "human"` and `is_multi_class == false`. If either fails, render a disabled state with reason.

**FR-02:** `_eligible_classes` MUST be computed by checking: (a) class is a single class (no multi-class targets), (b) old class ≠ new class, (c) race allows it, (d) ability score minimums met.

**FR-03:** The panel MUST render an eligible class list. Each row shows the class name, ability score requirements, and whether each requirement is met.

**FR-04:** Hovering a row updates a side description panel with full class details.

**FR-05:** Clicking a row selects it and enables the Confirm button.

**FR-06:** Pressing Confirm MUST show a secondary confirmation modal ("Are you sure? Old class abilities will be locked until new class exceeds old class level.") with Yes/No.

**FR-07:** Yes MUST submit backend command `dual_class <pc_id> <new_class_id>` and close the panel.

**FR-08:** No MUST return to the class list view.

**FR-09:** Cancel MUST close the panel without any backend call.

**FR-10:** The panel MUST refresh on `GameState.character_sheet_updated` and `GameState.state_updated`.

## 4. Data Structures

    class_name DualClassPanel extends PanelContainer
    
    const CLASS_ABILITY_MINIMUMS := {
        "fighter": {"str": 15},
        "ranger":  {"str": 13, "dex": 13, "con": 14, "wis": 14},
        "paladin": {"str": 12, "con": 9, "wis": 13, "cha": 17},
        "cleric":  {"wis": 17},
        "druid":   {"wis": 17, "cha": 15},
        "mage":    {"int": 17},
        "thief":   {"dex": 17},
        "bard":    {"int": 13, "dex": 12, "cha": 15},
    }
    
    var _eligible_classes: Array = []
    var _selected_class_id: String = ""
    var _active_pc_id: String = ""
    var _class_list_container: VBoxContainer
    var _description_label: RichTextLabel
    var _confirm_button: Button
    var _cancel_button: Button
    var _confirmation_modal: AcceptDialog

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # open / close
    func open_for_pc(pc_id: String) -> void
    func close_panel() -> void
    func is_open() -> bool
    
    # eligibility
    func validate_dual_class_eligibility(pc_id: String) -> Dictionary            # {eligible: bool, reason: String}
    func compute_eligible_classes(pc_id: String) -> Array
    func check_ability_minimums(pc_id: String, class_id: String) -> Dictionary   # {met: bool, missing: Array}
    func is_human(pc_id: String) -> bool
    func is_already_multi_class(pc_id: String) -> bool
    func get_current_class_id(pc_id: String) -> String
    
    # rendering
    func render_eligible_list() -> void
    func render_class_row(class_entry: Dictionary) -> Control
    func render_ineligible_state(reason: String) -> void
    func update_description_for(class_id: String) -> void
    
    # selection
    func select_new_class(class_id: String) -> void
    func get_selected_class() -> String
    func clear_selection() -> void
    
    # confirm / cancel
    func open_confirmation_modal() -> void
    func confirm_dual_class() -> void
    func cancel_dual_class() -> void
    func on_confirmation_yes() -> void
    func on_confirmation_no() -> void
    func on_cancel_pressed() -> void
    
    # refresh
    func refresh_on_state_update() -> void
    
    # signals
    signal dual_class_committed(pc_id: String, new_class_id: String)
    signal dual_class_canceled()
    signal panel_closed()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** `validate_dual_class_eligibility("pc_dwarf")` returns `{eligible: false, reason: <contains "human">}`.

**AC-02 [FR-01]:** `validate_dual_class_eligibility("pc_multi")` returns `{eligible: false, reason: <contains "multi">}`.

**AC-03 [FR-02]:** `compute_eligible_classes("pc_fighter_human")` returns a list that does NOT contain "fighter" (self).

**AC-04 [FR-02]:** `check_ability_minimums("pc_weak", "paladin")` returns `{met: false, missing: [...]}` when stats are below minimums.

**AC-05 [FR-04]:** Hovering a class row updates `_description_label.text` to contain the class name.

**AC-06 [FR-05]:** Selecting a class sets `_selected_class_id` and enables `_confirm_button`.

**AC-07 [FR-06]:** Pressing Confirm opens `_confirmation_modal` which is visible.

**AC-08 [FR-07]:** Pressing Yes in the confirmation modal emits `dual_class_committed(pc_id, class_id)` and closes the panel.

**AC-09 [FR-08]:** Pressing No in the modal hides the modal without emitting the commit signal.

**AC-10 [FR-09]:** Pressing Cancel closes the panel WITHOUT opening the confirmation modal.

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "open_for_pc", "close_panel", "is_open", "validate_dual_class_eligibility", "compute_eligible_classes", "check_ability_minimums", "is_human", "is_already_multi_class", "get_current_class_id", "render_eligible_list", "render_class_row", "render_ineligible_state", "update_description_for", "select_new_class", "get_selected_class", "clear_selection", "open_confirmation_modal", "confirm_dual_class", "cancel_dual_class", "on_confirmation_yes", "on_confirmation_no", "on_cancel_pressed", "refresh_on_state_update"]`

## 7. Performance Requirements

- `open_for_pc()`: **< 50ms**
- Eligibility compute for 8 classes: **< 10ms**
- Confirmation modal open: **< 30ms**

## 8. Error Handling

- Missing character_sheet for pc_id: render error "Character data unavailable", disable Confirm
- Backend command failure: show toast with error, keep panel open
- Invalid class_id: no-op, log at DEBUG

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/dual_class_panel.gd` — NEW
- `godot-client/scenes/dual_class_panel.tscn` — NEW
- `godot-client/scripts/ui/character_panel.gd` — route `panel_requested("dual_class")` to open this (no code change needed if routed via modal_host)
- `godot-client/tests/automation/godot/test_frontend_dual_class.gd` — NEW

**Backend (consumed, NOT modified):**
- `GameState.character_sheet` — read-only
- Command: `dual_class <pc_id> <new_class_id>`

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)
- No client-side rules enforcement beyond display — backend remains authority on eligibility

## 10. Test Coverage Target

- `test_frontend_dual_class.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_dual_class.gd

# PRD: Frontend Creation — Thief/Bard Skills (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **thief/bard skills allocation stage**. Players of thief-class characters (Thief, Bard, or multi-class containing either) distribute a pool of points across thief skills: Pick Pockets, Open Locks, Find/Remove Traps, Move Silently, Hide in Shadows, Detect Illusion, Set Traps. +/- buttons per skill adjust allocation. Total points come from class base + INT bonus. Done is disabled until all points are allocated. `guard_fn()` returns false for non-thief-like classes.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\GUICG6.py` (70 LOC — BG1-specific) + `gemrb/GUIScripts/LUSkillsSelection.py` (449 LOC — shared level-up skills helper, also used by creation)
- **Godot target:** NEW `godot-client/scripts/ui/creation_step_skills.gd` + NEW `godot-client/scenes/creation_step_skills.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- 7 thief skill rows with +/- buttons
- Points-remaining label
- Done disabled until 0 remaining
- Guard: stage skipped for non-thief classes
- Writes `CharGenState.skills`
- State machine hooks

**Out of scope:**
- Class skills other than thief (backend handles general class abilities)
- Skill improvement on level-up (separate `PRD_frontend_level_up_v1.md`)

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render 7 skill rows: pick_pockets, open_locks, find_traps, move_silently, hide_in_shadows, detect_illusion, set_traps.

**FR-02:** Each row has: label, current value, minus button, plus button, +/- disabled states.

**FR-03:** A "Points Remaining" label at the top MUST track unspent points.

**FR-04:** Initial point pool = class base (varies) + INT bonus (from `CharGenState.ability_scores.int.value`). Bard gets half.

**FR-05:** `+` adds 1 point to that skill (limit: remaining > 0 and skill <= 100). `-` subtracts 1 (limit: skill > 0).

**FR-06:** Done button is disabled until `points_remaining == 0`.

**FR-07:** `guard_fn()` MUST return false if `CharGenState.class_id` does NOT contain "thief" OR "bard". The parent wizard skips this stage entirely.

**FR-08:** Pressing Done calls parent `update_state("skills", skills_dict)` and `next()`.

**FR-09:** `unset_fn()` clears `CharGenState.skills` on back.

**FR-10:** `comment_fn(text_area)` MUST summarize allocated skills in the overview.

## 4. Data Structures

    class_name CreationStepSkills extends PanelContainer
    
    const THIEF_SKILLS := [
        {"id": "pick_pockets",    "name": "Pick Pockets"},
        {"id": "open_locks",      "name": "Open Locks"},
        {"id": "find_traps",      "name": "Find/Remove Traps"},
        {"id": "move_silently",   "name": "Move Silently"},
        {"id": "hide_in_shadows", "name": "Hide in Shadows"},
        {"id": "detect_illusion", "name": "Detect Illusion"},
        {"id": "set_traps",       "name": "Set Traps"},
    ]
    
    const MAX_SKILL_VALUE := 100
    
    const CLASS_BASE_POINTS := {
        "thief":              40,
        "bard":               20,
        "fighter_thief":      40,
        "mage_thief":         40,
        "cleric_thief":       40,
        "fighter_mage_thief": 40,
    }
    
    var _skill_values: Dictionary = {}            # {id: int}
    var _points_remaining: int = 0
    var _initial_pool: int = 0
    var _parent_wizard: Object = null
    var _skill_rows: Dictionary = {}               # id -> row node
    var _remaining_label: Label
    var _done_button: Button
    var _back_button: Button

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # parent wiring
    func bind_parent_wizard(wizard: Object) -> void
    func open_stage() -> void
    
    # point pool
    func compute_initial_pool() -> int                                           # class base + INT bonus
    func get_class_base_points(class_id: String) -> int
    func get_int_bonus_points(int_value: int) -> int
    func reset_skills_to_zero() -> void
    
    # skill allocation
    func increase_skill(skill_id: String) -> bool                                # returns true on success
    func decrease_skill(skill_id: String) -> bool
    func get_skill_value(skill_id: String) -> int
    func set_skill_value(skill_id: String, value: int) -> void
    func get_points_remaining() -> int
    func is_allocation_complete() -> bool
    
    # rendering
    func render_skill_rows() -> void
    func refresh_skill_row(skill_id: String) -> void
    func refresh_remaining_label() -> void
    func refresh_done_button_state() -> void
    
    # confirm / back
    func on_done_pressed() -> void
    func on_back_pressed() -> void
    
    # state machine hooks
    func set_fn() -> void
    func comment_fn(text_area: RichTextLabel) -> void
    func unset_fn() -> void
    func guard_fn() -> bool                                                      # false for non-thief classes
    
    # signals
    signal skill_value_changed(skill_id: String, new_value: int)
    signal allocation_complete()
    signal stage_advanced()
    signal stage_back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `render_skill_rows()`, `_skill_rows.size() == 7`.

**AC-02 [FR-04]:** With class="thief" and int=18, `compute_initial_pool()` returns `40 + INT_bonus(18)` (let bonus be ≥0).

**AC-03 [FR-05]:** After `reset_skills_to_zero()` with pool=40, calling `increase_skill("pick_pockets")` sets `_skill_values["pick_pockets"] == 1` and `_points_remaining == 39`.

**AC-04 [FR-05]:** Calling `decrease_skill("pick_pockets")` after the above sets value back to 0 and points to 40.

**AC-05 [FR-05]:** Cannot increase above MAX_SKILL_VALUE=100. Cannot decrease below 0.

**AC-06 [FR-06]:** With `_points_remaining > 0`, `_done_button.disabled == true`. After full allocation, `_done_button.disabled == false`.

**AC-07 [FR-07]:** `guard_fn()` with class_id="fighter" returns false. With "thief" returns true. With "fighter_thief" returns true.

**AC-08 [FR-08]:** Pressing Done with full allocation calls parent `update_state("skills", {...})` and `next()`.

**AC-09 [FR-09]:** `unset_fn()` clears `CharGenState.skills`.

**AC-10 [FR-10]:** `comment_fn(text_area)` appends a line containing "Skills:" and at least one skill name.

**AC-11 [reflection]:** Every method in §5 MUST exist on the script:
`["_ready", "_input", "bind_parent_wizard", "open_stage", "compute_initial_pool", "get_class_base_points", "get_int_bonus_points", "reset_skills_to_zero", "increase_skill", "decrease_skill", "get_skill_value", "set_skill_value", "get_points_remaining", "is_allocation_complete", "render_skill_rows", "refresh_skill_row", "refresh_remaining_label", "refresh_done_button_state", "on_done_pressed", "on_back_pressed", "set_fn", "comment_fn", "unset_fn", "guard_fn"]`

## 7. Performance Requirements

- `open_stage()`: **< 20ms**
- `increase_skill` / `decrease_skill`: **< 5ms**
- `render_skill_rows()` for 7 rows: **< 10ms**

## 8. Error Handling

- Missing class_id in CharGenState: treat as non-thief, `guard_fn` returns false
- Unknown skill_id: no-op, log at DEBUG
- Missing INT in ability_scores: use INT bonus = 0, log at WARNING

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_step_skills.gd` — NEW
- `godot-client/scenes/creation_step_skills.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_creation_skills.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_skills.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_skills.gd

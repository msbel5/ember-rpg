# PRD: Frontend Creation — Weapon Proficiencies (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **weapon proficiency allocation stage**. Players distribute starting proficiency points across weapon types. Each weapon row shows current star count (0-5) with +/- buttons. Class-dependent rules: Fighters start with 4 slots and can have up to 2 stars per weapon in BG1 (grandmaster cap 2). Thieves/Mages/Clerics get 2 slots, 1 star cap. Done is disabled until all points are spent.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\GUICG7.py` (51 LOC — BG1 proficiency picker) + `gemrb/GUIScripts/LUProfsSelection.py` (475 LOC — shared with level-up)
- **Godot target:** NEW `godot-client/scripts/ui/creation_step_proficiencies.gd` + NEW `godot-client/scenes/creation_step_proficiencies.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Scrollable list of weapon type rows with star count + +/- buttons
- Points-remaining label
- Per-class slot budget and per-weapon star cap
- Done gated on complete allocation
- Writes `CharGenState.proficiencies`
- State machine hooks

**Out of scope:**
- Proficiency improvement on level-up (separate PRD)
- Non-weapon proficiencies (BG2+; out of scope for BG1)

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render rows for every weapon type in `WEAPON_TYPES`: Long Sword, Bastard Sword, Two-Handed Sword, Short Sword, Dagger, Axe, Hammer, Mace, Flail, Quarterstaff, Spear, Halberd, Long Bow, Short Bow, Crossbow, Sling, Dart.

**FR-02:** Each row has: label, star display (5-star graphic), minus button, plus button.

**FR-03:** "Points Remaining" label tracks unspent slots.

**FR-04:** Initial slot budget is class-based: Fighter/Ranger/Paladin=4, Cleric/Druid=2, Mage/Thief=1, Bard=2. Multi-class picks the max across components.

**FR-05:** Per-weapon star cap: Fighter/Ranger/Paladin=2 (specialization), all others=1.

**FR-06:** `+` on a row adds a star (gated by remaining > 0 AND current star < cap).

**FR-07:** `-` on a row removes a star (gated by current star > 0).

**FR-08:** Done button enabled only when `points_remaining == 0`.

**FR-09:** Pressing Done calls parent `update_state("proficiencies", profs_dict)` and `next()`.

**FR-10:** `guard_fn()` MUST always return true (every class gets starting profs).

**FR-11:** `unset_fn()` clears `CharGenState.proficiencies` on back.

**FR-12:** `comment_fn(text_area)` appends a line summarizing which weapons got stars.

## 4. Data Structures

    class_name CreationStepProficiencies extends PanelContainer
    
    const WEAPON_TYPES := [
        {"id": "long_sword",        "name": "Long Sword"},
        {"id": "bastard_sword",     "name": "Bastard Sword"},
        {"id": "two_handed_sword",  "name": "Two-Handed Sword"},
        {"id": "short_sword",       "name": "Short Sword"},
        {"id": "dagger",            "name": "Dagger"},
        {"id": "axe",               "name": "Axe"},
        {"id": "hammer",            "name": "Hammer"},
        {"id": "mace",              "name": "Mace"},
        {"id": "flail",             "name": "Flail"},
        {"id": "quarterstaff",      "name": "Quarterstaff"},
        {"id": "spear",             "name": "Spear"},
        {"id": "halberd",           "name": "Halberd"},
        {"id": "long_bow",          "name": "Long Bow"},
        {"id": "short_bow",         "name": "Short Bow"},
        {"id": "crossbow",          "name": "Crossbow"},
        {"id": "sling",             "name": "Sling"},
        {"id": "dart",              "name": "Dart"},
    ]
    
    const CLASS_SLOT_BUDGET := {
        "fighter": 4, "ranger": 4, "paladin": 4,
        "cleric": 2, "druid": 2,
        "mage": 1, "thief": 1, "bard": 2,
    }
    
    const CLASS_STAR_CAP := {
        "fighter": 2, "ranger": 2, "paladin": 2,
        "cleric": 1, "druid": 1,
        "mage": 1, "thief": 1, "bard": 1,
    }
    
    var _stars: Dictionary = {}                    # weapon_id -> star count
    var _points_remaining: int = 0
    var _initial_budget: int = 0
    var _parent_wizard: Object = null
    var _weapon_rows: Dictionary = {}
    var _remaining_label: Label
    var _done_button: Button
    var _back_button: Button

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # parent wiring
    func bind_parent_wizard(wizard: Object) -> void
    func open_stage() -> void
    
    # budget computation
    func compute_class_slot_budget(class_id: String, components: Array) -> int
    func compute_class_star_cap(class_id: String, components: Array) -> int
    func reset_stars_to_zero() -> void
    
    # star allocation
    func increase_star(weapon_id: String) -> bool
    func decrease_star(weapon_id: String) -> bool
    func get_star_count(weapon_id: String) -> int
    func set_star_count(weapon_id: String, stars: int) -> void
    func get_points_remaining() -> int
    func is_allocation_complete() -> bool
    func get_star_cap() -> int
    
    # rendering
    func render_weapon_rows() -> void
    func refresh_weapon_row(weapon_id: String) -> void
    func refresh_star_display(weapon_id: String, stars: int) -> void
    func refresh_remaining_label() -> void
    func refresh_done_button_state() -> void
    
    # confirm / back
    func on_done_pressed() -> void
    func on_back_pressed() -> void
    
    # state machine hooks
    func set_fn() -> void
    func comment_fn(text_area: RichTextLabel) -> void
    func unset_fn() -> void
    func guard_fn() -> bool                                                      # always true
    
    # signals
    signal star_changed(weapon_id: String, new_stars: int)
    signal allocation_complete()
    signal stage_advanced()
    signal stage_back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** `_weapon_rows.size() == 17`.

**AC-02 [FR-04]:** `compute_class_slot_budget("fighter", ["fighter"]) == 4`. `compute_class_slot_budget("mage", ["mage"]) == 1`.

**AC-03 [FR-04 multi-class]:** `compute_class_slot_budget("fighter_mage", ["fighter", "mage"]) == 4` (max across components).

**AC-04 [FR-05]:** `compute_class_star_cap("fighter", ["fighter"]) == 2`, `compute_class_star_cap("thief", ["thief"]) == 1`.

**AC-05 [FR-06, FR-07]:** With Fighter budget=4 cap=2, `increase_star("long_sword")` twice succeeds, third call fails. `decrease_star("long_sword")` twice succeeds.

**AC-06 [FR-08]:** Done is disabled while `_points_remaining > 0`, enabled when 0.

**AC-07 [FR-09]:** Pressing Done with full allocation calls parent `update_state("proficiencies", {...})` and `next()`.

**AC-08 [FR-10]:** `guard_fn()` returns true for every class.

**AC-09 [FR-11]:** `unset_fn()` clears `CharGenState.proficiencies`.

**AC-10 [FR-12]:** `comment_fn(text_area)` appends a line containing weapon names that have stars > 0.

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "bind_parent_wizard", "open_stage", "compute_class_slot_budget", "compute_class_star_cap", "reset_stars_to_zero", "increase_star", "decrease_star", "get_star_count", "set_star_count", "get_points_remaining", "is_allocation_complete", "get_star_cap", "render_weapon_rows", "refresh_weapon_row", "refresh_star_display", "refresh_remaining_label", "refresh_done_button_state", "on_done_pressed", "on_back_pressed", "set_fn", "comment_fn", "unset_fn", "guard_fn"]`

## 7. Performance Requirements

- `open_stage()`: **< 30ms**
- `render_weapon_rows()` for 17 rows: **< 15ms**
- `increase_star` / `decrease_star`: **< 5ms**

## 8. Error Handling

- Missing class_id: default to Fighter budget (4 slots, cap 2), log at WARNING
- Unknown weapon_id: no-op, log at DEBUG
- Decrease on zero star: no-op

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_step_proficiencies.gd` — NEW
- `godot-client/scenes/creation_step_proficiencies.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_creation_proficiencies.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_proficiencies.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_proficiencies.gd

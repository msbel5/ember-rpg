# PRD: Frontend Creation — Class (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **class selection stage**. The player picks a single class OR a multi-class combination (only allowed by races other than Human). The list is filtered by `CharGenState.race`'s class restrictions (from the race stage). Each row shows class description, HP die, weapon proficiencies, starting abilities. Multi-class rows (e.g. Fighter/Mage) show the combined profile. Selecting writes to `CharGenState.class_id` and `CharGenState.is_multi_class`.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\GUICG3.py` (88 LOC — class picker) + `bg1/GUICG10.py` (109 LOC — multi-class variants)
- **Godot target:** NEW `godot-client/scripts/ui/creation_step_class.gd` + NEW `godot-client/scenes/creation_step_class.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Scrollable list of class rows (single and multi-class)
- Filter by `CharGenState.race` class restrictions (e.g. Dwarf hides Paladin/Mage/Sorcerer)
- Description panel with class details on selection
- Done button gated on selection
- Writes `CharGenState.class_id` + `is_multi_class` + `multi_class_components`
- State machine hooks

**Out of scope:**
- Kit selection (BG2-only; not applicable to BG1)
- Dual-class initiation (separate PRD `PRD_frontend_dual_class_v1.md`)
- Spell selection for casters (deferred to spells stage)

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render a scrollable list of class options filtered by `CharGenState.race`.

**FR-02:** Single classes: Fighter, Ranger, Paladin, Cleric, Druid, Mage, Thief, Bard. Multi-class: Fighter/Thief, Fighter/Mage, Fighter/Cleric, Fighter/Mage/Thief, Fighter/Mage/Cleric, Cleric/Thief, Cleric/Mage, Cleric/Ranger, Mage/Thief, Fighter/Druid (BG1 canonical pairs).

**FR-03:** Each row MUST display class name, HP die (d6/d8/d10), one-line summary.

**FR-04:** Selecting a row MUST update the description panel with: full description, weapon profs, starting spells (if caster), armor restrictions, XP cap (BG1).

**FR-05:** Multi-class rows MUST be visible only if `CharGenState.race != "human"`.

**FR-06:** Classes in `CharGenState.get_class_restrictions_for(race)` MUST be hidden (not just disabled).

**FR-07:** Done button MUST be disabled until a row is selected.

**FR-08:** Pressing Done MUST write `CharGenState.class_id`, `CharGenState.is_multi_class`, and `CharGenState.multi_class_components` (array of component class IDs), then call parent `next()`.

**FR-09:** `unset_fn()` MUST clear all three fields on back navigation.

**FR-10:** `comment_fn(text_area)` MUST append "Class: <Class Name>" to the overview.

## 4. Data Structures

    class_name CreationStepClass extends PanelContainer
    
    const SINGLE_CLASSES := [
        {"id": "fighter",  "name": "Fighter",  "hp_die": 10, "components": ["fighter"]},
        {"id": "ranger",   "name": "Ranger",   "hp_die": 10, "components": ["ranger"]},
        {"id": "paladin",  "name": "Paladin",  "hp_die": 10, "components": ["paladin"]},
        {"id": "cleric",   "name": "Cleric",   "hp_die": 8,  "components": ["cleric"]},
        {"id": "druid",    "name": "Druid",    "hp_die": 8,  "components": ["druid"]},
        {"id": "mage",     "name": "Mage",     "hp_die": 4,  "components": ["mage"]},
        {"id": "thief",    "name": "Thief",    "hp_die": 6,  "components": ["thief"]},
        {"id": "bard",     "name": "Bard",     "hp_die": 6,  "components": ["bard"]},
    ]
    
    const MULTI_CLASSES := [
        {"id": "fighter_thief",          "name": "Fighter/Thief",          "hp_die": 8, "components": ["fighter","thief"]},
        {"id": "fighter_mage",           "name": "Fighter/Mage",           "hp_die": 7, "components": ["fighter","mage"]},
        {"id": "fighter_cleric",         "name": "Fighter/Cleric",         "hp_die": 9, "components": ["fighter","cleric"]},
        {"id": "fighter_mage_thief",     "name": "Fighter/Mage/Thief",     "hp_die": 7, "components": ["fighter","mage","thief"]},
        {"id": "fighter_mage_cleric",    "name": "Fighter/Mage/Cleric",    "hp_die": 7, "components": ["fighter","mage","cleric"]},
        {"id": "cleric_thief",           "name": "Cleric/Thief",           "hp_die": 7, "components": ["cleric","thief"]},
        {"id": "cleric_mage",            "name": "Cleric/Mage",            "hp_die": 6, "components": ["cleric","mage"]},
        {"id": "cleric_ranger",          "name": "Cleric/Ranger",          "hp_die": 9, "components": ["cleric","ranger"]},
        {"id": "mage_thief",             "name": "Mage/Thief",             "hp_die": 5, "components": ["mage","thief"]},
        {"id": "fighter_druid",          "name": "Fighter/Druid",          "hp_die": 9, "components": ["fighter","druid"]},
    ]
    
    var _pending_class_id: String = ""
    var _pending_components: Array[String] = []
    var _class_rows: Dictionary = {}
    var _description_label: RichTextLabel
    var _done_button: Button
    var _back_button: Button
    var _parent_wizard: Object = null

## 5. Public API — methods that MUST exist

    # ---- lifecycle ----
    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # ---- parent wiring ----
    func bind_parent_wizard(wizard: Object) -> void
    func open_stage() -> void
    
    # ---- list management ----
    func build_filtered_class_list() -> Array                                    # filters by race restrictions
    func render_class_rows(filtered_list: Array) -> void
    func clear_rows() -> void
    func class_allowed_for_race(class_id: String, race_id: String) -> bool
    func is_multi_class_row(class_entry: Dictionary) -> bool
    
    # ---- selection ----
    func select_class(class_id: String) -> void
    func get_selected_class() -> String
    func get_selected_components() -> Array
    func clear_selection() -> void
    func is_class_selected() -> bool
    
    # ---- description ----
    func update_description_for(class_id: String) -> void
    func build_description_text(class_entry: Dictionary) -> String
    func build_weapon_profs_text(class_entry: Dictionary) -> String
    func build_armor_restrictions_text(class_entry: Dictionary) -> String
    func build_starting_spells_text(class_entry: Dictionary) -> String
    
    # ---- confirm / back ----
    func on_done_pressed() -> void
    func on_back_pressed() -> void
    
    # ---- state machine hooks ----
    func set_fn() -> void
    func comment_fn(text_area: RichTextLabel) -> void
    func unset_fn() -> void
    func guard_fn() -> bool                                                      # always true
    
    # ---- signals ----
    signal class_selected(class_id: String)
    signal stage_advanced()
    signal stage_back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `open_stage()` with race=human, `build_filtered_class_list().size() >= 18` (all 8 single + all 10 multi).

**AC-02 [FR-06]:** With race=dwarf, filtered list contains no entry with id "paladin" or "mage" or "sorcerer".

**AC-03 [FR-05]:** With race=human, filtered list contains no multi-class entries.

**AC-04 [FR-04]:** Calling `select_class("fighter")` updates the description panel with a text containing "d10" (HP die).

**AC-05 [FR-07]:** Before any selection, Done button is disabled. After `select_class("thief")`, Done is enabled.

**AC-06 [FR-08]:** Pressing Done after selecting "fighter_mage" calls parent `update_state("class_id", "fighter_mage")`, `update_state("is_multi_class", true)`, `update_state("multi_class_components", ["fighter", "mage"])`, then `next()`.

**AC-07 [FR-09]:** `unset_fn()` clears `class_id`, `is_multi_class`, `multi_class_components` on CharGenState.

**AC-08 [FR-10]:** `comment_fn(text_area)` after selecting Cleric appends a line containing "Cleric".

**AC-09 [is_multi_class_row]:** `is_multi_class_row({"id": "fighter_thief", ...}) == true`, `is_multi_class_row({"id": "fighter", ...}) == false`.

**AC-10 [class_allowed_for_race]:** `class_allowed_for_race("mage", "dwarf") == false`, `class_allowed_for_race("fighter", "dwarf") == true`.

**AC-11 [reflection]:** Every method in §5 MUST exist on the script. Enumerated list:
`["_ready", "_input", "bind_parent_wizard", "open_stage", "build_filtered_class_list", "render_class_rows", "clear_rows", "class_allowed_for_race", "is_multi_class_row", "select_class", "get_selected_class", "get_selected_components", "clear_selection", "is_class_selected", "update_description_for", "build_description_text", "build_weapon_profs_text", "build_armor_restrictions_text", "build_starting_spells_text", "on_done_pressed", "on_back_pressed", "set_fn", "comment_fn", "unset_fn", "guard_fn"]`

## 7. Performance Requirements

- `build_filtered_class_list()`: **< 5ms**
- `render_class_rows()` for 18 rows: **< 15ms**
- `update_description_for()`: **< 10ms**

## 8. Error Handling

- Missing race in CharGenState: render unfiltered single-class list only, log at WARNING
- Unknown class_id in `select_class`: no-op, log at DEBUG
- Missing parent wizard: log at WARNING

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_step_class.gd` — NEW
- `godot-client/scenes/creation_step_class.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_creation_class.gd` — NEW

**Backend (consumed, NOT modified):** CharGenState only; backend sees class at finalize.

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_class.gd` MUST cover AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_class.gd

# PRD: Frontend Creation — Race (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **race selection stage** of the BG1 character creation wizard. The player chooses one of six BG1 races: Human, Elf, Half-Elf, Dwarf, Halfling, Gnome. Each row shows a flavor description, racial ability modifiers (e.g. `+1 CON / -1 CHA` for Dwarf), and class restrictions (e.g. "Cannot be Paladin or Sorcerer" for Dwarf). Selecting a race writes to `CharGenState.race` and feeds into the ability-score racial-modifier projection used by later stages.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\GUICG2.py` (141 LOC — race picker with buttons, `OnLoad`, race click handlers, `NextPress`)
- **GemRB parent state machine:** `gemrb/GUIScripts/bg1/CharGenCommon.py`
- **Godot target (NEW):** `godot-client/scripts/ui/creation_step_race.gd`
- **Companion scene (NEW):** `godot-client/scenes/creation_step_race.tscn`

**Clean-room rule:** Read GemRB to understand behavior. Do NOT copy code. Max 15 consecutive words quoted.

## 2. Scope

**In scope:**
- 6 radio-group race buttons (Human / Elf / Half-Elf / Dwarf / Halfling / Gnome)
- Description `RichTextLabel` that updates on selection with race flavor + mods + restrictions
- Done button enabled only after a race is chosen
- Back button routes to parent's `back()` (returns to gender stage)
- Writes chosen race to `CharGenState.race` via parent `update_state("race", value)`
- Stores per-race ability modifier offsets in `CharGenState.racial_mods` for the abilities stage to consume
- State-machine hooks (`set_fn`, `comment_fn`, `unset_fn`, `guard_fn`)
- Keyboard hotkeys: `H/E/Q/D/A/G` for each race, Enter = Done, Esc = Back

**Out of scope:**
- Subrace selection (BG2+ feature; BG1 has no subraces)
- Race-specific portraits (handled by portrait stage)
- Race-specific starting languages (backend handles during finalize)

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render exactly 6 race buttons in a radio group.

**FR-02:** On first render, no race MUST be selected. Description area MUST show `PROMPT_SELECT_RACE`. Done button MUST be disabled.

**FR-03:** Selecting a race MUST update the description area with that race's flavor + ability mods + class restrictions. Done button MUST become enabled.

**FR-04:** Pressing Done with a valid selection MUST call `update_state("race", race_id)` on the parent wizard AND call parent `next()`.

**FR-05:** Each race MUST contribute to `CharGenState.racial_mods` — a dictionary of `{ability: delta}` pairs applied later in the abilities stage.

**FR-06:** Each race MUST expose `_class_restrictions` — a list of class IDs this race cannot take. Used by the class stage to filter its options.

**FR-07:** The widget MUST have keyboard hotkeys per race (first letter of English name).

**FR-08:** `guard_fn()` MUST always return true (race is mandatory for all creation flows).

**FR-09:** `comment_fn(text_area)` MUST append a single line summarizing the choice to the parent overview, e.g. "Race: Half-Elf (+1 CHA)".

**FR-10:** `unset_fn()` MUST clear `CharGenState.race` and `CharGenState.racial_mods` when the player returns via back.

## 4. Data Structures

    class_name CreationStepRace extends PanelContainer
    
    const RACE_IDS := ["human", "elf", "half_elf", "dwarf", "halfling", "gnome"]
    
    const RACIAL_MODS := {
        "human":    {},
        "elf":      {"dex": 1, "con": -1},
        "half_elf": {},
        "dwarf":    {"con": 1, "cha": -1},
        "halfling": {"dex": 1, "str": -1},
        "gnome":    {"int": 1, "wis": -1},
    }
    
    const CLASS_RESTRICTIONS := {
        "human":    [],
        "elf":      ["paladin"],
        "half_elf": [],
        "dwarf":    ["paladin", "mage", "sorcerer"],
        "halfling": ["paladin", "mage", "sorcerer"],
        "gnome":    ["paladin", "sorcerer", "monk", "bard"],
    }
    
    const HOTKEYS := {KEY_H: "human", KEY_E: "elf", KEY_Q: "half_elf", KEY_D: "dwarf", KEY_A: "halfling", KEY_G: "gnome"}
    
    const PROMPT_SELECT_RACE := "Choose a race. Each race gives ability modifiers and opens or closes certain class paths."
    
    var _pending_race: String = ""
    var _parent_wizard: Object = null
    var _race_buttons: Dictionary = {}
    var _description_label: RichTextLabel
    var _done_button: Button
    var _back_button: Button

## 5. Public API — methods that MUST exist

    # ---- lifecycle ----
    func _ready() -> void
    func _input(event: InputEvent) -> void                                       # hotkeys + Enter/Esc
    
    # ---- parent wiring ----
    func bind_parent_wizard(wizard: Object) -> void
    func open_stage() -> void                                                    # reset buttons, apply PROMPT_SELECT_RACE
    
    # ---- selection ----
    func select_race(race_id: String) -> void
    func get_selected_race() -> String
    func clear_selection() -> void
    func is_race_selected() -> bool
    
    # ---- description ----
    func update_description_for(race_id: String) -> void
    func build_description_text(race_id: String) -> String                       # BBCode block
    func format_ability_mods(mods: Dictionary) -> String                         # "+1 CON, -1 CHA"
    func format_class_restrictions(restrictions: Array) -> String                # "Cannot be Paladin, Mage"
    
    # ---- confirm / back ----
    func on_done_pressed() -> void
    func on_back_pressed() -> void
    
    # ---- data helpers ----
    func get_racial_mods_for(race_id: String) -> Dictionary
    func get_class_restrictions_for(race_id: String) -> Array
    
    # ---- state machine hooks (parent wizard) ----
    func set_fn() -> void                                                        # stage entry
    func comment_fn(text_area: RichTextLabel) -> void                            # overview summary append
    func unset_fn() -> void                                                      # stage exit on back
    func guard_fn() -> bool                                                      # always true
    
    # ---- signals ----
    signal race_selected(race_id: String)
    signal stage_advanced()
    signal stage_back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The widget has exactly 6 race button children. `_race_buttons.size() == 6`.

**AC-02 [FR-02]:** After `open_stage()`, `get_selected_race() == ""`, description text matches `PROMPT_SELECT_RACE`, Done button is disabled.

**AC-03 [FR-03]:** Calling `select_race("dwarf")` updates the description to contain "CON" and "Paladin". Done button becomes enabled.

**AC-04 [FR-04]:** Pressing Done after `select_race("elf")` MUST call the parent wizard's `update_state("race", "elf")` and `next()` exactly once each (verified with a spy).

**AC-05 [FR-05]:** `get_racial_mods_for("dwarf") == {"con": 1, "cha": -1}`.

**AC-06 [FR-06]:** `get_class_restrictions_for("dwarf") == ["paladin", "mage", "sorcerer"]`.

**AC-07 [FR-07]:** Pressing the `D` key via `_input` on a focused widget MUST call `select_race("dwarf")`.

**AC-08 [FR-08]:** `guard_fn() == true` always.

**AC-09 [FR-09]:** Calling `comment_fn(text_area)` after selecting Half-Elf appends a line containing "Half-Elf" to the text area.

**AC-10 [FR-10]:** Calling `unset_fn()` sets `CharGenState.race` to empty and clears `CharGenState.racial_mods`.

**AC-11 [reflection]:** A headless test MUST enumerate every method in §5 and assert `script.has_method(name) == true`:
`["_ready", "_input", "bind_parent_wizard", "open_stage", "select_race", "get_selected_race", "clear_selection", "is_race_selected", "update_description_for", "build_description_text", "format_ability_mods", "format_class_restrictions", "on_done_pressed", "on_back_pressed", "get_racial_mods_for", "get_class_restrictions_for", "set_fn", "comment_fn", "unset_fn", "guard_fn"]`

## 7. Performance Requirements

- `open_stage()`: **< 20ms**
- `select_race()` + description update: **< 10ms**
- Hotkey response: **< 16ms**

## 8. Error Handling

- Unknown race_id in `select_race`: no-op, log at DEBUG
- Missing parent wizard: `on_done_pressed` becomes no-op, log at WARNING
- Invalid hotkey: ignored
- `CharGenState` missing fields: re-initialize locally, log at WARNING

## 9. Integration Points

**Godot (editable by this PRD):**
- `godot-client/scripts/ui/creation_step_race.gd` — NEW
- `godot-client/scenes/creation_step_race.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_creation_race.gd` — NEW

**Backend (consumed, NOT modified):**
- `CharGenState` is client-side; backend receives `race` only in the finalize payload
- No new endpoints

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_race.gd` MUST cover AC-01..AC-11
- ≥80% branch coverage on the script
- `run_headless_tests.gd` stays green

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_race.gd

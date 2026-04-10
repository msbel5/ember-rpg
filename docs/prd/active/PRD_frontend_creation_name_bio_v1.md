# PRD: Frontend Creation — Name + Biography (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **character name + biography input stage**. A single `LineEdit` for the character name (validated: non-empty, ≤32 chars, no forbidden chars) and a multi-line `TextEdit` for biography (up to 5000 chars). The biography is pre-filled with an auto-generated text based on earlier creation choices (race, class, alignment) that the player can accept or edit.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\GUICG9.py` (67 LOC — name input) + `bg1/GUICG10.py` (109 LOC — related) + `GUIRECCommon.py` biography functions `OpenBiographyWindow`, `OpenBiographyEditWindow`, `RevertBiography`, `ClearBiography`, `DoneBiographyWindow`, `GetProtagonistBiography` (lines 485-607)
- **Godot target:** NEW `godot-client/scripts/ui/creation_step_name_bio.gd` + NEW `godot-client/scenes/creation_step_name_bio.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Name `LineEdit` with validation
- Bio `TextEdit` with character counter
- Auto-fill biography from earlier choices via `GetProtagonistBiography` equivalent
- Revert button (restores auto-fill)
- Clear button (empties bio)
- Writes `CharGenState.player_name` + `CharGenState.biography`
- State machine hooks

**Out of scope:**
- Portrait in this stage (separate PRD)
- Voice in this stage
- Name generation (player types)

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render a name `LineEdit` + bio `TextEdit` + character counter + Revert + Clear + Done + Back.

**FR-02:** Name validation: non-empty, ≤32 chars, no characters outside `[a-zA-Z0-9\s\-']`. Done disabled if invalid.

**FR-03:** Bio max length MUST be 5000 chars. Character counter updates live.

**FR-04:** On stage entry, `generate_default_biography()` MUST populate the bio from race+class+alignment template.

**FR-05:** Revert button MUST restore the auto-generated biography.

**FR-06:** Clear button MUST empty the bio to "".

**FR-07:** Pressing Done writes both fields to parent state and calls `next()`.

**FR-08:** `unset_fn()` clears both fields on back.

**FR-09:** `comment_fn(text_area)` appends "Name: <name>" to overview.

**FR-10:** `guard_fn()` MUST always return true.

## 4. Data Structures

    class_name CreationStepNameBio extends PanelContainer
    
    const MAX_NAME_LENGTH := 32
    const MAX_BIO_LENGTH := 5000
    const NAME_REGEX := r"^[a-zA-Z0-9\s\-']+$"
    
    var _name_edit: LineEdit
    var _bio_edit: TextEdit
    var _counter_label: Label
    var _revert_button: Button
    var _clear_button: Button
    var _done_button: Button
    var _back_button: Button
    var _auto_generated_bio: String = ""
    var _parent_wizard: Object = null

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # parent wiring
    func bind_parent_wizard(wizard: Object) -> void
    func open_stage() -> void
    
    # name validation
    func validate_name(name: String) -> Dictionary                               # {valid: bool, reason: String}
    func on_name_text_changed(new_text: String) -> void
    func refresh_done_button_state() -> void
    
    # biography
    func generate_default_biography() -> String                                  # GemRB: GetProtagonistBiography
    func get_bio_template_for(race: String, class_id: String, alignment: String) -> String
    func on_bio_text_changed() -> void
    func update_character_counter() -> void
    func revert_biography() -> void                                              # GemRB: RevertBiography
    func clear_biography() -> void                                               # GemRB: ClearBiography
    func done_biography() -> void                                                # GemRB: DoneBiographyWindow
    func get_current_bio() -> String
    func set_bio_text(text: String) -> void
    func truncate_bio_if_too_long() -> void
    
    # confirm / back
    func on_done_pressed() -> void
    func on_back_pressed() -> void
    
    # state machine hooks
    func set_fn() -> void
    func comment_fn(text_area: RichTextLabel) -> void
    func unset_fn() -> void
    func guard_fn() -> bool                                                      # always true
    
    # signals
    signal name_changed(new_name: String)
    signal bio_changed(new_length: int)
    signal stage_advanced()
    signal stage_back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The widget has named nodes: `NameEdit`, `BioEdit`, `CounterLabel`, `RevertButton`, `ClearButton`, `DoneButton`, `BackButton`.

**AC-02 [FR-02]:** `validate_name("") == {"valid": false, ...}`. `validate_name("Abdel") == {"valid": true, ...}`. `validate_name("<script>") == {"valid": false, ...}`.

**AC-03 [FR-02]:** Name of 33 chars MUST fail validation with reason containing "length".

**AC-04 [FR-03]:** Typing 10 chars in bio sets counter text containing "10". Typing 5001 chars truncates to 5000.

**AC-05 [FR-04]:** After `generate_default_biography()`, `_auto_generated_bio` is non-empty and contains the race name.

**AC-06 [FR-05]:** Editing the bio then pressing Revert restores `_bio_edit.text == _auto_generated_bio`.

**AC-07 [FR-06]:** Clicking Clear sets `_bio_edit.text == ""`.

**AC-08 [FR-07]:** Pressing Done with valid name calls parent `update_state("player_name", "Abdel")` and `update_state("biography", bio_text)`, then `next()`.

**AC-09 [FR-08]:** `unset_fn()` clears both fields.

**AC-10 [FR-09]:** `comment_fn(text_area)` appends a line containing the character name.

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "bind_parent_wizard", "open_stage", "validate_name", "on_name_text_changed", "refresh_done_button_state", "generate_default_biography", "get_bio_template_for", "on_bio_text_changed", "update_character_counter", "revert_biography", "clear_biography", "done_biography", "get_current_bio", "set_bio_text", "truncate_bio_if_too_long", "on_done_pressed", "on_back_pressed", "set_fn", "comment_fn", "unset_fn", "guard_fn"]`

## 7. Performance Requirements

- `open_stage()` + generate default: **< 50ms**
- Name validation per keystroke: **< 5ms**
- Bio counter update: **< 2ms**

## 8. Error Handling

- Regex failure: treat as invalid, show specific reason
- Auto-bio template missing: use generic template, log at WARNING
- Name with only whitespace: treat as empty (invalid)
- Bio paste exceeding 5000: truncate with toast "Truncated to 5000 chars"

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_step_name_bio.gd` — NEW
- `godot-client/scenes/creation_step_name_bio.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_creation_name_bio.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_name_bio.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_name_bio.gd

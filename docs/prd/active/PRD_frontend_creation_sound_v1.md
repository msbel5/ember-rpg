# PRD: Frontend Creation — Sound Set (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **sound set selection stage**. A sound set is a voice pack with ~20 sample lines (select, move, attack, damage, die, etc.). The stage lists available sets filtered by `CharGenState.gender`. Each row has a Preview button that plays a sample. Selecting writes to `CharGenState.sound_set`.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\GUIRECCommon.py` functions `OpenSoundWindow`, `CloseSoundWindow`, `DoneSoundWindow`, `PlaySoundPressed`, `NextSound` (~60 LOC around lines 297-388)
- **Godot target:** NEW `godot-client/scripts/ui/creation_step_sound.gd` + NEW `godot-client/scenes/creation_step_sound.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Scrollable list of sound set rows filtered by gender
- Per-row Preview button that plays one sample
- "Cycle sample" button on the currently-selected row to hear different lines
- Selection writes `CharGenState.sound_set`
- State machine hooks

**Out of scope:**
- Custom sound set import (Phase 3)
- Per-line reassignment (not in BG1)
- Voice generation

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render a scrollable list of sound sets from `GameState.creation_catalog.sound_sets` (dependency on backend catalog).

**FR-02:** On open, the list MUST be filtered by `CharGenState.gender` if sound sets are gendered.

**FR-03:** Each row has: set name, description, Preview button, selection radio/check.

**FR-04:** Clicking Preview plays sample 0 via `AudioStreamPlayer`. Cycling via "Next Sample" button plays samples 1, 2, ..., N, then wraps.

**FR-05:** Selecting a row writes the sound set ID to an internal pending field.

**FR-06:** Pressing Done calls parent `update_state("sound_set", set_id)` and `next()`.

**FR-07:** `guard_fn()` MUST always return true.

**FR-08:** `unset_fn()` clears `CharGenState.sound_set` and stops any playing sample.

**FR-09:** `comment_fn(text_area)` appends "Sound: <Set Name>" to overview.

**FR-10:** When the stage exits (confirm or back), any playing sample MUST be stopped.

## 4. Data Structures

    class_name CreationStepSound extends PanelContainer
    
    var _sound_sets: Array = []                    # [{id, name, description, sample_slugs: Array, gendered: bool}]
    var _filtered_sets: Array = []
    var _pending_set_id: String = ""
    var _current_sample_index: int = 0
    var _parent_wizard: Object = null
    var _row_nodes: Dictionary = {}
    var _audio_player: AudioStreamPlayer
    var _done_button: Button
    var _back_button: Button

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # parent wiring
    func bind_parent_wizard(wizard: Object) -> void
    func open_stage() -> void
    func close_stage() -> void                                                   # stops audio
    
    # catalog loading
    func load_sound_sets_from_catalog() -> void
    func filter_by_gender(gender: int) -> Array
    
    # rendering
    func render_sound_set_rows(filtered: Array) -> void
    func refresh_row(set_id: String) -> void
    
    # selection
    func select_sound_set(set_id: String) -> void
    func get_selected_set() -> String
    func is_set_selected() -> bool
    
    # preview playback
    func play_sound_pressed(set_id: String) -> void                              # GemRB: PlaySoundPressed
    func next_sound() -> void                                                    # GemRB: NextSound — cycles samples
    func stop_playback() -> void
    func load_sample_stream(set_id: String, sample_index: int) -> AudioStream
    func get_sample_count_for(set_id: String) -> int
    
    # confirm / back
    func on_done_pressed() -> void
    func on_back_pressed() -> void
    
    # state machine hooks
    func set_fn() -> void
    func comment_fn(text_area: RichTextLabel) -> void
    func unset_fn() -> void
    func guard_fn() -> bool
    
    # signals
    signal sound_set_selected(set_id: String)
    signal sample_played(set_id: String, sample_index: int)
    signal stage_advanced()
    signal stage_back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `open_stage()` with 5 catalog sets, `_row_nodes.size() >= 5`.

**AC-02 [FR-02]:** With gender=1 (Male), `filter_by_gender(1)` returns only male-compatible sets.

**AC-03 [FR-04]:** Calling `play_sound_pressed("warrior")` sets `_current_sample_index = 0` and starts playback.

**AC-04 [FR-04]:** Calling `next_sound()` after `play_sound_pressed` increments `_current_sample_index` by 1 and plays the new sample. At the last sample, it wraps to 0.

**AC-05 [FR-05]:** `select_sound_set("warrior")` sets `_pending_set_id == "warrior"`.

**AC-06 [FR-06]:** Pressing Done with a selection calls parent `update_state("sound_set", "warrior")` and `next()`.

**AC-07 [FR-08]:** `unset_fn()` calls `stop_playback()` and clears `CharGenState.sound_set`.

**AC-08 [FR-09]:** `comment_fn(text_area)` appends a line containing the set name.

**AC-09 [FR-10]:** Calling `close_stage()` calls `stop_playback()`.

**AC-10 [guard_fn]:** `guard_fn()` returns true always.

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "bind_parent_wizard", "open_stage", "close_stage", "load_sound_sets_from_catalog", "filter_by_gender", "render_sound_set_rows", "refresh_row", "select_sound_set", "get_selected_set", "is_set_selected", "play_sound_pressed", "next_sound", "stop_playback", "load_sample_stream", "get_sample_count_for", "on_done_pressed", "on_back_pressed", "set_fn", "comment_fn", "unset_fn", "guard_fn"]`

## 7. Performance Requirements

- `open_stage()` + render: **< 30ms**
- Sample playback start latency: **< 100ms**
- Next sample cycle: **< 50ms**

## 8. Error Handling

- Missing catalog: render empty list + "No sound sets available" label
- Missing sample asset: log at WARNING, skip to next sample
- Audio player busy: stop current, start new
- Invalid gender: show all sets

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_step_sound.gd` — NEW
- `godot-client/scenes/creation_step_sound.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_creation_sound.gd` — NEW

**Backend (consumed, NOT modified):**
- `GameState.creation_catalog.sound_sets` — read-only

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_sound.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_sound.gd

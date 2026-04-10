# PRD: Frontend Death Screen (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **death screen** shown when all party members die. Fades to black, shows a "You have died." message with reason, plays death music, then shows Load / Quit buttons. Prevents any world input during the death sequence.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\GUIWORLD.py` — `DeathWindow()` and `DeathWindowEnd()` functions (~30 LOC at lines 121-167)
- **Godot target:** NEW `godot-client/scripts/ui/death_screen.gd` + NEW `godot-client/scenes/death_screen.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Fade to black transition
- Death message label (reason text)
- Death music playback (via AudioStreamPlayer)
- Load and Quit buttons
- Input blocking during the sequence
- Trigger from `GameState.party_wiped` signal

**Out of scope:**
- Death cutscene video
- Resurrection mechanics (backend authority)

## 3. Functional Requirements (FR)

**FR-01:** The death screen MUST trigger when `GameState.party_wiped` signal fires (add signal if missing).

**FR-02:** On trigger: fade to black over 2 seconds, stop world audio, play death music.

**FR-03:** After fade completes: show death message label with reason text, followed by Load and Quit buttons appearing 1 second later.

**FR-04:** Load button opens the load browser.

**FR-05:** Quit button opens quit confirm modal with mode `RETURN_TO_TITLE`.

**FR-06:** All world input MUST be blocked during the sequence.

**FR-07:** `set_death_reason(text)` allows customizing the reason text.

**FR-08:** The widget MUST auto-hide when a new game starts or a save is loaded (via `GameState.campaign_started` signal).

**FR-09:** Escape during the death screen routes to Quit (same as clicking Quit).

**FR-10:** The widget MUST persist across scenes (attached to the root viewport) OR be re-shown after scene changes during game session.

## 4. Data Structures

    class_name DeathScreen extends Control
    
    const FADE_DURATION_SEC := 2.0
    const BUTTONS_DELAY_SEC := 1.0
    const DEFAULT_DEATH_MESSAGE := "Your party has fallen."
    
    var _reason_text: String = DEFAULT_DEATH_MESSAGE
    var _is_active: bool = false
    var _fade_rect: ColorRect
    var _message_label: Label
    var _load_button: Button
    var _quit_button: Button
    var _death_music_player: AudioStreamPlayer

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # trigger / dismiss
    func trigger_death_sequence(reason: String = "") -> void
    func dismiss() -> void
    func is_active() -> bool
    
    # fade
    func start_fade_to_black() -> void
    func on_fade_complete() -> void
    func start_buttons_reveal() -> void
    
    # messages
    func set_death_reason(reason: String) -> void
    func get_death_reason() -> String
    
    # audio
    func play_death_music() -> void
    func stop_death_music() -> void
    func stop_world_audio() -> void
    
    # button handlers
    func on_load_pressed() -> void
    func on_quit_pressed() -> void
    
    # input blocking
    func block_world_input() -> void
    func unblock_world_input() -> void
    func is_input_blocked() -> bool
    
    # signals
    signal death_sequence_started()
    signal death_sequence_completed()
    signal load_requested_from_death()
    signal quit_requested_from_death()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `GameState.party_wiped.emit()`, `trigger_death_sequence` is called (connected handler). Verified via spy.

**AC-02 [FR-02]:** `start_fade_to_black()` creates a tween on `_fade_rect.modulate.a` from 0 to 1 over `FADE_DURATION_SEC`.

**AC-03 [FR-03]:** After fade completes, `_message_label.visible == true`. After `BUTTONS_DELAY_SEC`, `_load_button.visible == true` and `_quit_button.visible == true`.

**AC-04 [FR-04]:** Clicking Load emits `load_requested_from_death` and opens the load browser.

**AC-05 [FR-05]:** Clicking Quit emits `quit_requested_from_death` and opens the quit confirm modal in `RETURN_TO_TITLE` mode.

**AC-06 [FR-06]:** While `_is_active == true`, `is_input_blocked() == true`.

**AC-07 [FR-07]:** `set_death_reason("Khalid was slain by a goblin chief")` sets `_message_label.text` to that exact string.

**AC-08 [FR-08]:** Firing `GameState.campaign_started` MUST call `dismiss()`.

**AC-09 [FR-09]:** Pressing Esc via `_input` while active calls `on_quit_pressed()`.

**AC-10 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "trigger_death_sequence", "dismiss", "is_active", "start_fade_to_black", "on_fade_complete", "start_buttons_reveal", "set_death_reason", "get_death_reason", "play_death_music", "stop_death_music", "stop_world_audio", "on_load_pressed", "on_quit_pressed", "block_world_input", "unblock_world_input", "is_input_blocked"]`

## 7. Performance Requirements

- `trigger_death_sequence()` to fade start: **< 30ms**
- Total sequence to buttons visible: **< 4s** (fade 2s + delay 1s + buffer)
- Dismiss: **< 100ms**

## 8. Error Handling

- Death music asset missing: skip audio, log at WARNING
- `trigger_death_sequence` called while already active: no-op
- Load browser unavailable: fall back to direct scene change to title

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/death_screen.gd` — NEW
- `godot-client/scenes/death_screen.tscn` — NEW
- `godot-client/autoloads/game_state.gd` — add `party_wiped` signal if missing
- `godot-client/scenes/game_session.gd` — connect `party_wiped` signal to the death screen instance
- `godot-client/tests/automation/godot/test_frontend_death_screen.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_death_screen.gd` covers AC-01..AC-10
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_death_screen.gd

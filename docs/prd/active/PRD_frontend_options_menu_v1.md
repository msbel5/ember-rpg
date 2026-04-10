# PRD: Frontend Options Menu (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **multi-tab options menu** — graphics, audio, gameplay, controls, feedback. Opened from the title menu AND from the pause menu. Persists settings to a `user://options.cfg` file via Godot's `ConfigFile` API.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\GUIOPT.py` (551 LOC) + `GUIOPTControls.py` (188 LOC) + `GUIOPTExtra.py` (360 LOC)
- **Godot target:** NEW `godot-client/scripts/ui/options_panel.gd` + NEW `godot-client/scenes/options_panel.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Tab bar with 5 tabs: Graphics, Audio, Gameplay, Controls, Feedback
- Graphics: resolution dropdown, fullscreen toggle, vsync, gamma slider, frame cap slider
- Audio: master/music/voice/sfx volume sliders
- Gameplay: auto-pause toggles (per event), difficulty dropdown, combat speed slider
- Controls: key rebinding list (50+ actions)
- Feedback: character feedback level (0-5), combat log verbosity
- Save button writes to `user://options.cfg`
- Reset to Defaults button
- Apply Now button (preview changes)
- Close via Save or Cancel (Cancel discards changes)
- Esc closes with Cancel

**Out of scope:**
- Cloud sync of options
- Per-profile options (single profile)

## 3. Functional Requirements (FR)

**FR-01:** The panel MUST render 5 tab buttons. Clicking one switches the visible content.

**FR-02:** Each tab MUST load its current settings from `user://options.cfg` on open.

**FR-03:** Changes MUST be staged in a `_pending_options` dict until Save or Apply Now is pressed.

**FR-04:** Save MUST write `_pending_options` to the config file AND apply them to the running session.

**FR-05:** Apply Now MUST apply without closing the panel.

**FR-06:** Cancel (or Esc) MUST discard `_pending_options` and close the panel.

**FR-07:** Reset to Defaults MUST overwrite `_pending_options` with the default set (but does not save until Save is pressed).

**FR-08:** Volume sliders MUST update audio buses live as the slider moves (preview).

**FR-09:** Key rebinding row MUST display the current key + a "Rebind" button. Clicking Rebind captures the next key press and assigns it.

**FR-10:** Graphics changes (resolution/fullscreen) MUST apply immediately to the DisplayServer.

## 4. Data Structures

    class_name OptionsPanel extends PanelContainer
    
    const CONFIG_PATH := "user://options.cfg"
    
    const DEFAULT_OPTIONS := {
        "graphics/resolution": Vector2i(1920, 1080),
        "graphics/fullscreen": false,
        "graphics/vsync": true,
        "graphics/gamma": 1.0,
        "graphics/frame_cap": 60,
        "audio/master": 1.0,
        "audio/music": 0.8,
        "audio/voice": 1.0,
        "audio/sfx": 1.0,
        "gameplay/auto_pause_enemy_sighted": true,
        "gameplay/auto_pause_hp_low": true,
        "gameplay/auto_pause_spell_cast": false,
        "gameplay/difficulty": "normal",
        "gameplay/combat_speed": 1.0,
        "feedback/character_level": 3,
        "feedback/combat_log_verbosity": 2,
    }
    
    var _pending_options: Dictionary = {}
    var _current_tab: String = "graphics"
    var _tab_buttons: Dictionary = {}
    var _tab_panels: Dictionary = {}
    var _save_button: Button
    var _cancel_button: Button
    var _apply_button: Button
    var _reset_button: Button
    var _rebind_capturing: String = ""             # action name being rebound

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # open / close
    func open_panel() -> void
    func close_panel() -> void
    func is_open() -> bool
    
    # config file
    func load_options_from_file() -> Dictionary
    func save_options_to_file(options: Dictionary) -> void
    func get_default_options() -> Dictionary
    
    # tab management
    func set_active_tab(tab_id: String) -> void
    func get_active_tab() -> String
    func render_tab(tab_id: String) -> void
    
    # per-tab renderers
    func render_graphics_tab() -> void
    func render_audio_tab() -> void
    func render_gameplay_tab() -> void
    func render_controls_tab() -> void
    func render_feedback_tab() -> void
    
    # option management
    func get_option(key: String) -> Variant
    func set_option(key: String, value: Variant) -> void
    func reset_to_defaults() -> void
    func has_pending_changes() -> bool
    
    # apply
    func apply_now() -> void
    func save_and_close() -> void
    func cancel_and_close() -> void
    func apply_graphics_settings() -> void
    func apply_audio_settings() -> void
    func apply_gameplay_settings() -> void
    func apply_controls_settings() -> void
    func apply_feedback_settings() -> void
    
    # key rebinding
    func start_rebind_for(action: String) -> void
    func capture_rebind_key(event: InputEventKey) -> void
    func cancel_rebind() -> void
    func get_key_for_action(action: String) -> int
    func set_key_for_action(action: String, scancode: int) -> void
    
    # signals
    signal options_saved(options: Dictionary)
    signal options_canceled()
    signal rebind_started(action: String)
    signal rebind_completed(action: String, key: int)
    signal tab_changed(new_tab: String)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The panel has exactly 5 tab buttons.

**AC-02 [FR-02]:** On `open_panel()`, `_pending_options` is populated from file (or defaults if file missing).

**AC-03 [FR-04]:** Calling `save_and_close()` with pending changes writes them to `user://options.cfg` via `ConfigFile.save`.

**AC-04 [FR-05]:** `apply_now()` applies current `_pending_options` to running session via apply_* sub-methods.

**AC-05 [FR-06]:** `cancel_and_close()` clears `_pending_options` and closes the panel without saving.

**AC-06 [FR-07]:** `reset_to_defaults()` sets `_pending_options == DEFAULT_OPTIONS.duplicate(true)`.

**AC-07 [FR-08]:** Moving the master volume slider MUST call `set_option("audio/master", value)` and apply it live (preview).

**AC-08 [FR-09]:** Calling `start_rebind_for("move_north")` sets `_rebind_capturing == "move_north"`. The next `capture_rebind_key` call updates `_pending_options["controls/move_north"]`.

**AC-09 [FR-10]:** `apply_graphics_settings()` with `graphics/fullscreen == true` calls `DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)` in a test-safe stub.

**AC-10 [set_active_tab]:** Calling `set_active_tab("audio")` hides other tab panels and shows `_tab_panels["audio"]`.

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "open_panel", "close_panel", "is_open", "load_options_from_file", "save_options_to_file", "get_default_options", "set_active_tab", "get_active_tab", "render_tab", "render_graphics_tab", "render_audio_tab", "render_gameplay_tab", "render_controls_tab", "render_feedback_tab", "get_option", "set_option", "reset_to_defaults", "has_pending_changes", "apply_now", "save_and_close", "cancel_and_close", "apply_graphics_settings", "apply_audio_settings", "apply_gameplay_settings", "apply_controls_settings", "apply_feedback_settings", "start_rebind_for", "capture_rebind_key", "cancel_rebind", "get_key_for_action", "set_key_for_action"]`

## 7. Performance Requirements

- `open_panel()`: **< 100ms**
- Tab switch: **< 50ms**
- `save_and_close()`: **< 50ms**

## 8. Error Handling

- Config file missing: use defaults, log at DEBUG
- Config file corrupt: use defaults, log at WARNING
- Invalid resolution: fall back to 1280×720
- Key rebind to already-bound action: show toast "Key already bound"

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/options_panel.gd` — NEW
- `godot-client/scenes/options_panel.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_options_menu.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_options_menu.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_options_menu.gd

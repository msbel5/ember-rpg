# PRD: Frontend Dev Console (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify a **developer console overlay** (Tilde key toggles). Command input with history navigation (Up/Down arrows). Commands: backend command submit, GameState inspection, debug flag toggles, screenshot, scene reload. Dev build only — compiled out of release via `OS.is_debug_build()` gate.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\Console.py` + `gemrb/core/GUI/Console.h`/`Console.cpp`
- **Godot target:** NEW `godot-client/scripts/ui/dev_console.gd` + NEW `godot-client/scenes/dev_console.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Tilde (~/`) toggles overlay visibility
- LineEdit for command input with Enter = execute
- ScrollingRichTextLabel output area
- Command history (Up/Down navigation)
- Built-in commands: `cmd <text>`, `state <path>`, `debug <flag>`, `screenshot`, `reload`, `help`, `clear`, `quit`
- Dev build only (hidden in release)
- Auto-hide during dialog/combat

**Out of scope:**
- Remote console / telnet
- Command scripting beyond single-line
- Auto-complete

## 3. Functional Requirements (FR)

**FR-01:** The console MUST be hidden by default. Tilde toggles visibility.

**FR-02:** Tilde MUST be ignored in release builds (`not OS.is_debug_build()`).

**FR-03:** Enter in the input MUST parse and execute the command.

**FR-04:** Up/Down arrows MUST navigate command history.

**FR-05:** Output area MUST display command results, errors, and log lines. Auto-scroll to bottom.

**FR-06:** `cmd <text>` MUST submit the remainder as a backend campaign command via `Backend.submit_campaign_command`.

**FR-07:** `state <path>` MUST print the value at `GameState.<path>` (e.g. `state player.name`).

**FR-08:** `debug <flag>` MUST toggle a debug flag. Valid flags: `show_pathfinding`, `show_colliders`, `show_fps`, `log_backend_traffic`.

**FR-09:** `screenshot` MUST call `ScreenshotCapture.capture_viewport`.

**FR-10:** `reload` MUST reload the current scene.

**FR-11:** `help` MUST list available commands. `clear` MUST clear the output area. `quit` MUST exit the game via `get_tree().quit()`.

**FR-12:** The console MUST auto-hide when `GameState.has_active_dialog() == true` or `GameState.is_in_combat() == true`.

## 4. Data Structures

    class_name DevConsole extends Control
    
    const MAX_HISTORY_SIZE := 100
    const MAX_OUTPUT_LINES := 500
    
    const BUILTIN_COMMANDS := {
        "cmd":        "Submit backend campaign command",
        "state":      "Inspect GameState.<path>",
        "debug":      "Toggle debug flag",
        "screenshot": "Capture viewport screenshot",
        "reload":     "Reload current scene",
        "help":       "List commands",
        "clear":      "Clear output",
        "quit":       "Quit application",
    }
    
    const DEBUG_FLAGS := ["show_pathfinding", "show_colliders", "show_fps", "log_backend_traffic"]
    
    var _history: Array[String] = []
    var _history_index: int = -1
    var _output_lines: Array[String] = []
    var _debug_flags_state: Dictionary = {}
    var _input_edit: LineEdit
    var _output_text: RichTextLabel
    var _is_visible: bool = false

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # visibility
    func toggle_console() -> void
    func show_console() -> void
    func hide_console() -> void
    func is_console_visible() -> bool
    func can_show_console() -> bool                                              # debug build gate + state gates
    
    # command parsing
    func execute_command(input: String) -> void
    func parse_command(input: String) -> Dictionary                              # {cmd, args}
    func append_output(line: String) -> void
    func clear_output() -> void
    
    # builtin handlers
    func cmd_submit_backend(text: String) -> void
    func cmd_inspect_state(path: String) -> void
    func cmd_toggle_debug(flag: String) -> void
    func cmd_screenshot() -> void
    func cmd_reload_scene() -> void
    func cmd_help() -> void
    func cmd_clear() -> void
    func cmd_quit() -> void
    
    # history
    func push_to_history(input: String) -> void
    func history_previous() -> String
    func history_next() -> String
    func get_history_size() -> int
    
    # state inspection
    func resolve_game_state_path(path: String) -> Variant
    func format_value(value: Variant) -> String
    
    # debug flags
    func get_debug_flag(flag: String) -> bool
    func set_debug_flag(flag: String, value: bool) -> void
    func list_debug_flags() -> Array
    
    # state auto-hide
    func on_dialog_state_changed() -> void
    func on_combat_state_changed() -> void
    
    # signals
    signal command_executed(cmd: String, args: Array)
    signal console_shown()
    signal console_hidden()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `_ready()`, `_is_visible == false`.

**AC-02 [FR-02]:** Calling `can_show_console()` in a release build returns false. In debug build returns true (when no dialog/combat).

**AC-03 [FR-03]:** Calling `execute_command("help")` calls `cmd_help()` which appends help lines to `_output_lines`.

**AC-04 [FR-04]:** After pushing 3 commands to history, `history_previous()` returns the most recent, a second call returns the one before, etc.

**AC-05 [FR-06]:** Calling `execute_command("cmd move north")` calls `Backend.submit_campaign_command` with "move north".

**AC-06 [FR-07]:** Calling `cmd_inspect_state("player.name")` appends a line containing the player name.

**AC-07 [FR-08]:** Calling `cmd_toggle_debug("show_fps")` toggles `_debug_flags_state["show_fps"]`.

**AC-08 [FR-09]:** `cmd_screenshot()` calls `ScreenshotCapture.capture_viewport`.

**AC-09 [FR-12]:** With `GameState.has_active_dialog() == true`, calling `show_console()` MUST NOT set `_is_visible = true`. The method respects the gate.

**AC-10 [FR-11]:** `cmd_clear()` empties `_output_lines`.

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "toggle_console", "show_console", "hide_console", "is_console_visible", "can_show_console", "execute_command", "parse_command", "append_output", "clear_output", "cmd_submit_backend", "cmd_inspect_state", "cmd_toggle_debug", "cmd_screenshot", "cmd_reload_scene", "cmd_help", "cmd_clear", "cmd_quit", "push_to_history", "history_previous", "history_next", "get_history_size", "resolve_game_state_path", "format_value", "get_debug_flag", "set_debug_flag", "list_debug_flags", "on_dialog_state_changed", "on_combat_state_changed"]`

## 7. Performance Requirements

- `execute_command()`: **< 10ms** for most builtins
- Output append: **< 2ms** per line
- History navigation: **< 2ms**

## 8. Error Handling

- Unknown command: append "Unknown command: <cmd>" to output, don't crash
- Invalid state path: append "Path not found: <path>"
- Backend command failure: append the error message
- History empty: navigation returns ""

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/dev_console.gd` — NEW
- `godot-client/scenes/dev_console.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_dev_console.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)
- MUST be compiled out of release builds via `if not OS.is_debug_build(): queue_free()` pattern in `_ready()`

## 10. Test Coverage Target

- `test_frontend_dev_console.gd` covers AC-01..AC-11
- ≥80% branch coverage
- Tests run only under `OS.is_debug_build()` check

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_dev_console.gd

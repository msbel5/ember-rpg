# PRD: Frontend Quit Confirm Modal (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **quit confirmation modal** — a small Yes/No dialog shown when the player presses Quit from the title menu or from the pause menu. Prevents accidental quits. Two contexts:
- From **title screen**: "Yes" quits the application.
- From **pause menu** (in-game): "Yes" returns to the title screen (doesn't exit app).

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\QuitGame.py` (27 LOC)
- **Godot target:** NEW `godot-client/scripts/ui/quit_confirm_modal.gd` + NEW `godot-client/scenes/quit_confirm_modal.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Centered modal with "Are you sure you want to quit?" text, Yes and No buttons
- Two context modes: `MODE_EXIT_APP` and `MODE_RETURN_TO_TITLE`
- Enter = Yes, Esc = No hotkeys
- Shadow overlay behind the modal

**Out of scope:**
- Save-before-quit prompt (separate consideration; not in BG1)
- Auto-save on quit

## 3. Functional Requirements (FR)

**FR-01:** The modal MUST render centered with a text label, Yes button, No button, and a semi-transparent backdrop.

**FR-02:** The text MUST be configurable per context: "Quit the game?" (exit app) or "Return to main menu?" (return to title).

**FR-03:** Yes in `MODE_EXIT_APP` context MUST call `get_tree().quit()`.

**FR-04:** Yes in `MODE_RETURN_TO_TITLE` context MUST call `get_tree().change_scene_to_file("res://scenes/title_screen.tscn")`.

**FR-05:** No MUST close the modal without action.

**FR-06:** Enter key MUST trigger Yes; Esc MUST trigger No.

**FR-07:** The modal MUST be modal (blocks input to the surface behind).

**FR-08:** When the modal opens, Yes button MUST have initial focus.

## 4. Data Structures

    class_name QuitConfirmModal extends PanelContainer
    
    enum QuitMode { EXIT_APP, RETURN_TO_TITLE }
    
    var _mode: int = QuitMode.EXIT_APP
    var _text_label: Label
    var _yes_button: Button
    var _no_button: Button
    var _backdrop: ColorRect

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # open / close
    func open_for_mode(mode: int) -> void
    func close_modal() -> void
    func is_open() -> bool
    
    # text / mode
    func set_mode(mode: int) -> void
    func get_mode() -> int
    func build_text_for_mode(mode: int) -> String
    
    # actions
    func on_yes_pressed() -> void
    func on_no_pressed() -> void
    func execute_quit() -> void
    func execute_return_to_title() -> void
    
    # signals
    signal quit_confirmed(mode: int)
    signal quit_canceled()
    signal modal_closed()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `_ready()`, the modal has named nodes: `TextLabel`, `YesButton`, `NoButton`, `Backdrop`.

**AC-02 [FR-02]:** `build_text_for_mode(QuitMode.EXIT_APP)` returns a string containing "Quit". `build_text_for_mode(QuitMode.RETURN_TO_TITLE)` returns a string containing "main menu".

**AC-03 [FR-03]:** Calling `open_for_mode(QuitMode.EXIT_APP)` then `on_yes_pressed()` MUST call `execute_quit()` which (in test mode) emits `quit_confirmed(QuitMode.EXIT_APP)`. The test spy verifies this instead of actually quitting the process.

**AC-04 [FR-04]:** `open_for_mode(QuitMode.RETURN_TO_TITLE)` then `on_yes_pressed()` MUST call `execute_return_to_title()` and emit `quit_confirmed(QuitMode.RETURN_TO_TITLE)`.

**AC-05 [FR-05]:** `on_no_pressed()` MUST emit `quit_canceled` and call `close_modal`.

**AC-06 [FR-06]:** Pressing Enter via `_input` while the modal is open triggers Yes. Pressing Esc triggers No.

**AC-07 [FR-07]:** After `open_for_mode`, `_backdrop.visible == true` and `_backdrop.mouse_filter == Control.MOUSE_FILTER_STOP`.

**AC-08 [FR-08]:** After `open_for_mode`, the focused control is `_yes_button`.

**AC-09 [is_open]:** After `open_for_mode`, `is_open() == true`. After `close_modal`, `is_open() == false`.

**AC-10 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "open_for_mode", "close_modal", "is_open", "set_mode", "get_mode", "build_text_for_mode", "on_yes_pressed", "on_no_pressed", "execute_quit", "execute_return_to_title"]`

## 7. Performance Requirements

- `open_for_mode()`: **< 30ms**
- Enter/Esc response: **< 16ms**

## 8. Error Handling

- Invalid mode: fall back to EXIT_APP, log at WARNING
- Scene change failure in `execute_return_to_title`: log at ERROR, keep modal open
- Yes pressed while modal is closing: no-op

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/quit_confirm_modal.gd` — NEW
- `godot-client/scenes/quit_confirm_modal.tscn` — NEW
- `godot-client/scripts/ui/pause_menu.gd` — wire Quit button to `quit_confirm_modal.open_for_mode(QuitMode.RETURN_TO_TITLE)`
- `godot-client/scenes/title_screen.gd` — wire Quit button to `quit_confirm_modal.open_for_mode(QuitMode.EXIT_APP)`
- `godot-client/tests/automation/godot/test_frontend_quit_confirm.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_quit_confirm.gd` covers AC-01..AC-10
- ≥80% branch coverage
- Tests MUST use spy on `quit_confirmed` signal, NOT actually call `get_tree().quit()`

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_quit_confirm.gd

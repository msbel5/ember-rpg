# PRD: Frontend Clock Widget (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **in-game clock widget** — shows current game time (day, hour, minute) in a small HUD element. Updates via backend tick events. Clicking shows a detail popup; right-click pauses/resumes the world.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\Clock.py`
- **Godot target:** NEW `godot-client/scripts/ui/clock_widget.gd` + extend `godot-client/scripts/ui/status_bar_widget.gd`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Digital display format: "Day N, HH:MM" (24h)
- Optional analog clock face
- Click: opens a detail popup with date breakdown
- Right-click: pauses/resumes world (calls `Backend.set_runtime_mode` between "exploration_realtime" and "tactical_pause")
- Live refresh on `GameState.game_time_changed` (add signal if missing)
- Auto-syncs with backend `tick_state`

**Out of scope:**
- Calendar system with months/seasons (BG1 doesn't have one; just day/hour)
- Alarms / reminders
- Weather display (separate widget)

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render a small clock element with a text label (format `Day N, HH:MM`).

**FR-02:** The time MUST be read from `GameState.tick_state.game_time` (structure: `{day, hour, minute}`).

**FR-03:** The widget MUST update on `GameState.game_time_changed` signal.

**FR-04:** Left-click MUST open a detail popup showing full date breakdown: day, hour, minute, total game days, real-world elapsed.

**FR-05:** Right-click MUST toggle between `exploration_realtime` and `tactical_pause` via `Backend.set_runtime_mode`.

**FR-06:** A subtle visual change (color tint) MUST indicate whether the world is paused.

**FR-07:** `format_time(day, hour, minute)` MUST return `"Day N, HH:MM"` with zero-padded hour and minute.

**FR-08:** Hovering the clock MUST show a tooltip (via `TooltipHost`) with "Click for details, right-click to pause".

**FR-09:** `set_pause_state(paused: bool)` MUST update the visual state without changing runtime mode (for local preview).

**FR-10:** The widget MUST handle day-of-week/month rollover if the tick_state provides those fields.

## 4. Data Structures

    class_name ClockWidget extends Control
    
    var _current_day: int = 1
    var _current_hour: int = 8
    var _current_minute: int = 0
    var _is_paused: bool = false
    var _time_label: Label
    var _detail_popup: PanelContainer

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _gui_input(event: InputEvent) -> void
    
    # refresh
    func refresh_from_game_state() -> void
    func set_time(day: int, hour: int, minute: int) -> void
    func get_current_time() -> Dictionary                                        # {day, hour, minute}
    
    # formatting
    func format_time(day: int, hour: int, minute: int) -> String
    func format_detail_text() -> String                                          # multi-line date breakdown
    
    # click handlers
    func on_left_click() -> void
    func on_right_click() -> void
    
    # detail popup
    func open_detail_popup() -> void
    func close_detail_popup() -> void
    func is_detail_open() -> bool
    
    # pause
    func toggle_pause() -> void                                                  # calls backend
    func set_pause_state(paused: bool) -> void                                   # local visual only
    func is_paused() -> bool
    func apply_pause_visual() -> void                                            # tint update
    
    # tooltip
    func build_tooltip_text() -> String
    
    # signals
    signal time_changed(day: int, hour: int, minute: int)
    signal pause_toggled(is_paused: bool)
    signal detail_opened()
    signal detail_closed()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `_ready()`, `_time_label` has a non-empty text that matches `format_time(1, 8, 0)`.

**AC-02 [FR-02]:** After setting `GameState.tick_state.game_time = {day: 5, hour: 14, minute: 30}` and calling `refresh_from_game_state`, `_time_label.text == "Day 5, 14:30"`.

**AC-03 [FR-03]:** Firing `GameState.game_time_changed` causes the label to refresh.

**AC-04 [FR-04]:** Left-click via `_gui_input` opens `_detail_popup` (visible == true).

**AC-05 [FR-05]:** Right-click calls `toggle_pause` which calls `Backend.set_runtime_mode("tactical_pause")` when unpaused.

**AC-06 [FR-06]:** With `_is_paused == true`, `self.modulate` differs from the unpaused state.

**AC-07 [FR-07]:** `format_time(3, 9, 5) == "Day 3, 09:05"`.

**AC-08 [FR-08]:** Tooltip text from `build_tooltip_text()` contains "Click" and "pause".

**AC-09 [FR-09]:** `set_pause_state(true)` sets `_is_paused == true` and calls `apply_pause_visual()` but does NOT call `Backend.set_runtime_mode`.

**AC-10 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_gui_input", "refresh_from_game_state", "set_time", "get_current_time", "format_time", "format_detail_text", "on_left_click", "on_right_click", "open_detail_popup", "close_detail_popup", "is_detail_open", "toggle_pause", "set_pause_state", "is_paused", "apply_pause_visual", "build_tooltip_text"]`

## 7. Performance Requirements

- `refresh_from_game_state()`: **< 3ms**
- Click response: **< 16ms**
- Detail popup open: **< 30ms**

## 8. Error Handling

- Missing `tick_state`: show "Day ?, --:--", log at DEBUG
- Invalid time fields: clamp to safe values, log at WARNING
- `Backend.set_runtime_mode` failure: show toast, keep local visual consistent with backend state

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/clock_widget.gd` — NEW
- `godot-client/scripts/ui/status_bar_widget.gd` — embed the clock widget as a child
- `godot-client/autoloads/game_state.gd` — add `game_time_changed` signal if missing
- `godot-client/tests/automation/godot/test_frontend_clock_widget.gd` — NEW

**Backend (consumed, NOT modified):**
- `GameState.tick_state.game_time` — read-only
- `Backend.set_runtime_mode` — existing

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_clock_widget.gd` covers AC-01..AC-10
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_clock_widget.gd

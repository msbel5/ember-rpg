# PRD: Frontend Tooltip System (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify a **global tooltip host** — any UI element can register a tooltip via `TooltipHost.register(control, text_fn)`. Shows a styled panel with text at the mouse position after a 400ms hover delay. Auto-hides on leave. Supports BBCode rich text, icons, multi-line. Edge-of-screen clamping. Single tooltip visible at a time.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\core\GUI\Tooltip.h` + `Tooltip.cpp` (~200 LOC combined — read headers for class interface)
- **Godot target:** NEW autoload `godot-client/autoloads/tooltip_host.gd` (THIS PRD ALLOWS A NEW AUTOLOAD as a documented exception)
- **Tooltip visual:** NEW `godot-client/scenes/tooltip_host.tscn` as the container scene

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Autoload-based singleton registry for controls → tooltip text providers
- Hover detection via Control.mouse_entered / mouse_exited signals (auto-wired on register)
- Configurable delay (default 400ms)
- BBCode rich text rendering
- Edge clamping (never render off-screen)
- Single-visible invariant
- Register/unregister API

**Out of scope:**
- Nested tooltips
- Persistent/pinned tooltips
- Tooltip animations beyond simple fade

## 3. Functional Requirements (FR)

**FR-01:** `TooltipHost.register(control, text_provider)` MUST wire up `mouse_entered` / `mouse_exited` signals on `control` and store the provider.

**FR-02:** `TooltipHost.unregister(control)` MUST disconnect signals and remove the entry.

**FR-03:** On hover: start a `TOOLTIP_DELAY_SEC` (default 0.4s) timer. If still hovering after delay, invoke `text_provider()` to get the current text and show the tooltip panel.

**FR-04:** On leave: cancel any pending timer and hide the tooltip.

**FR-05:** Tooltip text supports BBCode. The panel uses a `RichTextLabel`.

**FR-06:** Tooltip position MUST follow the mouse with an offset of `(12, 20)` and MUST be clamped to the viewport bounds.

**FR-07:** Only one tooltip can be visible at a time. A new `show` cancels any existing tooltip.

**FR-08:** `set_delay(seconds)` MUST globally override the default hover delay.

**FR-09:** `text_provider` MUST be a `Callable` that takes no arguments and returns a String. This allows the text to be computed lazily at show time.

**FR-10:** Tooltip MUST support a maximum width (default 400px) with word wrap.

## 4. Data Structures

    class_name TooltipHost extends Node
    
    const DEFAULT_DELAY_SEC := 0.4
    const DEFAULT_MAX_WIDTH := 400
    const MOUSE_OFFSET := Vector2(12, 20)
    
    var _entries: Dictionary = {}                  # control_instance_id -> text_provider Callable
    var _current_delay_sec: float = DEFAULT_DELAY_SEC
    var _current_max_width: int = DEFAULT_MAX_WIDTH
    var _hover_timer: SceneTreeTimer = null
    var _active_control: Control = null
    var _tooltip_panel: PanelContainer
    var _tooltip_label: RichTextLabel

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _process(delta: float) -> void                                          # updates position while visible
    
    # registration
    func register(control: Control, text_provider: Callable) -> void
    func unregister(control: Control) -> void
    func is_registered(control: Control) -> bool
    func get_text_provider_for(control: Control) -> Callable
    
    # hover handling
    func on_mouse_entered_control(control: Control) -> void
    func on_mouse_exited_control(control: Control) -> void
    func start_hover_timer(control: Control) -> void
    func cancel_hover_timer() -> void
    func on_hover_timeout() -> void
    
    # show / hide
    func show_at(control: Control, text: String) -> void
    func hide_tooltip() -> void
    func is_visible_tooltip() -> bool
    
    # positioning
    func compute_tooltip_position(mouse_pos: Vector2, tooltip_size: Vector2) -> Vector2
    func clamp_to_viewport(position: Vector2, size: Vector2) -> Vector2
    func update_position_to_mouse() -> void
    
    # config
    func set_delay(seconds: float) -> void
    func get_delay() -> float
    func set_max_width(px: int) -> void
    func get_max_width() -> int
    
    # helpers
    func build_tooltip_panel() -> PanelContainer
    func apply_text(text: String) -> void
    
    # signals
    signal tooltip_shown(control: Control, text: String)
    signal tooltip_hidden()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** Calling `TooltipHost.register(button, func(): return "hello")` stores an entry and connects the two signals.

**AC-02 [FR-02]:** `TooltipHost.unregister(button)` removes the entry and disconnects signals.

**AC-03 [FR-03]:** After `on_mouse_entered_control(button)` and advancing `_hover_timer` by `_current_delay_sec`, `_tooltip_panel.visible == true` and `_tooltip_label.text == "hello"`.

**AC-04 [FR-04]:** Calling `on_mouse_exited_control(button)` before the timer elapses cancels the timer and no tooltip shows.

**AC-05 [FR-06]:** `compute_tooltip_position(Vector2(100, 100), Vector2(200, 50))` returns `Vector2(112, 120)` (mouse + offset).

**AC-06 [FR-06]:** `clamp_to_viewport(Vector2(1950, 100), Vector2(200, 50))` with viewport width 1920 returns an x value such that `position.x + size.x <= 1920`.

**AC-07 [FR-07]:** Showing a new tooltip while another is visible hides the old one first. Verified by checking `_active_control` changes.

**AC-08 [FR-08]:** `set_delay(0.8)` sets `_current_delay_sec == 0.8`.

**AC-09 [FR-09]:** The text provider is called EVERY time the tooltip is shown (not cached). Verified by a spy on a provider that increments a counter.

**AC-10 [reflection]:** Every method in §5 MUST exist on the TooltipHost singleton.

## 7. Performance Requirements

- `register()`: **< 1ms**
- `show_at()` render: **< 10ms**
- Position update per frame: **< 0.5ms**

## 8. Error Handling

- Control freed without unregister: entry MUST be dropped on next hover check (use weak references or `is_instance_valid`)
- Text provider returns empty string: do not show tooltip
- Text provider throws: catch, log at WARNING, do not show tooltip
- Multiple registrations of the same control: overwrite the previous provider

## 9. Integration Points

**Godot (editable):**
- `godot-client/autoloads/tooltip_host.gd` — NEW (explicit autoload EXCEPTION documented in this PRD)
- `godot-client/scenes/tooltip_host.tscn` — NEW
- `godot-client/project.godot` — register the new autoload
- `godot-client/tests/automation/godot/test_frontend_tooltip_system.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No GemRB code port (clean-room rule)

**Autoload exception:** This PRD is the ONLY frontend PRD authorized to add a new autoload. All other frontend PRDs must forbid new autoloads. The reason is that a tooltip host is inherently a cross-cutting UI concern that cannot be scoped to a single widget.

## 10. Test Coverage Target

- `test_frontend_tooltip_system.gd` covers AC-01..AC-10
- ≥85% branch coverage
- Test MUST NOT rely on actual mouse movement; uses direct signal emissions

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_tooltip_system.gd

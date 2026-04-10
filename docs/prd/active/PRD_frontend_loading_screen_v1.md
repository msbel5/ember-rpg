# PRD: Frontend Loading Screen (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **loading screen** shown during area transitions and save/load operations. Full-screen backdrop with area art, area name label, loading tip text (rotating), progress bar, "Loading..." indicator. Auto-dismisses when the loading completes.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\LoadScreen.py` (60 LOC)
- **Godot target:** NEW `godot-client/scenes/loading_screen.tscn` + `godot-client/scripts/ui/loading_screen.gd`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Full-screen backdrop image (per area or generic fallback)
- Area name label (top)
- Loading tip text (bottom, rotates every 4s through a tip pool)
- Progress bar (0-100%)
- "Loading..." animated ellipsis
- Fade in/out transitions
- Context dict accepted from scene change caller: `{area_id, area_name, loading_type}`

**Out of scope:**
- Loading-time minigames
- Audio streaming during load

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render a full-screen `Control` with a `TextureRect` backdrop, `Label` for area name, `Label` for tip text, `ProgressBar`, and an animated "Loading..." indicator.

**FR-02:** Setting `loading_context = {area_id, area_name, loading_type}` MUST update the backdrop, area name, and tip pool accordingly.

**FR-03:** Tip text MUST rotate every 4 seconds through `LOADING_TIPS`.

**FR-04:** `set_progress(0.0..1.0)` MUST update the progress bar.

**FR-05:** The "Loading..." label MUST animate by cycling "Loading", "Loading.", "Loading..", "Loading..." every 500ms.

**FR-06:** Fade in MUST take 200ms. Fade out MUST take 300ms.

**FR-07:** `dismiss()` MUST fade out and then hide/remove the widget.

**FR-08:** If the backdrop asset for `area_id` is missing, fall back to a generic backdrop (`res://assets/loading/generic.png`).

**FR-09:** The widget MUST block input while visible.

**FR-10:** `set_loading_type("save" | "load" | "area_transition")` MUST update the status label text ("Saving...", "Loading...", "Entering area...").

## 4. Data Structures

    class_name LoadingScreen extends Control
    
    const LOADING_TIPS := [
        "Press Space to pause time in the middle of combat.",
        "Right-click a spell icon to see its description.",
        "Rest to replenish spells and HP, but travel is dangerous at night.",
        "Thieves can Hide in Shadows even in combat if they succeed.",
        "Some enemies are immune to weapons below a certain magical enchantment.",
        "Check your journal (J) for quest updates.",
        "Formation shortcuts: F1-F5 in combat.",
        "Save often. Save early. Save in multiple slots.",
    ]
    
    const TIP_ROTATION_SEC := 4.0
    const ELLIPSIS_CYCLE_SEC := 0.5
    const FADE_IN_SEC := 0.2
    const FADE_OUT_SEC := 0.3
    
    var _loading_context: Dictionary = {}
    var _current_tip_index: int = 0
    var _ellipsis_frame: int = 0
    var _tip_timer: float = 0.0
    var _ellipsis_timer: float = 0.0
    var _backdrop: TextureRect
    var _area_name_label: Label
    var _tip_label: Label
    var _progress_bar: ProgressBar
    var _loading_label: Label

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _process(delta: float) -> void
    
    # show / hide
    func show_for_context(context: Dictionary) -> void
    func dismiss() -> void
    func is_visible_loading() -> bool
    
    # context
    func set_loading_context(context: Dictionary) -> void
    func get_loading_context() -> Dictionary
    func set_area_id(area_id: String) -> void
    func set_area_name(name: String) -> void
    func set_loading_type(type: String) -> void
    
    # backdrop
    func load_backdrop_for_area(area_id: String) -> Texture2D
    func apply_backdrop(texture: Texture2D) -> void
    
    # tips
    func start_tip_rotation() -> void
    func stop_tip_rotation() -> void
    func advance_tip() -> void
    func get_current_tip() -> String
    
    # progress
    func set_progress(fraction: float) -> void
    func get_progress() -> float
    
    # animated label
    func tick_ellipsis_animation(delta: float) -> void
    func build_loading_label_text() -> String                                    # "Loading" + N dots
    
    # fades
    func fade_in() -> void
    func fade_out() -> void
    
    # signals
    signal shown(context: Dictionary)
    signal dismissed()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `_ready()`, the widget has named child nodes: `Backdrop`, `AreaNameLabel`, `TipLabel`, `ProgressBar`, `LoadingLabel`.

**AC-02 [FR-02]:** Calling `show_for_context({"area_id": "ar1000", "area_name": "Candlekeep"})` sets `_area_name_label.text == "Candlekeep"`.

**AC-03 [FR-03]:** With `_tip_timer >= TIP_ROTATION_SEC`, `advance_tip()` increments `_current_tip_index` (wrapping at the end).

**AC-04 [FR-04]:** `set_progress(0.5)` sets `_progress_bar.value == 50.0` (if max=100) or equivalent.

**AC-05 [FR-05]:** `build_loading_label_text()` with `_ellipsis_frame == 2` returns "Loading..".

**AC-06 [FR-06]:** `fade_in()` creates a tween with duration 0.2s on `self.modulate.a` from 0 to 1.

**AC-07 [FR-07]:** `dismiss()` calls `fade_out()` and emits `dismissed` after fade completes.

**AC-08 [FR-08]:** `load_backdrop_for_area("missing")` returns the generic backdrop texture.

**AC-09 [FR-10]:** `set_loading_type("save")` updates the loading label text prefix to contain "Saving".

**AC-10 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_process", "show_for_context", "dismiss", "is_visible_loading", "set_loading_context", "get_loading_context", "set_area_id", "set_area_name", "set_loading_type", "load_backdrop_for_area", "apply_backdrop", "start_tip_rotation", "stop_tip_rotation", "advance_tip", "get_current_tip", "set_progress", "get_progress", "tick_ellipsis_animation", "build_loading_label_text", "fade_in", "fade_out"]`

## 7. Performance Requirements

- `show_for_context()` render: **< 50ms**
- Backdrop load (cached): **< 20ms**
- Progress update: **< 2ms**

## 8. Error Handling

- Missing backdrop asset: fall back to generic, log once
- Invalid progress value: clamp to [0, 1]
- Dismiss called before show: no-op

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/loading_screen.gd` — NEW
- `godot-client/scenes/loading_screen.tscn` — NEW
- `godot-client/scenes/game_session.gd` — integrate show/dismiss hooks on area transitions
- `godot-client/tests/automation/godot/test_frontend_loading_screen.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_loading_screen.gd` covers AC-01..AC-10
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_loading_screen.gd

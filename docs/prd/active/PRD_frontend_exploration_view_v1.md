# PRD: Frontend Exploration View — BG1 Main Game Window
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the main isometric game window where exploration, selection, movement, targeting, dialog, and combat interaction all happen. This is the single widget the player spends 90% of their time in. In BG1/GemRB this is `core/GUI/GameControl.cpp` — a 4000+ LOC C++ widget with explicit state machines for selection, targeting, viewport scrolling, formation rotation, and tooltip display. In ember-rpg today, `godot-client/scripts/world/world_view.gd` is its nearest equivalent but is much thinner and missing key interactions.

This PRD enumerates the **methods that must exist** on the Godot exploration view widget, based on GemRB's GameControl public interface, and maps each to the ember-rpg backend command protocol.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\core\GUI\GameControl.h` (public/private method declarations), `GameControl.cpp` (implementation — skim only, do NOT translate)
- **GemRB companion headers:** `core/GUI/GameControlDefs.h` (TargetMode enum, ScreenFlags enum, DialogueFlags constants)
- **GemRB viewport/sprite:** `core/Video/Video.h` abstract base; ember-rpg does not port this
- **Godot targets:**
  - Primary: `godot-client/scripts/world/world_view.gd` (currently ~442 LOC; extend)
  - Input routing: `godot-client/scripts/world/world_intent_router.gd`
  - Focus/selection: `godot-client/scripts/world/world_focus.gd`, `selection_overlay.gd`
  - Camera: `godot-client/scripts/world/camera_controller.gd`
  - Host scene: `godot-client/scenes/game_session.gd`

**Clean-room rule:** Read `GameControl.h` to extract the method catalog. Do NOT port `GameControl.cpp` logic — reimplement from behavior only. All GDScript below is newly written.

## 2. Scope

**In scope:**
- Viewport scrolling (keyboard arrows + edge-push + middle-drag)
- Zoom (default 100% = `zoom_level = 16`, stepped zoom in/out)
- Actor selection: single-click, click-and-drag selection rect, group select all, select by portrait
- Targeting mode state machine: None / Talk / Attack / Cast / Defend / Use / Pickup / Container
- Left-click routing based on target mode + what's under cursor (actor / door / container / ground)
- Right-click → context menu or attack (configurable)
- Cursor state: normal / talk / attack / cast / move / invalid / scroll
- Tooltip display with string + timed auto-hide
- Display text banner (timed HUD text for events like "you hear voices")
- Target reticle drawing on the selected actor's move destination
- Dialog state integration (freeze world when DF_IN_DIALOG)
- Cutscene mode integration
- Tab-to-highlight-all (outline interactive containers + doors + actors briefly)
- Formation rotation for party movement (hold-right-click and drag)

**Out of scope:**
- Actual pathfinding (covered by `PRD_architecture_pathfinding_v1.md`)
- Combat turn resolution (backend kernel)
- Dialog UI surface itself (covered by `PRD_frontend_message_window_v1.md` + `dialog_overlay.gd`)
- Area rendering and tile map (`world_view_planner.gd` + `tile_catalog.gd` — separate PRDs)
- Sprite animation state (covered by `PRD_architecture_actor_animation_v1.md`)

## 3. Functional Requirements (FR)

**FR-01:** The exploration view MUST expose a `TargetMode` enum matching GemRB: `NONE`, `TALK`, `ATTACK`, `CAST`, `DEFEND`, `PICK_UP`, `USE`, `CONTAINER`. Mode transitions MUST fire a signal `target_mode_changed(mode: int)`.

**FR-02:** Left-click on an empty tile while in `NONE` mode MUST issue a `move_to_point` command for the currently selected party member(s). Click on an actor while in `NONE` mode → context action depends on disposition (friendly=talk, hostile=attack). Click while in explicit mode (e.g. `CAST`) MUST issue the mode-specific command and then reset mode to `NONE`.

**FR-03:** Right-click anywhere MUST open a local context menu with the tile-appropriate actions. Holding right and dragging MUST rotate party formation (store the drag angle as `formation_base_angle` in radians).

**FR-04:** The widget MUST implement edge-scrolling: when the mouse pointer is within 20px of a viewport edge and the view is not locked, scroll the viewport at a speed proportional to distance from edge.

**FR-05:** Keyboard arrows (WASD or cursor keys, configurable) MUST scroll the viewport at a fixed rate. Holding Shift MUST double the scroll rate.

**FR-06:** Pressing `Tab` MUST highlight all interactive scene objects (doors, containers, actors) for 3 seconds with a visible outline.

**FR-07:** The widget MUST draw a target reticle at the destination tile of the selected party member's current move order. The reticle color MUST reflect state: green (friendly target), red (hostile target), yellow (invalid), white (plain move).

**FR-08:** The widget MUST expose a zoom-level control with discrete steps: 50% (`zoom_level=8`), 75% (`zoom_level=12`), 100% (`zoom_level=16`), 125% (`zoom_level=20`), 150% (`zoom_level=24`). Mouse wheel over the view cycles between steps.

**FR-09:** When `set_dialog_flags(DF_IN_DIALOG, OP_OR)` is called, the widget MUST freeze actor movement input, gray out the action bar, and route clicks through the dialog overlay instead.

**FR-10:** The widget MUST expose a `in_dialog(): bool` query used by other panels to decide whether to accept input.

**FR-11:** The widget MUST track `last_actor_id: int` (most recently interacted actor) and `tracker_id: int` (an NPC to auto-follow the camera), and expose getters/setters for both.

**FR-12:** Moving the mouse over an actor MUST show a tooltip with that actor's name + HP string + one-line status. Tooltip auto-hides after 3 seconds of no movement.

## 4. Data Structures

Extend `world_view.gd` with:

    class_name WorldViewWidget extends Control
    
    enum TargetMode { NONE, TALK, ATTACK, CAST, DEFEND, PICK_UP, USE, CONTAINER }
    
    const ZOOM_STEPS := [8, 12, 16, 20, 24]  # 50%..150%
    const DEFAULT_ZOOM := 16
    const EDGE_SCROLL_MARGIN := 20
    const HIGHLIGHT_DURATION := 3.0
    
    var _target_mode: int = TargetMode.NONE
    var _zoom_level: int = DEFAULT_ZOOM
    var _viewport_offset: Vector2 = Vector2.ZERO
    var _last_actor_id: String = ""
    var _tracker_id: String = ""
    var _highlighted_until: float = 0.0
    var _formation_base_angle: float = 0.0
    var _dialogue_flags: int = 0
    var _display_text: String = ""
    var _display_text_until: float = 0.0
    var _user_actor_id: String = ""  # who is casting / using
    var _selected_actor_ids: Array[String] = []
    var _over_me: Dictionary = {}  # what's under the cursor right now
    var _game_click_point: Vector2i = Vector2i.ZERO
    var _screen_mouse_pos: Vector2 = Vector2.ZERO

## 5. Public API — methods that MUST exist

The Godot implementation MUST provide the following methods. Copilot CLI / codex-cli MUST generate each of these with exact names and signatures; the acceptance test enumerates them via reflection.

    # ---- construction & lifecycle ----
    func _ready() -> void                                                       # wire signals, init default mode
    func _process(delta: float) -> void                                          # drive scroll, tooltip fade, display text timer, highlight timer
    func _unhandled_input(event: InputEvent) -> void                             # route mouse + keyboard
    
    # ---- target mode ----
    func set_target_mode(mode: int) -> void
    func get_target_mode() -> int
    func clear_target_mode() -> void                                             # resets to NONE, emits signal
    signal target_mode_changed(mode: int)
    
    # ---- screen/dialogue flags (mirror GemRB ScreenFlags / DialogueFlags) ----
    func set_screen_flags(flags: int, mode_op: int) -> void                      # mode_op: OP_SET/OP_OR/OP_NAND/OP_XOR
    func get_screen_flags() -> int
    func set_dialogue_flags(flags: int, mode_op: int) -> void
    func get_dialogue_flags() -> int
    func in_dialog() -> bool                                                     # returns (_dialogue_flags & DF_IN_DIALOG) != 0
    
    # ---- display text (timed HUD banner) ----
    func set_display_text(text: String, duration_ms: int) -> void
    func clear_display_text() -> void
    
    # ---- coordinate conversion ----
    func game_mouse_pos() -> Vector2i                                            # screen → tile position
    func convert_point_from_screen(screen_point: Vector2) -> Vector2i
    func convert_point_to_screen(tile_point: Vector2i) -> Vector2
    
    # ---- viewport / camera ----
    func move_viewport_to(point: Vector2i, center: bool, speed: int = 0) -> bool # returns true if move happened
    func move_viewport_unlocked_to(point: Vector2i, center: bool) -> void
    func viewport() -> Rect2                                                     # current visible region
    func scale_viewport(level: int) -> void                                      # zoom step
    func apply_key_scrolling(delta: float) -> void                               # called from _process
    func scroll(amount: Vector2) -> void
    
    # ---- selection ----
    func select_actor(actor_id: String, select_type: int = -1) -> void           # type: 0=add, 1=remove, -1=replace
    func select_all() -> void                                                    # selects all party
    func clear_selection() -> void
    func get_selected_actor_ids() -> Array[String]
    
    # ---- targeting actions (issued as backend commands) ----
    func try_to_attack(source_id: String, target_id: String) -> void             # emits command_requested("attack <target_id>")
    func try_to_cast(source_id: String, target_point: Vector2i, spell_ref: String) -> void
    func try_to_talk(source_id: String, target_id: String) -> void
    func try_to_defend(source_id: String) -> void
    func perform_selected_action(point: Vector2i) -> void                        # routes click based on current mode
    func command_selected_movement(point: Vector2i, formation: bool = true, append: bool = false, try_to_run: bool = false) -> void
    
    # ---- containers / doors ----
    func handle_container(container_id: String, actor_id: String) -> void
    func handle_door(door_id: String, actor_id: String) -> void
    
    # ---- cursor ----
    func update_cursor() -> void                                                 # sets cursor shape based on _over_me + _target_mode
    func is_disabled_cursor() -> bool
    
    # ---- highlighting (Tab key) ----
    func highlight_interactive_objects() -> void                                 # starts a 3-second highlight
    func outline_info_points() -> void
    func outline_doors() -> void
    func outline_containers() -> void
    func draw_tracking_arrows() -> void                                          # arrows pointing to off-screen selected actors
    
    # ---- tooltips ----
    func draw_tooltip(point: Vector2) -> void
    func tooltip_text() -> String
    func show_actor_tooltip(actor_id: String) -> void
    func hide_tooltip() -> void
    
    # ---- target reticle ----
    func draw_target_reticle(target_point: Vector2i, size: int, color: Color, offset: int = 0) -> void
    func draw_target_reticles() -> void                                          # draws all currently-queued reticles
    
    # ---- tracker & formation ----
    func set_tracker(actor_id: String, distance: int) -> void
    func get_tracker_id() -> String
    func get_formation_base_angle() -> float
    func set_formation_base_angle(angle: float) -> void
    
    # ---- cutscene mode ----
    func set_cutscene_mode(active: bool) -> void
    func is_in_cutscene() -> bool
    
    # ---- formation rendering ----
    func draw_formation(actor_ids: Array[String], formation_point: Vector2i, angle: float) -> void
    func get_formation_point(origin: Vector2i, pos: int, angle: float, exclude: Array = []) -> Vector2i
    func get_formation_points(origin: Vector2i, actor_ids: Array[String], angle: float) -> Array

Signals emitted:

    signal command_requested(command_text: String)                               # catch-all, routes to Backend.runtime_submit_command
    signal structured_action_requested(shortcut: String, args: Dictionary)
    signal focus_changed(focus_summary: String)
    signal focus_actions_changed(actions: Array)
    signal target_mode_changed(mode: int)
    signal viewport_moved(offset: Vector2)
    signal zoom_changed(zoom_level: int)
    signal cutscene_mode_changed(active: bool)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The `TargetMode` enum exists with exactly the 8 values listed. Verified by `script.new().TargetMode.keys().size() == 8`.

**AC-02 [FR-01, FR-02]:** Calling `set_target_mode(TargetMode.ATTACK)` then simulating a left-click on a hostile actor via automation bridge MUST emit `command_requested` with a string matching `^attack [\w_-]+$`, and then the mode MUST reset to `TargetMode.NONE`.

**AC-03 [FR-04, FR-05]:** Simulating a mouse at `(5, viewport.y/2)` (left edge) for 0.5s MUST cause `_viewport_offset.x` to decrease. Simulating Shift+Right arrow key MUST increase `_viewport_offset.x` at double speed compared to plain Right arrow.

**AC-04 [FR-06]:** Pressing Tab (via automation bridge `activate_node` on the root control) MUST set `_highlighted_until > Time.get_unix_time_from_system()`. Querying again 4 seconds later MUST show `_highlighted_until <=` now.

**AC-05 [FR-07]:** Calling `draw_target_reticle((10, 10), 8, Color.GREEN)` MUST render a reticle node or queue one for next frame. Verified by spying on a helper `_reticle_queue` array.

**AC-06 [FR-08]:** Calling `scale_viewport(20)` MUST set `_zoom_level == 20`. Simulating mouse wheel up on the viewport MUST advance `_zoom_level` through the step array.

**AC-07 [FR-09]:** Calling `set_dialogue_flags(DF_IN_DIALOG, OP_OR)` MUST make `in_dialog()` return true. Subsequent left-clicks MUST NOT emit `command_requested` (input is consumed by the dialog layer).

**AC-08 [FR-11]:** Calling `set_tracker("npc_42", 60)` then `get_tracker_id()` MUST return `"npc_42"`.

**AC-09 [FR-12]:** Moving the mouse over a tile with an actor (via automation bridge) MUST cause a tooltip to become visible within 200ms. The tooltip text MUST contain the actor name.

**AC-10 [public API existence]:** Every method listed in §5 MUST exist on the `world_view.gd` script. Verified by reflection: `for name in ["set_target_mode", "get_target_mode", ...] assert script.has_method(name)`. This is the bright-line test that the method-level spec has been followed.

## 7. Performance Requirements

- `_process()` per-frame cost under idle: **< 2ms** (excluding rendering)
- Edge scroll smoothness: 60 FPS maintained while scrolling
- Tooltip latency (mouse-over to visible): **< 200ms**
- Target reticle draw: 0 frame drops with up to 6 simultaneous reticles

## 8. Error Handling

- Invalid tile in `move_viewport_to`: clamp to area bounds, do not crash
- Selection targeting a non-existent actor_id: no-op, log at DEBUG level
- `set_target_mode` with out-of-range integer: clamp to `NONE`, log at WARNING
- Dialog mode override: if `in_dialog() == true`, most input is ignored — but ESC still exits dialog mode via existing dialog overlay hotkey
- Cursor update during scene transition: skip if scene is not `game_session`

## 9. Integration Points

**Godot (editable by this PRD):**
- `godot-client/scripts/world/world_view.gd` — extend with §5 methods
- `godot-client/scripts/world/world_intent_router.gd` — route `command_requested` signals
- `godot-client/scripts/world/selection_overlay.gd` — draw highlight / reticle
- `godot-client/scripts/world/world_focus.gd` — maintain focus summary
- `godot-client/scripts/world/camera_controller.gd` — viewport scrolling mechanics
- `godot-client/tests/automation/godot/test_frontend_exploration_view.gd` — NEW acceptance test exercising AC-01..AC-10

**Backend (consumed, NOT modified):**
- `/game/campaigns/{id}/command` — issues `move_to`, `attack`, `talk`, `cast`, `open_container`, `pick_up`, `use` shortcuts
- `GameState.entities` — source of truth for what's drawable
- `GameState.is_in_combat()`, `has_active_dialog()` — control input gating

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new autoloads
- No new backend endpoints
- No GemRB code port (clean-room rule)
- Do not break existing `world_view.gd` callers — all current methods must keep working

## 10. Test Coverage Target

- `test_frontend_exploration_view.gd` MUST cover AC-01..AC-10 in order
- `run_headless_tests.gd` MUST stay green
- Coverage goal: ≥80% of new methods exercised

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_exploration_view.gd

Both MUST be green.

## 12. Implementation notes (non-binding)

- GemRB's `GameControl` is 4000+ LOC. Most of it is rendering/cursor logic that Godot already handles via node tree + input events. Focus on the **state machine** and **command routing** — those are the load-bearing parts.
- The `TargetMode` transitions should be a single `func _set_target_mode_internal(mode: int)` helper to centralize signal emission and cursor update.
- `update_cursor()` should be idempotent and called from any state-changing public method.
- Reuse existing `instrument_rail.gd` focus summary wiring; don't duplicate.

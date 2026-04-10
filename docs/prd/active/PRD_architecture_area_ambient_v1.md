# PRD: Architecture — Area Ambient Animation Layer
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **area ambient layer** — background environmental animations (torches flickering, flags waving, water flowing, chimney smoke, crowds in distance) that loop independently of actors. This is the single biggest "alive world" multiplier after ambient_life and actor_animation. GemRB calls these `AreaAnimation` objects attached to `Map`. Ember renders them as sprites in a dedicated layer below actors.

### Reference sources
- **GemRB behavior:** `gemrb/core/AreaAnimation.{h,cpp}` (~200 LOC combined)
- **Godot target:** NEW `godot-client/scripts/world/area_ambient_layer.gd` + integration with `world_view.gd`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- `AreaAnimation` data structure with position, slug, frame_count, fps, z-order, tint, conditions
- Load ambient list on area entry
- Tick at 30 Hz (shared with actor animation)
- Time-of-day conditions (day only / night only)
- Weather conditions (optional hook)
- Pause/resume (during cutscenes or tactical pause)
- Does NOT participate in collision or pathfinding
- Z-order relative to tile grid

**Out of scope:**
- Interactive ambient (fountain with clickable water)
- Particle systems (separate PRD if needed)
- Audio loops tied to ambient (separate audio layer)

## 3. Functional Requirements (FR)

**FR-01:** `AreaAmbientLayer._ready()` MUST set up a Node2D layer below the entity layer.

**FR-02:** `load_ambient_list_for_area(area_id)` MUST fetch the ambient list from `GameState.area_state.ambient_animations` and instantiate sprite nodes.

**FR-03:** Each ambient entry has fields: `anim_id`, `position`, `slug`, `frame_count`, `fps`, `z_bias`, `tint` (Color), `conditions` (dict with optional `time_of_day`, `weather`).

**FR-04:** `tick_ambient(delta)` MUST advance frame cursors on all active ambients at their configured fps.

**FR-05:** `set_time_of_day(hour)` MUST enable/disable ambients whose `conditions.time_of_day` doesn't match the current hour.

**FR-06:** `pause_all()` MUST stop ticking without removing sprites. `resume_all()` restarts ticking.

**FR-07:** Sprites are rendered sorted by `position.y + z_bias` (Godot y-sort).

**FR-08:** On area exit, all ambients MUST be freed.

**FR-09:** The layer MUST handle 50+ simultaneous ambients without frame drops.

**FR-10:** Ambient textures MUST be loaded via `AssetBootstrap.resolve_asset(...)`.

## 4. Data Structures

    class_name AreaAmbientLayer extends Node2D
    
    const DEFAULT_FPS := 8.0
    
    var _active_ambients: Dictionary = {}          # anim_id -> {sprite, frame_cursor, timer, entry}
    var _area_id: String = ""
    var _paused: bool = false
    var _current_hour: int = 12
    var _current_weather: String = "clear"

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _process(delta: float) -> void
    
    # load / unload
    func load_ambient_list_for_area(area_id: String) -> void
    func unload_all() -> void
    func reload_current() -> void
    
    # entry management
    func instantiate_ambient(entry: Dictionary) -> Node2D
    func remove_ambient(anim_id: String) -> void
    func get_ambient(anim_id: String) -> Node2D
    func has_ambient(anim_id: String) -> bool
    
    # ticking
    func tick_ambient(delta: float) -> void
    func advance_frame(anim_id: String) -> void
    func update_sprite_frame(anim_id: String, frame_index: int) -> void
    
    # time / weather
    func set_time_of_day(hour: int) -> void
    func set_weather(weather: String) -> void
    func matches_conditions(entry: Dictionary) -> bool
    func refresh_visibility_for_all() -> void
    
    # pause / resume
    func pause_all() -> void
    func resume_all() -> void
    func is_paused() -> bool
    
    # rendering
    func compute_z_for(entry: Dictionary) -> int
    func apply_tint(sprite: Node2D, tint: Color) -> void
    func load_ambient_texture(slug: String, frame_count: int) -> Texture2D
    
    # debug
    func debug_list_active() -> Array                                            # returns list of anim_ids + positions
    func count_active() -> int
    
    # signals
    signal ambient_loaded(area_id: String, count: int)
    signal ambient_unloaded(area_id: String)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `_ready()`, the layer is a `Node2D` with `y_sort_enabled == true`.

**AC-02 [FR-02]:** Calling `load_ambient_list_for_area("ar1000")` with 3 ambients in GameState creates 3 child sprites in `_active_ambients`.

**AC-03 [FR-04]:** After calling `tick_ambient(0.2)` on an ambient with `fps == 8`, its frame cursor advances by at least 1 (since 0.2s ≥ 1/8s).

**AC-04 [FR-05]:** An ambient with `conditions.time_of_day = "night"` MUST NOT be visible after `set_time_of_day(12)` (noon).

**AC-05 [FR-05]:** Same ambient becomes visible after `set_time_of_day(22)` (10pm).

**AC-06 [FR-06]:** After `pause_all()`, `tick_ambient(1.0)` MUST NOT advance any frame cursors.

**AC-07 [FR-08]:** Calling `unload_all()` removes all sprites from the tree.

**AC-08 [FR-10]:** `load_ambient_texture("torch_flicker", 8)` returns a non-null texture (or placeholder).

**AC-09 [FR-07]:** Two ambients at positions (10, 10) and (10, 20) have different z-ordering values.

**AC-10 [count_active]:** With 5 ambients loaded, `count_active() == 5`.

**AC-11 [reflection]:** Every method in §5 MUST exist on the script:
`["_ready", "_process", "load_ambient_list_for_area", "unload_all", "reload_current", "instantiate_ambient", "remove_ambient", "get_ambient", "has_ambient", "tick_ambient", "advance_frame", "update_sprite_frame", "set_time_of_day", "set_weather", "matches_conditions", "refresh_visibility_for_all", "pause_all", "resume_all", "is_paused", "compute_z_for", "apply_tint", "load_ambient_texture", "debug_list_active", "count_active"]`

## 7. Performance Requirements

- `tick_ambient(delta)` with 50 ambients: **< 5ms**
- `load_ambient_list_for_area` with 30 ambients: **< 50ms**
- `unload_all` with 50 ambients: **< 30ms**

## 8. Error Handling

- Missing ambient texture: load placeholder, log once
- Invalid entry shape (missing required fields): skip, log at DEBUG
- `set_time_of_day` with out-of-range hour: clamp to [0, 23]
- `tick_ambient` on paused: no-op

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/world/area_ambient_layer.gd` — NEW
- `godot-client/scripts/world/world_view.gd` — host the ambient layer as a child below the entity layer
- `godot-client/autoloads/game_state.gd` — ensure `area_state.ambient_animations` is present (backend projection)
- `godot-client/tests/automation/godot/test_architecture_area_ambient.gd` — NEW

**Backend (consumed, NOT modified):**
- `GameState.area_state.ambient_animations` — from `region_projection.py` (existing module)
- `GameState.tick_state.game_time.hour` — for time-of-day filter

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new HTTP endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_architecture_area_ambient.gd` covers AC-01..AC-11
- ≥85% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_architecture_area_ambient.gd

# PRD: Architecture — Effect Visualization
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify **client-side visualization of active actor effects** — buffs, debuffs, status conditions, damage/heal numbers. Strictly client-rendering only; backend owns effect resolution. Reads `actor.active_effects` from state snapshots and produces: overlays (color tints, icons above head), floating damage/heal numbers, critical hit feedback, status icon strip.

### Reference sources
- **GemRB behavior:** `gemrb/core/Effect.{h,cpp}` + `EffectQueue.{h,cpp}` (~500 LOC combined — read top 200 for opcode structure, duration rules)
- **Ember target:** `frp-backend/engine/kernel/effects/` (existing — READ-ONLY) + NEW `godot-client/scripts/ui/effect_visualizer.gd` + EXTEND `godot-client/scripts/world/entity_visuals.gd`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Per-actor status icon strip above their sprite
- Per-actor color overlay (e.g. green for poison, blue for charm, gray for petrified)
- Floating damage numbers spawned on hit events
- Floating heal numbers (green) on heal events
- Miss / critical text feedback
- Sync effects from `actor.active_effects` on every state update
- Effect icon catalog (8+ canonical conditions)

**Out of scope:**
- Effect resolution rules (backend kernel authority)
- Spell particle effects (separate visual effects PRD)
- Sound associated with effects (audio layer)

## 3. Functional Requirements (FR)

**FR-01:** The effect visualizer MUST maintain a map `actor_id -> {icons_node, overlay_node, active_effect_ids}`.

**FR-02:** `sync_effects_for_actor(actor_id, effect_list)` MUST diff the new list against the stored list and create/remove icons accordingly.

**FR-03:** Each icon MUST be rendered above the actor's sprite position with a fixed offset.

**FR-04:** Color overlay MUST be applied via the sprite's `modulate` property based on the dominant effect category (poison > charm > sleep > petrified > default).

**FR-05:** `spawn_damage_number(actor_id, amount, color)` MUST create a floating Label that drifts upward over 1 second and fades out.

**FR-06:** `spawn_heal_number(actor_id, amount)` MUST do the same with green color.

**FR-07:** `spawn_miss_text(actor_id)` MUST spawn a "MISS" label with gray color.

**FR-08:** `show_critical_hit_effect(actor_id)` MUST spawn a "CRITICAL" label with red color and a brief screen shake (optional).

**FR-09:** Effect icons MUST be loaded from `EFFECT_ICON_CATALOG` dict (slug → texture).

**FR-10:** The visualizer MUST clean up stale overlays when an actor is removed from the world.

**FR-11:** On `GameState.actor_effect_event` signal (add if missing) with `{actor_id, event_type, data}`, dispatch to the right spawner (hit/heal/miss/crit).

**FR-12:** Duration-bar display (optional nice-to-have) MAY appear below the status icon strip.

## 4. Data Structures

    class_name EffectVisualizer extends Node2D
    
    const EFFECT_ICON_CATALOG := {
        "poisoned":  "res://assets/effects/status_poisoned.png",
        "charmed":   "res://assets/effects/status_charmed.png",
        "paralyzed": "res://assets/effects/status_paralyzed.png",
        "sleeping":  "res://assets/effects/status_sleeping.png",
        "stunned":   "res://assets/effects/status_stunned.png",
        "silenced":  "res://assets/effects/status_silenced.png",
        "feared":    "res://assets/effects/status_feared.png",
        "hasted":    "res://assets/effects/status_hasted.png",
        "slowed":    "res://assets/effects/status_slowed.png",
        "blessed":   "res://assets/effects/status_blessed.png",
        "berserk":   "res://assets/effects/status_berserk.png",
        "petrified": "res://assets/effects/status_petrified.png",
    }
    
    const CATEGORY_OVERLAY_COLOR := {
        "poisoned":  Color(0.55, 1.0, 0.55),
        "charmed":   Color(0.80, 0.70, 1.0),
        "sleeping":  Color(0.60, 0.60, 0.60),
        "petrified": Color(0.45, 0.45, 0.45),
        "feared":    Color(1.0, 0.80, 0.50),
    }
    
    const CATEGORY_PRIORITY := ["petrified", "sleeping", "charmed", "feared", "poisoned", "hasted", "blessed"]
    
    const FLOAT_NUMBER_DURATION_SEC := 1.0
    const FLOAT_NUMBER_DISTANCE_PX := 48.0
    
    var _actor_viz: Dictionary = {}                # actor_id -> {icons_node, overlay_node, effect_ids: Array}
    var _float_labels_root: Node2D

## 5. Public API — methods that MUST exist

    func _ready() -> void
    
    # per-actor sync
    func sync_effects_for_actor(actor_id: String, effect_list: Array) -> void
    func add_visual_effect(actor_id: String, effect_data: Dictionary) -> void
    func remove_visual_effect(actor_id: String, effect_id: String) -> void
    func clear_all_for_actor(actor_id: String) -> void
    
    # rendering — icons
    func render_icon_strip(actor_id: String, effect_ids: Array) -> void
    func get_icon_texture_for(effect_slug: String) -> Texture2D
    func position_icon_strip(actor_id: String, sprite_position: Vector2) -> void
    
    # rendering — overlay tint
    func apply_overlay_color(actor_id: String, effect_ids: Array) -> void
    func get_dominant_overlay_color(effect_ids: Array) -> Color
    func get_dominant_category(effect_ids: Array) -> String
    func clear_overlay_color(actor_id: String) -> void
    
    # floating numbers
    func spawn_damage_number(actor_id: String, amount: int, color: Color = Color.RED) -> void
    func spawn_heal_number(actor_id: String, amount: int) -> void
    func spawn_miss_text(actor_id: String) -> void
    func spawn_custom_float_text(actor_id: String, text: String, color: Color) -> void
    func show_critical_hit_effect(actor_id: String) -> void
    
    # event dispatch
    func on_actor_effect_event(payload: Dictionary) -> void
    func get_actor_screen_position(actor_id: String) -> Vector2
    
    # cleanup
    func on_actor_removed(actor_id: String) -> void
    func clear_all() -> void
    
    # debug
    func debug_count_visible_effects() -> int
    func debug_list_active_actors() -> Array

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `add_visual_effect("pc_0", {...})`, `_actor_viz.has("pc_0") == true`.

**AC-02 [FR-02]:** Calling `sync_effects_for_actor("pc_0", [{"id": "e1", "slug": "poisoned"}])` then sync with `[]` removes all icons for pc_0.

**AC-03 [FR-03]:** After rendering an icon strip, the node position matches the actor sprite's position + fixed offset.

**AC-04 [FR-04]:** With effects `["poisoned"]`, `get_dominant_overlay_color(...)` returns the poisoned color `Color(0.55, 1.0, 0.55)`.

**AC-05 [FR-04]:** With effects `["poisoned", "petrified"]`, dominant returns petrified (higher priority).

**AC-06 [FR-05]:** `spawn_damage_number("pc_0", 12, Color.RED)` creates a Label child with text "12" that begins a tween animation.

**AC-07 [FR-06]:** `spawn_heal_number("pc_0", 8)` creates a green "+8" label.

**AC-08 [FR-07]:** `spawn_miss_text("pc_0")` creates a label with text "MISS".

**AC-09 [FR-10]:** `on_actor_removed("pc_0")` clears the actor from `_actor_viz`.

**AC-10 [FR-11]:** `on_actor_effect_event({"actor_id": "pc_0", "event_type": "damage", "amount": 5})` calls `spawn_damage_number`.

**AC-11 [reflection]:** Every method in §5 MUST exist on the script:
`["_ready", "sync_effects_for_actor", "add_visual_effect", "remove_visual_effect", "clear_all_for_actor", "render_icon_strip", "get_icon_texture_for", "position_icon_strip", "apply_overlay_color", "get_dominant_overlay_color", "get_dominant_category", "clear_overlay_color", "spawn_damage_number", "spawn_heal_number", "spawn_miss_text", "spawn_custom_float_text", "show_critical_hit_effect", "on_actor_effect_event", "get_actor_screen_position", "on_actor_removed", "clear_all", "debug_count_visible_effects", "debug_list_active_actors"]`

## 7. Performance Requirements

- `sync_effects_for_actor` with 10 effects: **< 3ms**
- `spawn_damage_number`: **< 2ms**
- 20 floating numbers visible simultaneously: 0 frame drops at 60 FPS

## 8. Error Handling

- Missing icon asset: use placeholder, log once per slug
- Unknown category in effect list: treat as generic, no overlay
- Spawn for non-existent actor_id: no-op, log at DEBUG
- Event with missing fields: log at WARNING, no-op

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/effect_visualizer.gd` — NEW
- `godot-client/scripts/world/entity_visuals.gd` — existing; may provide `body_modulate` extension hook
- `godot-client/scripts/world/entity_layer.gd` — existing; invokes `sync_effects_for_actor` after each entity update
- `godot-client/autoloads/game_state.gd` — add `actor_effect_event` signal if missing
- `godot-client/tests/automation/godot/test_architecture_effect_visualization.gd` — NEW

**Backend (consumed, NOT modified):**
- `actor.active_effects` in `/state` response — read-only
- `actor_effect_event` WS message (backend must emit for hit/heal/miss/crit if it doesn't already)

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**` (effect kernel is authoritative)
- No edits to any other PRD file
- No new HTTP endpoints
- No new autoloads
- No GemRB code port (clean-room rule)
- No client-side effect resolution

## 10. Test Coverage Target

- `test_architecture_effect_visualization.gd` covers AC-01..AC-11
- ≥85% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_architecture_effect_visualization.gd

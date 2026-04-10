# PRD: Architecture — Multi-Layer Sprite Composition
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **multi-layer sprite composition** system. A character is rendered as base body + head + torso armor + helmet + cloak + weapon main + weapon off + shield + ammo overlay. Each layer dyed with major/minor colors from stats. Produces a single composed texture per (actor, state, facing, frame) that `entity_layer.gd` draws.

### Reference sources
- **GemRB behavior:** `gemrb/core/CharAnimations.{h,cpp}` (palette cycling, layered body sprites, equipment overlays) + `gemrb/plugins/PLTImporter/` (PLT format) + `gemrb/GUIScripts/PaperDoll.py` (composition)
- **Godot target:** EXTEND `godot-client/scripts/world/entity_sprite_catalog.gd` + NEW `godot-client/scripts/world/sprite_layer_compositor.gd`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Layer definitions: body, head, torso_armor, helmet, cloak, weapon_main, weapon_off, shield, ammo, effect_top
- Per-layer asset registration
- Color tinting via shader (major/minor color stats)
- Layer z-order
- Composition cache keyed by (template, state, facing, frame, equipment_hash)
- Fallback to generic sprite when specific layer asset missing

**Out of scope:**
- Animation state transitions (covered by actor_animation PRD)
- Per-item PLT file import (use pre-converted PNG atlases)
- Dynamic lighting on sprites

## 3. Functional Requirements (FR)

**FR-01:** Define `LAYER_ORDER := ["body", "cloak", "torso_armor", "head", "helmet", "weapon_off", "shield", "weapon_main", "ammo", "effect_top"]`. Layers render in this order (later ones on top).

**FR-02:** `compose_actor_sprite(actor_data, state, facing, frame) -> Texture2D` MUST return a single composed texture by stacking all applicable layers.

**FR-03:** `register_layer_asset(layer_type, slug, texture)` MUST store a layer asset keyed by (layer_type, slug).

**FR-04:** `get_equipment_layer_for(slot, item_id)` MUST map a (slot, item_id) pair to a layer slug.

**FR-05:** `apply_palette_tint(texture, major, minor)` MUST apply major/minor color via a shader material and return the tinted texture.

**FR-06:** The composition MUST be cached per `_composition_cache_key(actor_id, state, facing, frame, equipment_hash)`. Repeated calls with the same key MUST return the cached texture.

**FR-07:** `invalidate_cache_for(actor_id)` MUST clear all cached compositions for that actor (e.g. after equipment change).

**FR-08:** Missing layer assets MUST fall back: specific template → generic template → `placeholder.png`. Log once per unique miss.

**FR-09:** `compute_equipment_hash(equipped_slots)` MUST return a stable hash of the equipped items, used as part of the cache key.

**FR-10:** The module MUST expose a debug method `dump_layer_stack(actor_data, state, facing, frame) -> Array[Dictionary]` returning an ordered list of what layers would be composed (for inspector / test).

## 4. Data Structures

    # godot-client/scripts/world/sprite_layer_compositor.gd
    class_name SpriteLayerCompositor extends RefCounted
    
    const LAYER_ORDER := [
        "body",
        "cloak",
        "torso_armor",
        "head",
        "helmet",
        "weapon_off",
        "shield",
        "weapon_main",
        "ammo",
        "effect_top",
    ]
    
    const TINT_SHADER_PATH := "res://assets/shaders/palette_tint.gdshader"
    const FALLBACK_PLACEHOLDER := "res://assets/generated/fallback_placeholder.png"
    
    static var _layer_assets: Dictionary = {}      # {(layer_type, slug): Texture2D}
    static var _composition_cache: Dictionary = {} # {cache_key: Texture2D}
    static var _tint_shader: Shader = null

## 5. Public API — methods that MUST exist

All static methods on `SpriteLayerCompositor`:

    static func compose_actor_sprite(actor_data: Dictionary, state: int, facing: int, frame: int) -> Texture2D
    static func compose_actor_sprite_uncached(actor_data: Dictionary, state: int, facing: int, frame: int) -> Texture2D
    
    # layer registration
    static func register_layer_asset(layer_type: String, slug: String, texture: Texture2D) -> void
    static func get_layer_asset(layer_type: String, slug: String) -> Texture2D
    static func has_layer_asset(layer_type: String, slug: String) -> bool
    static func preload_layer_assets_from_manifest() -> void
    
    # equipment mapping
    static func get_equipment_layer_for(slot: String, item_id: String) -> String
    static func compute_equipment_hash(equipped_slots: Dictionary) -> String
    
    # composition helpers
    static func build_layer_stack(actor_data: Dictionary, state: int, facing: int, frame: int) -> Array
    static func dump_layer_stack(actor_data: Dictionary, state: int, facing: int, frame: int) -> Array
    static func composite_layers(layers: Array) -> Texture2D
    static func load_layer_texture(layer_type: String, slug: String, state: int, facing: int, frame: int) -> Texture2D
    
    # tinting
    static func apply_palette_tint(texture: Texture2D, major: Color, minor: Color) -> Texture2D
    static func get_actor_colors(actor_data: Dictionary) -> Dictionary
    
    # cache
    static func composition_cache_key(actor_id: String, state: int, facing: int, frame: int, equipment_hash: String) -> String
    static func get_cached(cache_key: String) -> Texture2D
    static func store_cached(cache_key: String, texture: Texture2D) -> void
    static func invalidate_cache_for(actor_id: String) -> int                   # returns count cleared
    static func clear_full_cache() -> void
    
    # fallback
    static func resolve_fallback_layer(layer_type: String, requested_slug: String) -> Texture2D
    static func get_placeholder() -> Texture2D

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** `LAYER_ORDER` MUST equal the exact 10-element array listed. Verified by literal equality.

**AC-02 [FR-02]:** `compose_actor_sprite({...}, 1, 4, 0)` returns a non-null `Texture2D`.

**AC-03 [FR-03]:** After `register_layer_asset("body", "human_male", tex)`, `get_layer_asset("body", "human_male") == tex`.

**AC-04 [FR-04]:** `get_equipment_layer_for("weapon_main", "long_sword") == "long_sword_icon"` (or similar stable slug).

**AC-05 [FR-05]:** `apply_palette_tint(tex, Color.RED, Color.BLUE)` returns a texture whose shader material has both color uniforms set.

**AC-06 [FR-06]:** Calling `compose_actor_sprite` twice with identical args hits the cache on the second call. Verified by spying on `compose_actor_sprite_uncached`.

**AC-07 [FR-07]:** After `invalidate_cache_for("pc_0")`, any cached composition for that actor_id is removed. Verified by `get_cached(key) == null`.

**AC-08 [FR-08]:** Calling `resolve_fallback_layer("body", "missing_slug")` returns the placeholder if no fallback exists. Never returns null.

**AC-09 [FR-09]:** `compute_equipment_hash({"weapon_main": "long_sword", "armor": "chain"})` returns a stable non-empty string. Same input → same hash.

**AC-10 [FR-10]:** `dump_layer_stack({...}, 1, 4, 0)` returns a non-empty Array with entries ordered by `LAYER_ORDER`.

**AC-11 [reflection]:** A test MUST verify every static method in §5 exists on `SpriteLayerCompositor`:
`["compose_actor_sprite", "compose_actor_sprite_uncached", "register_layer_asset", "get_layer_asset", "has_layer_asset", "preload_layer_assets_from_manifest", "get_equipment_layer_for", "compute_equipment_hash", "build_layer_stack", "dump_layer_stack", "composite_layers", "load_layer_texture", "apply_palette_tint", "get_actor_colors", "composition_cache_key", "get_cached", "store_cached", "invalidate_cache_for", "clear_full_cache", "resolve_fallback_layer", "get_placeholder"]`

## 7. Performance Requirements

- `compose_actor_sprite` cached: **< 0.5ms**
- `compose_actor_sprite_uncached` for 6 layers: **< 15ms**
- Cache lookup: **< 0.1ms**
- Tint application: **< 5ms**

## 8. Error Handling

- Missing layer asset: fall back per FR-08, log once per unique slug
- Null actor_data: return placeholder
- Invalid state/facing: clamp to valid range, log at DEBUG
- Cache overflow (>10000 entries): evict oldest LRU

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/world/sprite_layer_compositor.gd` — NEW
- `godot-client/scripts/world/entity_sprite_catalog.gd` — existing; may delegate to compositor
- `godot-client/assets/shaders/palette_tint.gdshader` — NEW shader file
- `godot-client/tests/automation/godot/test_architecture_sprite_layers.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new HTTP endpoints
- No new autoloads
- No GemRB code port (clean-room rule)
- No PLT/BAM file format loaders (ember uses pre-converted PNG atlases)

## 10. Test Coverage Target

- `test_architecture_sprite_layers.gd` covers AC-01..AC-11
- ≥85% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_architecture_sprite_layers.gd

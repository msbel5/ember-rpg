# PRD: Architecture — Actor Animation State Machine + 8-Direction Sprites
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the actor animation state machine that renders a BG1-fidelity "alive" actor on screen. Today, `godot-client/scripts/world/entity_layer.gd` tweens positions smoothly and `entity_visuals.gd` adds an idle sprite bob, but there is NO per-state animation: a walking actor looks the same as a standing one, an attacking actor doesn't swing, a casting actor doesn't gesture. The actor-facing direction is also not honored. This PRD fills that gap by defining an animation state machine (walk / stand / attack / cast / hit / die / get_up / sleep / sit) with 8-directional sprites per state, integrated into the existing `entity_layer.gd` render pipeline. This is the A2 row in the architectural layers index (`PRD_frontend_extraction_index_v1.md`).

### Reference sources
- **GemRB behavior:** `gemrb/core/CharAnimations.{h,cpp}` (~800 LOC — sprite frame management, palette cycling, directional atlases), `gemrb/core/Animation.{h,cpp}` (~400 LOC — frame cursor, loop/pong/random modes), `gemrb/core/AnimationFactory.{h,cpp}` (asset loader). The sprite file format is BAM/BAMP/PLT (Infinity Engine archive); ember-rpg does NOT port the file format — it uses its own sprite atlases.
- **GemRB state names in engine:** `IE_ANI_STAND`, `IE_ANI_WALK`, `IE_ANI_ATTACK`, `IE_ANI_ATTACK_BACKSLASH`, `IE_ANI_ATTACK_JAB`, `IE_ANI_ATTACK_SLASH`, `IE_ANI_CAST`, `IE_ANI_CONJURE`, `IE_ANI_DAMAGE`, `IE_ANI_DIE`, `IE_ANI_GET_UP`, `IE_ANI_TWITCH`, `IE_ANI_RUN`, `IE_ANI_READY`, `IE_ANI_HEAD_TURN`, `IE_ANI_AWAKE`, `IE_ANI_SLEEP`, `IE_ANI_EMERGE`. ember-rpg does not need all of these in Phase 2 — the minimum set is listed in §2.
- **Direction encoding:** GemRB uses 9 orientations (0..8 — N, NE, E, SE, S, SW, W, NW, and flipped). ember-rpg uses the 8-compass model: N, NE, E, SE, S, SW, W, NW.
- **Ember client existing code:**
  - `godot-client/scripts/world/entity_layer.gd` — actor render loop, tween-based movement
  - `godot-client/scripts/world/entity_visuals.gd` — tinting, idle bob, size lookups (`idle_amplitude`, `idle_speed`)
  - `godot-client/scripts/world/entity_sprite_catalog.gd` — texture lookup
  - Ambient life PRD (`PRD_architecture_ambient_life_v1.md`) emits `visual_delta` messages with `state` and `facing` fields that this PRD's state machine consumes

**Clean-room rule:** Read GemRB's `CharAnimations.h` to extract the state set and direction encoding. Do NOT port any file loaders or PLT/BAM format code. All sprite loading in ember-rpg goes through the existing `entity_sprite_catalog.gd`.

## 2. Scope

**In scope:**
- Animation state enum with the minimum BG1 set: `STAND`, `WALK`, `ATTACK`, `CAST`, `HIT`, `DIE`, `DEAD`, `GET_UP`, `SLEEP`, `SIT`
- 8-compass directional facing: `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`
- Per-actor state machine that picks the right sprite frame based on (state, facing, frame_index)
- Automatic state transitions driven by `visual_delta` WS messages (walk on position change, hit on damage event, die on HP=0, etc.)
- Frame cursor advancement at fixed rate (e.g. 12 FPS for animation playback regardless of display framerate)
- Loop modes: LOOP, ONCE (like DIE), PONG (like HEAD_TURN), RANDOM (like TWITCH)
- Animation event hooks: attack_hit_frame, cast_launch_frame, die_final_frame — fires signals the combat kernel can subscribe to
- Sprite atlas lookup via `entity_sprite_catalog.gd` with fallback to generic placeholders when a specific state/direction is missing

**Out of scope:**
- File format loaders (BAM/PLT from GemRB — not ported)
- Sprite authoring pipeline (art team responsibility)
- Paper-doll equipment overlays (`PRD_architecture_sprite_layers_v1.md`)
- Area ambient animations like torches / flags (`PRD_architecture_area_ambient_v1.md`)
- Combat resolution (backend kernel)

## 3. Functional Requirements (FR)

**FR-01:** Define an enum `ActorState` with exactly 10 values: `STAND`, `WALK`, `ATTACK`, `CAST`, `HIT`, `DIE`, `DEAD`, `GET_UP`, `SLEEP`, `SIT`.

**FR-02:** Define an enum `Facing` with exactly 8 values: `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`.

**FR-03:** Every actor node rendered by `entity_layer.gd` MUST have an attached `ActorAnimationController` (new class) that tracks current state, facing, frame cursor, frame count, loop mode, and tick timer.

**FR-04:** `ActorAnimationController.tick(delta)` MUST advance the frame cursor at the controller's configured rate (default 12 FPS → ~83ms per frame), handling loop/once/pong/random mode at the end of the cycle.

**FR-05:** When a `visual_delta` message arrives with a position change for an actor, the controller MUST transition to `WALK` state, set `facing` to the direction from old position to new position, and stay in `WALK` until the next tick with no position change (then transition to `STAND`).

**FR-06:** When a `visual_delta` message arrives with an explicit `state` field (from `SleepAtNightNode` or similar), the controller MUST honor it — e.g. set state to `SLEEP` and hold.

**FR-07:** The combat engine MUST be able to drive actor animations via a new `Backend` signal `actor_animation_event(actor_id, event_type, data)`. Event types: `"attack_started"`, `"attack_hit_frame"`, `"spell_cast_started"`, `"spell_launched"`, `"damage_taken"`, `"death"`, `"resurrected"`.

**FR-08:** The `ATTACK` state MUST emit an `attack_hit_frame` signal at a specific frame (configurable per weapon; default frame 3 of 6). The combat kernel listens for this to time the actual damage calculation so visual and mechanic stay in sync.

**FR-09:** The `DIE` state MUST play once (loop mode `ONCE`) and transition to `DEAD` on final frame. `DEAD` state holds the final frame indefinitely.

**FR-10:** When the actor is in `DEAD`, `entity_layer.gd` MUST apply a grayscale shader + darken modulate (matching `PRD_frontend_party_portraits_v1.md` death overlay).

**FR-11:** Sprite atlas lookup: `entity_sprite_catalog.get_sprite_for(template_id, state, facing, frame_index)` MUST return the right sub-region. If specific (state, facing) is missing, fall back to `(state, S)` (south), then to `(STAND, S)` generic.

**FR-12:** The animation controller MUST handle facing interpolation: when a new facing arrives that differs from current by ≥90°, play a brief `HEAD_TURN`-style snap animation (can be as simple as skipping directly to the new facing — no long rotation animation required in Phase 2).

## 4. Data Structures

    # godot-client/scripts/world/actor_animation_controller.gd
    class_name ActorAnimationController extends Node
    
    enum ActorState {
        STAND,
        WALK,
        ATTACK,
        CAST,
        HIT,
        DIE,
        DEAD,
        GET_UP,
        SLEEP,
        SIT,
    }
    
    enum Facing {
        N, NE, E, SE, S, SW, W, NW
    }
    
    enum LoopMode {
        LOOP,        # continuous (WALK, STAND)
        ONCE,        # play then stop on final frame (DIE → DEAD)
        PONG,        # play forward then backward (HEAD_TURN)
        RANDOM,      # advance with random probability (TWITCH)
    }
    
    const DEFAULT_FPS := 12.0
    const FRAMES_PER_STATE := {
        ActorState.STAND: 4,
        ActorState.WALK:  6,
        ActorState.ATTACK: 6,
        ActorState.CAST:  8,
        ActorState.HIT:   3,
        ActorState.DIE:   10,
        ActorState.DEAD:  1,
        ActorState.GET_UP: 5,
        ActorState.SLEEP: 1,
        ActorState.SIT:   1,
    }
    const LOOP_MODE_PER_STATE := {
        ActorState.STAND: LoopMode.LOOP,
        ActorState.WALK:  LoopMode.LOOP,
        ActorState.ATTACK: LoopMode.ONCE,
        ActorState.CAST:  LoopMode.ONCE,
        ActorState.HIT:   LoopMode.ONCE,
        ActorState.DIE:   LoopMode.ONCE,
        ActorState.DEAD:  LoopMode.LOOP,
        ActorState.GET_UP: LoopMode.ONCE,
        ActorState.SLEEP: LoopMode.LOOP,
        ActorState.SIT:   LoopMode.LOOP,
    }
    
    var _current_state: int = ActorState.STAND
    var _current_facing: int = Facing.S
    var _frame_cursor: int = 0
    var _frame_timer: float = 0.0
    var _fps: float = DEFAULT_FPS
    var _actor_id: String = ""
    var _sprite: Sprite2D                                  # the actual sprite node to update
    var _attack_hit_fired_for_cycle: bool = false          # prevents double-firing the hit event
    var _last_position: Vector2i = Vector2i.ZERO
    var _ticks_since_position_change: int = 0

## 5. Public API — methods that MUST exist

New file: `godot-client/scripts/world/actor_animation_controller.gd`

    # ---- construction ----
    func _init(actor_id: String, sprite: Sprite2D) -> void
    func _ready() -> void
    func _process(delta: float) -> void                                          # drives tick
    
    # ---- state ----
    func set_state(new_state: int) -> void
    func get_state() -> int
    func set_facing(new_facing: int) -> void
    func get_facing() -> int
    func set_state_and_facing(state: int, facing: int) -> void
    
    # ---- ticking ----
    func tick(delta: float) -> void                                              # advances frame cursor by fps * delta
    func advance_frame() -> void                                                 # +1 frame, handles loop/once/pong/random
    func on_cycle_complete() -> void                                             # fired when a non-loop state finishes
    func reset_frame_cursor() -> void
    
    # ---- direction helpers ----
    func facing_from_vector(delta: Vector2i) -> int                              # dx/dy → N/NE/E/...
    func facing_to_vector(facing: int) -> Vector2i                               # inverse
    func compute_facing_toward(from: Vector2i, to: Vector2i) -> int
    
    # ---- sprite resolution ----
    func current_frame_texture() -> Texture2D                                    # calls entity_sprite_catalog
    func current_frame_region() -> Rect2                                         # atlas sub-rect
    func apply_to_sprite() -> void                                               # updates self._sprite.texture and region
    
    # ---- event hooks ----
    func on_position_changed(old_pos: Vector2i, new_pos: Vector2i) -> void       # triggers WALK transition
    func on_state_override_from_delta(state_name: String) -> void                # from visual_delta "state" field
    func on_combat_event(event_type: String, data: Dictionary) -> void           # attack_started / attack_hit_frame / etc.
    
    # ---- signals emitted ----
    signal state_changed(new_state: int)
    signal facing_changed(new_facing: int)
    signal attack_hit_frame_reached(actor_id: String)
    signal spell_launched(actor_id: String)
    signal die_cycle_completed(actor_id: String)
    signal cycle_completed(actor_id: String, state: int)

Extend `entity_layer.gd` with:

    # attach controller per actor
    func _attach_animation_controller(actor_id: String, sprite: Sprite2D) -> ActorAnimationController
    func _get_animation_controller(actor_id: String) -> ActorAnimationController
    
    # wire visual_delta + combat events
    func apply_visual_delta_to_animations(delta_payload: Dictionary) -> void
    func on_combat_event(actor_id: String, event_type: String, data: Dictionary) -> void

Extend `entity_sprite_catalog.gd` with:

    static func get_sprite_for(template_id: String, state: int, facing: int, frame_index: int) -> Dictionary
        # returns {texture: Texture2D, region: Rect2}
    static func has_sprite_for(template_id: String, state: int, facing: int) -> bool
    static func fallback_sprite_for(template_id: String) -> Dictionary

Extend `Backend` autoload with:

    signal actor_animation_event(actor_id: String, event_type: String, data: Dictionary)
    # emitted when the WS runtime delivers an actor_animation_event message from the combat kernel

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01, FR-02]:** Both enums exist with exactly the specified values. Verified by `ActorState.keys().size() == 10` and `Facing.keys().size() == 8`.

**AC-02 [FR-03]:** Every actor in `entity_layer._actors_by_id` MUST have an attached `ActorAnimationController` after `render_entities()`. Verified by iterating and asserting `_get_animation_controller(id) != null`.

**AC-03 [FR-04]:** Creating a controller, setting state to `WALK`, calling `tick(0.1)` repeatedly, and measuring that `_frame_cursor` advances by roughly `ceil(12 * 0.1 * N)` after N ticks (within ±1).

**AC-04 [FR-05]:** Calling `on_position_changed((10,10), (11,10))` MUST transition state to `WALK` and facing to `E`.

**AC-05 [FR-06]:** Receiving a `visual_delta` with `state="sleep"` MUST call `on_state_override_from_delta("sleep")` which transitions the controller to `ActorState.SLEEP`.

**AC-06 [FR-08]:** When state is `ATTACK` and the frame cursor reaches frame 3, `attack_hit_frame_reached(actor_id)` MUST be emitted exactly once per attack cycle.

**AC-07 [FR-09]:** Setting state to `DIE`, ticking until all 10 frames have played, the state MUST automatically transition to `DEAD` and `die_cycle_completed(actor_id)` MUST be emitted once.

**AC-08 [FR-10]:** An actor in `DEAD` state MUST have `entity_layer` apply a grayscale + darken modulate to its sprite. Verified by inspecting the sprite's modulate color.

**AC-09 [FR-11]:** Calling `get_sprite_for("merchant", ActorState.WALK, Facing.NE, 2)` with a template that only has `STAND` sprites MUST fall back to the STAND frame without crashing. Verified by a unit test.

**AC-10 [reflection]:** Every method in §5 MUST exist on the respective scripts.

## 7. Performance Requirements

- `tick(delta)` per actor: **< 0.2ms** (budget for 30 actors per frame: 6ms)
- `apply_to_sprite()`: **< 0.1ms** (sprite texture/region swap is cheap)
- Sprite catalog lookup: **< 0.05ms** per call (cached in hash map)
- Total animation cost for 30 actors at 60 FPS: **< 10ms / frame**

## 8. Error Handling

- Invalid state value: clamp to `STAND`, log at WARNING
- Invalid facing value: clamp to `S`, log at WARNING
- Missing sprite for (template, state, facing, frame): fallback chain per FR-11, log once per unique miss
- Frame cursor out of range: wrap for LOOP, clamp for ONCE, mirror for PONG
- Combat event for unknown actor_id: no-op, log at DEBUG

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/world/actor_animation_controller.gd` — NEW
- `godot-client/scripts/world/entity_layer.gd` — extend per §5
- `godot-client/scripts/world/entity_sprite_catalog.gd` — extend per §5
- `godot-client/autoloads/backend.gd` — add `actor_animation_event` signal
- `godot-client/tests/automation/godot/test_architecture_actor_animation.gd` — NEW

**Backend (consumed, NOT modified):**
- `visual_delta` messages from `PRD_architecture_ambient_life_v1.md` provide `state` + `facing` fields — this PRD's consumer honors them
- Combat kernel SHOULD emit `actor_animation_event` messages on attack / cast / damage / death — if it doesn't yet, this PRD specifies the message format and the combat kernel PRD absorbs the emission

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new autoloads
- No BAM/PLT file loader (GemRB formats are out of scope)
- No GemRB code port

## 10. Test Coverage Target

- `test_architecture_actor_animation.gd` MUST cover AC-01..AC-10
- ≥85% branch coverage on `actor_animation_controller.gd`
- Performance test: simulate 30 actors, run `tick()` for 10 frames, assert total time < 60ms

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_architecture_actor_animation.gd

## 12. Implementation notes

- Start with a **minimum viable set** of states: STAND, WALK, DIE, DEAD. Add ATTACK/CAST/HIT in a second pass once art is ready.
- Sprite atlases can be simple horizontal strips per (state, facing) to start; per-template art can replace them without touching the state machine.
- The animation tick can be shared across all actors via a single autoload timer (12 FPS global tick), OR per-actor local timers. Per-actor is simpler to reason about but costs more timer instances. Start with per-actor; optimize if profiler shows it's hot.
- The `attack_hit_frame` concept is BG1-accurate: the visual swing hits at a specific frame, and the damage math should happen at that moment. The combat kernel subscribes to this signal to time its resolution.
- For non-humanoid templates (spider, wolf), the state set is smaller (no CAST, no SLEEP maybe) — the state machine handles missing frames via the FR-11 fallback chain.

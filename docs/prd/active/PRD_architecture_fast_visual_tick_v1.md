# PRD: Architecture — Fast Visual Tick Infrastructure
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Formalize the **fast visual tick lane** — the ≥30 Hz delta stream that pushes actor position/facing/state changes from backend to client, parallel to the 30s macro tick. This PRD captures the class signatures, delta compression, coalescing, back-pressure, and pause semantics required to make the `VisualTickLoop` (introduced in `PRD_architecture_ambient_life_v1.md`) a stable subsystem.

### Reference sources
- **GemRB behavior:** No direct equivalent — GemRB runs at native framerate with interpolated movement. ember separates macro ticks (30s = game hour) from visual ticks (33ms = ~30 Hz animation). This PRD formalizes that split.
- **Ember targets:**
  - `frp-backend/engine/api/campaign/visual_tick_loop.py` — from ambient_life PRD (may exist or not yet)
  - `frp-backend/engine/api/campaign/runtime_transport.py` — existing; extend with delta emission
  - `godot-client/autoloads/backend_runtime.gd` — existing; extend with visual_delta handler
  - `godot-client/autoloads/game_state.gd` — existing; add `apply_visual_delta`
  - `godot-client/scripts/world/entity_layer.gd` — existing; consumes position updates

**Clean-room rule applies where relevant.**

## 2. Scope

**In scope:**
- `VisualTickLoop` class with start/stop/pause/resume/tick_once
- Delta compression: emit only changed fields per actor
- Coalescing: merge multiple deltas within a frame
- Back-pressure: drop intermediate deltas if WS queue full
- Pause conditions: combat, dialog, tactical pause, modal UI
- Kill switch via env var `EMBER_DISABLE_VISUAL_TICK=1`
- Per-actor rate limit: max 1 delta per visual tick per actor (coalesce changes)
- Client `apply_visual_delta` + `entity_layer` tween integration

**Out of scope:**
- Game time advancement (only macro tick advances time)
- Spawn/despawn via visual tick (only existing actors update)
- Combat resolution
- New WebSocket channels (reuses existing transport)

## 3. Functional Requirements (FR)

**FR-01:** `VisualTickLoop.__init__(runtime, campaign_id, interval=0.033, on_tick=None)` MUST initialize an asyncio task configuration (default ~30 Hz).

**FR-02:** `start()` MUST begin the asyncio task. `stop()` MUST cancel it cleanly. Both MUST be idempotent.

**FR-03:** `pause(reason)` MUST add a reason to a pause set. Ticks are suppressed while the set is non-empty. `resume(reason)` removes the reason.

**FR-04:** Automatic pause on: `context.in_combat()`, `context.has_active_dialog()`, `context.runtime_mode == "tactical_pause"`, modal UI open (via a runtime flag).

**FR-05:** `tick_once()` MUST execute one tick iteration synchronously (for testing).

**FR-06:** Each tick: iterate `context.ambient_actors`, compute position/facing/state deltas since last tick, build a `visual_delta` payload with ONLY changed fields per actor, push via `on_tick` callback.

**FR-07:** `_compute_deltas(context) -> list[dict]` MUST return a list of per-actor delta dicts with only changed fields (`id` is always present; `position`/`facing`/`state` only if changed).

**FR-08:** `_compress_deltas(deltas) -> dict` MUST package the list into a `{type: "visual_delta", tick_index, actors: [...]}` message.

**FR-09:** Back-pressure: if the transport queue is full, MUST drop the current tick's deltas and log at DEBUG. Visual jitter acceptable; simulation integrity unaffected.

**FR-10:** Kill switch: if `os.environ.get("EMBER_DISABLE_VISUAL_TICK") == "1"`, `start()` MUST return immediately without starting the task. Log at INFO.

**FR-11:** The client handler `BackendRuntime.on_visual_delta_received` MUST call `GameState.apply_visual_delta(payload)` which updates affected actor positions.

**FR-12:** `GameState.apply_visual_delta(payload)` MUST merge the delta into the actors list (only the provided fields) and emit `entity_layer_needs_refresh` (or equivalent signal) so the existing tween kicks in.

## 4. Data Structures

    # frp-backend/engine/api/campaign/visual_tick_loop.py
    
    from __future__ import annotations
    import asyncio
    import logging
    import os
    from typing import Any, Callable, Coroutine, Optional
    
    logger = logging.getLogger(__name__)
    
    DEFAULT_VISUAL_TICK_INTERVAL = 0.033  # ~30 Hz
    KILL_SWITCH_ENV = "EMBER_DISABLE_VISUAL_TICK"
    MAX_DELTAS_PER_TICK = 50  # safety
    
    class VisualTickLoop:
        def __init__(
            self,
            runtime: Any,
            campaign_id: str,
            *,
            interval: float = DEFAULT_VISUAL_TICK_INTERVAL,
            on_tick: Optional[Callable[[str, dict], Coroutine]] = None,
        ) -> None: ...
    
    _visual_loops: dict[str, VisualTickLoop] = {}

## 5. Public API — methods that MUST exist

### Backend (Python)

    class VisualTickLoop:
        # lifecycle
        def __init__(self, runtime, campaign_id, *, interval=0.033, on_tick=None) -> None
        
        @property
        def running(self) -> bool
        
        @property
        def paused(self) -> bool
        
        @property
        def pause_reasons(self) -> tuple[str, ...]
        
        async def start(self) -> None
        async def stop(self) -> None
        def pause(self, reason: str = "manual") -> None
        def resume(self, reason: str = "manual") -> None
        def set_on_tick(self, callback: Optional[Callable]) -> None
        
        # core tick
        async def _loop(self) -> None                                            # async task body
        async def tick_once(self) -> None
        async def _execute_tick(self) -> None
        def _should_pause_auto(self, context) -> bool
        
        # delta computation
        def _compute_deltas(self, context) -> list[dict]
        def _diff_actor(self, actor, prev_snapshot: dict) -> Optional[dict]
        def _compress_deltas(self, deltas: list[dict]) -> dict
        def _snapshot_actor(self, actor) -> dict
        
        # back-pressure
        def _transport_queue_full(self) -> bool
        def _drop_tick_due_to_backpressure(self) -> None
    
    # module-level
    async def start_visual_tick_loop(runtime, campaign_id, on_tick=None, interval: float = DEFAULT_VISUAL_TICK_INTERVAL) -> VisualTickLoop
    async def stop_visual_tick_loop(campaign_id: str) -> None
    def get_visual_tick_loop(campaign_id: str) -> Optional[VisualTickLoop]
    def is_visual_tick_enabled() -> bool                                         # reads kill switch env

### Client (GDScript)

    # godot-client/autoloads/backend_runtime.gd (existing — add)
    func on_visual_delta_received(payload: Dictionary) -> void
    func register_visual_delta_handler() -> void
    
    # godot-client/autoloads/game_state.gd (existing — add)
    func apply_visual_delta(payload: Dictionary) -> void
    func merge_actor_delta(actor_id: String, delta_fields: Dictionary) -> void
    func emit_entity_refresh() -> void

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** `VisualTickLoop(runtime, "camp_1")` creates an instance with `interval == 0.033`.

**AC-02 [FR-02]:** Calling `await loop.start()` twice is idempotent (no double task).

**AC-03 [FR-03]:** `loop.pause("combat")` then `loop.paused == True`. `loop.resume("combat")` then `paused == False`.

**AC-04 [FR-04]:** When `context.in_combat() == True`, `_should_pause_auto(context) == True`.

**AC-05 [FR-05]:** `tick_once()` on a campaign with 3 ambient actors MUST call `on_tick` once with a payload containing at most 3 actor entries.

**AC-06 [FR-06]:** Two consecutive ticks without any actor movement MUST result in the second tick emitting an empty `actors` list.

**AC-07 [FR-07]:** `_diff_actor(actor, prev_snapshot)` with no changes returns `None`. With position change returns a dict containing `{id, position}` only.

**AC-08 [FR-08]:** `_compress_deltas([{"id": "a", "position": (5, 5)}])` returns a dict with keys `type`, `tick_index`, `actors` where `actors == [{id, position}]`.

**AC-09 [FR-10]:** With `EMBER_DISABLE_VISUAL_TICK=1` env set, `start()` exits early without scheduling a task.

**AC-10 [FR-11, FR-12, client]:** A headless Godot test that injects a synthetic `visual_delta` payload into `BackendRuntime.on_visual_delta_received` MUST result in the affected actor's `GameState.actors` entry being updated with the new position.

**AC-11 [reflection]:** A Python test MUST import `VisualTickLoop` and verify every method/property in §5 exists. A Godot test MUST verify the new client methods exist on the respective autoloads. Combined enumerated lists:

Backend:
`["running", "paused", "pause_reasons", "start", "stop", "pause", "resume", "set_on_tick", "_loop", "tick_once", "_execute_tick", "_should_pause_auto", "_compute_deltas", "_diff_actor", "_compress_deltas", "_snapshot_actor", "_transport_queue_full", "_drop_tick_due_to_backpressure"]`

Client (backend_runtime.gd):
`["on_visual_delta_received", "register_visual_delta_handler"]`

Client (game_state.gd):
`["apply_visual_delta", "merge_actor_delta", "emit_entity_refresh"]`

## 7. Performance Requirements

- Visual tick per tick for 20 actors: **< 10ms** (budget is 33ms per tick at 30 Hz)
- Delta compute per actor: **< 0.3ms**
- WS message size per tick: **< 2KB** for 10 moving actors
- Client `apply_visual_delta` for 10 actors: **< 5ms**
- Client frame drops at 30 Hz visual tick under 20-actor load: **0**

## 8. Error Handling

- Campaign removed mid-tick: stop the loop, log at INFO
- Behavior tree exception during tick: catch per-actor, skip that actor, continue others
- Transport queue overflow: drop the current tick's deltas (back-pressure), log at DEBUG
- Client delta for unknown actor_id: skip, log at DEBUG
- Malformed delta payload: skip, log at WARNING

## 9. Integration Points

**Backend (editable):**
- `frp-backend/engine/api/campaign/visual_tick_loop.py` — extend (or create) per §5
- `frp-backend/engine/api/campaign/runtime.py` — wire `start_visual_tick_loop` alongside `start_tick_loop` on campaign start
- `frp-backend/engine/api/campaign/runtime_transport.py` — ensure `visual_delta` message type is recognized and routed
- `frp-backend/tests/test_visual_tick_loop_architecture.py` — NEW

**Client (editable):**
- `godot-client/autoloads/backend_runtime.gd` — add `on_visual_delta_received`, `register_visual_delta_handler`
- `godot-client/autoloads/game_state.gd` — add `apply_visual_delta`, `merge_actor_delta`, `emit_entity_refresh`
- `godot-client/tests/automation/godot/test_architecture_fast_visual_tick.gd` — NEW

**Backend (consumed, NOT modified):**
- Existing `CampaignTickLoop` (macro) — parallel, independent
- Existing WebSocket transport — reused, no changes

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new HTTP endpoints
- No new WebSocket channels
- No new autoloads
- No GemRB code port (clean-room rule — where applicable)
- NO game time advancement in the visual tick (macro tick owns time)

## 10. Test Coverage Target

- `test_visual_tick_loop_architecture.py` covers AC-01..AC-09 and AC-11 (backend portion)
- `test_architecture_fast_visual_tick.gd` covers AC-10 and AC-11 (client portion)
- ≥85% branch coverage on `visual_tick_loop.py`
- Full backend suite stays green

## 11. Verification

    # Backend
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_visual_tick_loop_architecture.py -q
    
    # Client
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_architecture_fast_visual_tick.gd
    
    # Full backend smoke
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests -q

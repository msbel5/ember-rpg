# PRD: Architecture — Ambient Life (NPC Wander + Schedules + Fast Visual Tick)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Make the ember-rpg game world feel **alive** in the BG1/BG2 sense. Today, when a player enters a settlement and stops moving, NPCs stand still because:

1. The backend tick loop runs at 30 real seconds per game hour (`frp-backend/engine/api/campaign/tick_loop.py:24`) — far too slow for visible walking.
2. `advance_world_tick()` does not iterate NPCs and update their positions via wander/schedule logic — it advances macro simulation but not per-actor motion.
3. The existing `frp-backend/engine/world/behavior_tree.py` has RimWorld-style primitives (PriorityNode, SequenceNode, ConditionNode) but no NPCs are tagged with a "wander + schedule" tree that actually produces position deltas.
4. The Godot client's `entity_layer.gd` already tweens between old and new tile positions over 0.24s (line 8), so if the backend pushes new positions every ~1 second, visible walking just works. But the backend doesn't push them at that cadence.

This PRD defines the minimum vertical slice that produces visible ambient NPC movement on a BG1-style settlement map: **daily schedules, wander within bounds, and a fast visual tick lane that pushes sub-second position deltas to the client without affecting gameplay mechanics**.

### Reference sources
- **GemRB behavior — script slots:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\core\Scriptable\Scriptable.h` lines 49–58 define 8 script slots per actor (SCR_OVERRIDE through SCR_DEFAULT). The SCR_GENERAL and SCR_DEFAULT slots run constantly and produce idle behaviors (wander, gossip, work). BCS scripts check triggers (time, location, distance to PC) and emit actions (WalkTo, Say, Face, Wait).
- **GemRB behavior — pathfinding + movement:** `gemrb/core/Scriptable/Movable.{h,cpp}` (513 + 126 LOC) — path execution, facing, orientation, step interpolation.
- **GemRB behavior — calendar + time:** `gemrb/core/Calendar.{h,cpp}` — game time, day/night, hour-of-day for schedule triggers.
- **GemRB behavior — area animations:** `gemrb/core/AreaAnimation.{h,cpp}` — ambient environmental loops (torches, flags, water) that run independently of actor scripts.
- **ember-rpg existing code — behavior tree:** `frp-backend/engine/world/behavior_tree.py` (uses Status enum, BehaviorContext, PriorityNode, SequenceNode, ConditionNode — reuse these, do NOT reinvent)
- **ember-rpg existing code — tick loop:** `frp-backend/engine/api/campaign/tick_loop.py` (CampaignTickLoop with 30s default interval, on_tick push callback, pause/resume)
- **ember-rpg existing code — entity rendering:** `godot-client/scripts/world/entity_layer.gd` (MOVE_TWEEN_DURATION = 0.24, y_sort, idle sprite bob via entity_visuals.idle_amplitude)
- **ember-rpg existing code — runtime transport:** `frp-backend/engine/api/campaign/runtime_transport.py`, `websocket_support.py` (WS channel already landed and proven green in the runtime-authority refactor on 2026-04-10)

**Clean-room rule:** Read GemRB Scriptable / Movable / Calendar source to understand what a BCS-driven wander+schedule system DOES. Do not port BCS bytecode or any C++ code. The ember-rpg wander+schedule system is expressed using the existing Python behavior_tree primitives plus new leaf nodes.

## 2. Scope

**In scope:**
- A new fast visual tick lane (1-second cadence by default, configurable) that runs in parallel with the existing 30-second macro tick. Only updates actor positions and facing — does NOT advance macro simulation (economy, jobs, colony).
- New behavior tree leaf nodes for NPC ambient behavior: `WanderInBoundsNode`, `FollowScheduleNode`, `FaceTargetNode`, `WaitNode`, `GoToWaypointNode`
- A minimal schedule data structure per NPC: `{hour: waypoint_name}` plus default "wander" waypoint
- Per-settlement waypoint registry: 3-5 named anchors per settlement (e.g. "tavern_counter", "market_stall", "temple_door", "bed_home") populated by `region_projection.py` or `worldgen/npc_authored.py`
- Broadcast of position deltas via the existing WebSocket transport on the visual-tick cadence
- Client-side smooth interpolation via the existing `entity_layer.gd` tween (no client changes other than handling the new message type if needed)
- A "sleeping" state for NPCs during night hours (stay in bed, don't emit position deltas)

**Out of scope:**
- Animation state machine beyond position changes (walk vs. stand vs. attack — covered by `PRD_architecture_actor_animation_v1.md`)
- Area ambient animations (torches, water — covered by `PRD_architecture_area_ambient_v1.md`)
- Combat AI (covered by existing `PRD_kernel_combat_engine_v1.md`)
- Dialog chatter over NPCs' heads (separate feature, Phase 3)
- Job execution — NPCs walking to a workstation and performing an animation (separate PRD; this one just gets them to the right place at the right time)

## 3. Functional Requirements (FR)

**FR-01:** A new class `VisualTickLoop` MUST exist in `frp-backend/engine/api/campaign/visual_tick_loop.py` that runs an asyncio task at a configurable interval (**default 33 ms = ~30 Hz**) while a campaign is active and in exploration mode. It MUST NOT run during combat, dialog, tactical pause, or modal screens. The interval is tunable via constructor param `tick_interval` and env var `EMBER_VISUAL_TICK_INTERVAL` (seconds, float); valid range `0.016` (~60 Hz) to `1.0` (slow fallback). User-confirmed on 2026-04-10 that 30-subticks-per-second is acceptable — default 30 Hz is the target; 1 Hz is the fallback only if performance does not hold. The implementing agent MUST measure and report per-tick CPU on a 20-NPC area before locking the default, adjusting upward if budget is blown.

**FR-02:** Each tick, `VisualTickLoop` MUST iterate all NPCs in the player's current area that have a `wander_tree` attached, evaluate their behavior tree once, collect any resulting position/facing changes, and push a compact `visual_delta` message through the existing WebSocket channel.

**FR-03:** The `visual_delta` message format MUST be:

    {
      "type": "visual_delta",
      "tick_index": int,
      "actors": [
        {"id": str, "position": [int, int], "facing": "north|east|south|west|ne|nw|se|sw", "state": "walk|stand|sleep|sit"}
      ]
    }

Only actors whose state changed since the previous visual tick are included. Empty actor lists are allowed (keepalive) but throttled to once per 5 visual ticks max.

**FR-04:** The behavior tree MUST support these new leaf nodes (in `frp-backend/engine/world/behavior_tree.py` or a new sibling `behavior_tree_leaves.py`). Each MUST be a subclass of `BehaviorNode` with the exact signatures and post-tick contracts below — Copilot CLI MUST generate these exact method names:

    class WanderInBoundsNode(BehaviorNode):
        def __init__(self, center: tuple[int, int], radius: int, step_cadence: int = 15, name: str = "WanderInBounds") -> None: ...
        def tick(self, ctx: BehaviorContext) -> Status: ...
            # Post: if ctx.entity.position changes, ctx.blackboard["last_step_tick"] = current tick
            #       sets ctx.entity.facing toward chosen target
            #       returns RUNNING while moving, SUCCESS on arrival, FAILURE if no reachable tile in radius
            #       step_cadence controls how many visual ticks between movement decisions

    class FollowScheduleNode(BehaviorNode):
        def __init__(self, schedule: dict[int, str], waypoints: dict[str, tuple[int, int]], name: str = "FollowSchedule") -> None: ...
        def tick(self, ctx: BehaviorContext) -> Status: ...
            # Reads ctx.game_time.hour (0..23). Finds self.schedule.get(hour) or falls through
            # to previous scheduled hour (search backward). If no schedule entry, returns FAILURE.
            # Calls GoToWaypointNode.tick() internally with target = self.waypoints[waypoint_name]
            # Returns RUNNING while walking, SUCCESS on arrival, FAILURE if waypoint name unknown

    class GoToWaypointNode(BehaviorNode):
        def __init__(self, target: tuple[int, int], name: str = "GoToWaypoint") -> None: ...
        def tick(self, ctx: BehaviorContext) -> Status: ...
            # Moves ctx.entity one tile toward self.target using the backend pathfinder if available,
            # otherwise Bresenham step. Sets ctx.entity.facing each step.
            # Returns RUNNING until arrived, SUCCESS on arrival.

    class FaceTargetNode(BehaviorNode):
        def __init__(self, target: tuple[int, int], name: str = "FaceTarget") -> None: ...
        def tick(self, ctx: BehaviorContext) -> Status: ...
            # Sets ctx.entity.facing to the 8-compass direction from entity position toward target.
            # Always returns SUCCESS. Non-blocking.

    class WaitNode(BehaviorNode):
        def __init__(self, ticks: int, name: str = "Wait") -> None: ...
        def tick(self, ctx: BehaviorContext) -> Status: ...
            # Uses ctx.blackboard["{self.name}_elapsed"] counter.
            # Returns RUNNING for self.ticks consecutive ticks, then SUCCESS and resets counter.

    class SleepAtNightNode(BehaviorNode):
        def __init__(self, bed: tuple[int, int], night_hours: range, name: str = "SleepAtNight") -> None: ...
        def tick(self, ctx: BehaviorContext) -> Status: ...
            # If ctx.game_time.hour not in self.night_hours, returns FAILURE (lets priority fall through).
            # Otherwise walks to self.bed via GoToWaypointNode.tick(), then sets ctx.entity.state = "sleep".
            # Returns RUNNING while walking, SUCCESS on bed arrival, stays SUCCESS during night.

Pathfinder fallback note: if no backend pathfinder exists yet, implement a simple helper `def step_toward(pos, target, map_data) -> tuple[int,int]` in `behavior_tree_leaves.py` using 8-way Bresenham with obstacle check from `map_data["tiles"]`. Document this as a known limitation to be replaced when `PRD_architecture_pathfinding_v1.md` lands.

**FR-05:** A default ambient behavior tree MUST be constructed by a new helper `build_default_ambient_tree(npc_record) -> BehaviorNode` that composes: `PriorityNode([SleepAtNightNode(...), FollowScheduleNode(...), WanderInBoundsNode(...)])`. This becomes the default for any NPC flagged `ambient_life: true` in the authored data.

**FR-06:** `worldgen/npc_authored.py` (or `region_projection.py`) MUST provide a `waypoints` dictionary per settlement of at least 3 named anchors derived from the area layout (e.g. `tavern_counter`, `market_stall`, `temple_door`). Schedules for each NPC select from these names.

**FR-07:** The visual tick loop MUST NOT advance game time. Game time only advances in the existing 30-second macro tick loop. Schedule lookups use the current `game_state.calendar.hour` which is updated by the macro tick.

**FR-08:** When the player enters a new area, the visual tick loop MUST load that area's NPCs and start ticking them. When the player leaves, it MUST stop ticking NPCs in the old area.

**FR-09:** The client MUST apply `visual_delta` messages by updating the affected actors' tile positions. The existing `entity_layer.gd` tween handles smooth interpolation; no changes needed there other than wiring the new message type to the same update path that full-snapshot messages use.

**FR-10:** At least 50% of NPCs in a populated settlement MUST have an ambient behavior tree attached on area load. The rest (shopkeepers, quest NPCs, scripted event NPCs) may remain stationary by design.

**FR-11:** The visual tick loop MUST have a kill switch: setting environment variable `EMBER_DISABLE_VISUAL_TICK=1` OR sending a runtime command `set_visual_tick disabled` MUST stop all visual ticking. This exists so the kill criterion in `PRD_PLAYABILITY_RESCUE.md` can route around it if the feature destabilizes the runtime.

## 4. Data Structures

Extend the NPC record with:

    class NpcAmbientProfile:
        ambient_life: bool            # default False; set True to enable
        home_tile: (int, int)         # where they sleep
        wander_center: (int, int)     # center of their daily wander area
        wander_radius: int            # typically 4..10 tiles
        schedule: Dict[int, str]      # {hour: waypoint_name}, hours 0..23
        default_waypoint: str         # used when hour not in schedule
        state: Literal["walk", "stand", "sleep", "sit"]
        facing: str                   # 8-compass direction
        _wander_tree: BehaviorNode    # cached compiled tree, not serialized

Extend the settlement/area record with:

    waypoints: Dict[str, (int, int)]  # e.g. {"tavern_counter": (45, 12), "market_stall": (38, 14)}

These extensions SHOULD be additive; NPCs without `ambient_life: true` behave exactly as they do today.

## 5. Public API

New module `frp-backend/engine/api/campaign/visual_tick_loop.py`:

    class VisualTickLoop:
        def __init__(self, runtime, campaign_id, *, interval: float = 1.0, on_tick: Callable | None = None): ...
        async def start(self) -> None: ...
        async def stop(self) -> None: ...
        def pause(self, reason: str = "manual") -> None: ...
        def resume(self, reason: str = "manual") -> None: ...
    
    async def start_visual_tick_loop(runtime, campaign_id, on_tick) -> VisualTickLoop: ...
    async def stop_visual_tick_loop(campaign_id) -> None: ...

Extend `behavior_tree.py` (or a sibling `behavior_tree_leaves.py`) with the new leaf node classes listed in FR-04.

Extend `runtime_transport.py` to recognize the `visual_delta` outbound message type and route it through the existing WebSocket pipeline. No new transport — reuse what's already green.

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01, FR-02]:** Given a campaign with the player standing idle in a populated settlement with `ambient_life` NPCs, after 3 real seconds at least one `visual_delta` message with a non-empty `actors` list MUST have been emitted via the WebSocket channel. Verified by a new backend test that spins up a mock WS client and asserts message receipt.

**AC-02 [FR-04]:** `WanderInBoundsNode(center=(10,10), radius=3)` applied to an actor at `(10,10)`, ticked 20 times at 1Hz, MUST move the actor to at least 2 distinct tiles, all within Chebyshev distance 3 of the center. Verified by a unit test in `frp-backend/tests/test_behavior_tree_leaves.py`.

**AC-03 [FR-04]:** `FollowScheduleNode` with `schedule={9: "market_stall"}` and `waypoints={"market_stall": (50, 20)}`, applied to an actor at `(10, 10)` at game hour 9, ticked N times, MUST produce a path whose final tile is `(50, 20)`. Verified by a unit test.

**AC-04 [FR-04]:** `SleepAtNightNode(bed=(5,5), night_hours=range(22,24))` applied to an actor at game hour 23 MUST walk the actor to `(5, 5)` and set `state="sleep"` on arrival. At game hour 7 (dawn), the actor's state MUST transition out of `sleep`.

**AC-05 [FR-07]:** The visual tick loop running for 10 seconds MUST NOT change `game_state.calendar.hour`. Only the macro tick loop advances game time. Verified by a test that runs both loops and asserts hour is unchanged.

**AC-06 [FR-08]:** When a campaign's player changes areas, the set of actively ticking NPCs MUST match the new area's NPC list, not the old area's. Verified by a test that moves the player and inspects the visual tick loop's actor set.

**AC-07 [FR-09]:** (Client-side) A headless Godot test script that injects a synthetic `visual_delta` into the WebSocket handler MUST observe the corresponding actor node's tile position change and the `entity_layer` tween being initiated. Verified by `godot-client/tests/automation/godot/test_visual_delta_client_apply.gd`.

**AC-08 [FR-10]:** On entering a test settlement of 10 NPCs, the runtime snapshot's `world_entities` list MUST contain at least 5 NPCs whose `npc_ambient_profile.ambient_life` is True. Verified by a test.

**AC-09 [FR-11]:** When `EMBER_DISABLE_VISUAL_TICK=1` is set, the visual tick loop MUST NOT emit any `visual_delta` messages over 5 seconds. Verified by a test.

**AC-10 (alive-world manual smoke):** Start the backend, launch Godot, enter a settlement, DO NOT touch keyboard or mouse, watch the world. Within 10 real seconds, at least one NPC MUST visibly walk to a different tile. If this fails three times after implementation, escalate per PRD_PLAYABILITY_RESCUE.md §12 kill criterion — this is the single strongest "F1 feel" test the project has.

## 7. Performance Requirements

- Visual tick loop per-tick CPU: **< 50ms** for a 20-NPC area on a dev machine (measured by timing one full tick)
- WebSocket message rate: **≤ 2 messages per second** per campaign, average (target is 1/s)
- `visual_delta` payload size: **< 2KB** per message for 10 moving actors
- Client frame drop: 0 frames dropped under a 10-NPC visual tick load (verified by `print_stats` during test)
- Behavior tree evaluation per NPC per tick: **< 2ms** (budget 50ms / 25 NPCs)

## 8. Error Handling

- **No pathfinder available:** Fall back to Bresenham straight-line stepping. NPCs may clip through walls in Phase 2. Log once: `[visual_tick] pathfinder unavailable, using fallback`.
- **Waypoint references a name that doesn't exist in the area's waypoints dict:** Skip that schedule entry, fall through to the next priority (wander). Log at WARNING.
- **Behavior tree throws an exception mid-tick:** Catch, log with `logger.exception`, skip that NPC for this tick, keep ticking others. Do NOT crash the tick loop.
- **WebSocket disconnected mid-tick:** The existing `runtime_transport.py` error handling applies; visual tick loop keeps running in memory until `campaign.in_combat()` or the loop is stopped.
- **Macro tick loop paused for combat:** Visual tick loop MUST also pause (reason="combat") so NPCs freeze during turn-based combat (consistent with BG1 behavior in turn-based mode).

## 9. Integration Points

**Backend (editable by this PRD):**
- `frp-backend/engine/api/campaign/visual_tick_loop.py` — NEW
- `frp-backend/engine/world/behavior_tree.py` — extend with new leaf nodes OR add `behavior_tree_leaves.py`
- `frp-backend/engine/api/campaign/runtime.py` — wire `start_visual_tick_loop` alongside the existing `start_tick_loop` in the campaign lifecycle
- `frp-backend/engine/api/campaign/runtime_transport.py` — recognize `visual_delta` message type (pass-through is fine, no new socket plumbing)
- `frp-backend/engine/worldgen/npc_authored.py` — tag half the NPCs with `ambient_life: true` and attach a default schedule drawn from the settlement's waypoints
- `frp-backend/engine/api/campaign/region_projection.py` — ensure area record exposes `waypoints` dictionary derived from the layout (tavern/market/temple anchors)
- `frp-backend/tests/test_visual_tick_loop.py` — NEW
- `frp-backend/tests/test_behavior_tree_leaves.py` — NEW
- `frp-backend/tests/test_visual_delta_ws_emission.py` — NEW

**Client (minimal — or zero — edits):**
- `godot-client/autoloads/backend_runtime.gd` — if the WS handler doesn't already route unknown message types through the snapshot applier, add `visual_delta` routing
- `godot-client/autoloads/game_state.gd` — add `apply_visual_delta(payload: Dictionary)` method that updates the entity positions (this in turn triggers the existing `entity_layer.render_entities` tween)
- `godot-client/tests/automation/godot/test_visual_delta_client_apply.gd` — NEW

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**` (kernel is frozen)
- No edits to any other PRD file
- No new HTTP endpoints
- No new autoloads on the client
- No changes to the 30-second macro tick loop's cadence — the visual tick is a **parallel** lane, not a replacement
- No GemRB code reuse (clean-room rule)

## 10. Test Coverage Target

- New backend tests MUST cover AC-01..AC-09 (client AC-07 stays on the Godot side)
- `run_headless_tests.gd` MUST stay green
- Full backend suite (2008 tests) MUST stay green
- Coverage goal on `visual_tick_loop.py` and new behavior tree leaves: **≥85% line coverage**

## 11. Verification (run in order)

    # 1. Behavior tree leaves
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_behavior_tree_leaves.py -q
    
    # 2. Visual tick loop
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_visual_tick_loop.py -q
    
    # 3. Visual delta WS emission
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_visual_delta_ws_emission.py -q
    
    # 4. Godot headless (must stay green)
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    
    # 5. Godot client visual delta application
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_visual_delta_client_apply.gd
    
    # 6. Full backend smoke
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests -q

All six MUST be green. If the full suite is red, STOP and diagnose before claiming done.

## 12. Manual smoke — the "alive world" test

This is the subjective proof. Without it, no amount of green tests makes the PRD "done."

1. Start the backend: `.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8741 --app-dir frp-backend`
2. Launch Godot: `godot --path godot-client`
3. Click New Game, complete creation, enter a settlement
4. **Put both hands behind your back and do not touch anything.**
5. Watch for 30 seconds. Within that window:
   - At least 3 distinct NPCs MUST visibly walk across tile boundaries
   - At least one NPC MUST change facing direction
   - No NPC MUST visibly teleport (always smooth tween)
6. Advance game time to 22:00 via the pause menu time-skip (if present) or wait. Within 1 real minute:
   - At least one NPC MUST walk toward their `home_tile` and stop
   - NPCs walking outdoors at midnight should be rare (shopkeepers/guards excluded)

If any of the above fails after three implementation attempts, fire the kill criterion in `PRD_PLAYABILITY_RESCUE.md` §12 and pivot to the browser client. This PRD is the single strongest gate on Godot's alive-world viability.

## 13. Implementation notes (non-binding)

- Reuse `behavior_tree.py` primitives; do NOT write a new framework.
- The `WanderInBoundsNode` may use a simple random walk initially — full pathfinding can come in a later PRD.
- The visual tick interval of 1.0s is a default, not a requirement. It can be tuned per-campaign or per-settlement if performance demands.
- Consider batching `visual_delta` messages when multiple NPCs move in the same tick (already implied by the message shape).
- The `facing` field is mostly cosmetic in Phase 2 — the client renders the bucket tint but not per-direction sprites yet. Still populate it so the animation state machine PRD (A2) can build on top.
- Do NOT emit `visual_delta` for NPCs in combat — the combat kernel already owns position updates during turn-based mode.

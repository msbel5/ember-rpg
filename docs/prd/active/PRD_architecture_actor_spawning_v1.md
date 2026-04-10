# PRD: Architecture — Actor Spawning
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify how NPCs and creatures are placed into a loaded area. Four spawn sources: (1) **authored list** (content-file-defined fixed spawns), (2) **spawn points** (random pick from a pool within a bounding box, triggered on area entry), (3) **time-triggered** (e.g. "wolves appear at dusk at the forest edge"), (4) **script-triggered** (from story events). Backend authoritative; this PRD defines the data model and hooks.

### Reference sources
- **GemRB behavior:** `gemrb/plugins/AREImporter/` (area file importer) + `gemrb/core/Map.{h,cpp}` (area with spawn handling) + GemRB's `SpawnGroup` concept
- **Ember target:** `frp-backend/engine/worldgen/npc_generator.py` (existing) + `npc_authored.py` (existing) + `frp-backend/engine/api/campaign/region_projection.py` (existing — extend for spawn injection)

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- 4 spawn source types: fixed, random_point, time_triggered, script_triggered
- `SpawnDefinition` dataclass
- Spawn execution on area load
- Despawn on area exit
- Respawn rules for non-unique creatures after N game hours
- Time-triggered spawn tick checks
- Script-triggered spawn API (for story events to call)

**Out of scope:**
- Area generation from scratch (worldgen authority)
- Encounter tables for random wilderness (separate `travel_encounter` system)
- Creature AI definitions (those come from the creature content files)

## 3. Functional Requirements (FR)

**FR-01:** Define `SpawnDefinition` dataclass with fields: `spawn_id`, `source_type` (enum), `area_id`, `creature_ref`, `position` (for fixed), `bounding_box` (for random_point), `pool_size` (count), `trigger_hour` (for time-triggered), `trigger_script_flag` (for script-triggered), `respawn_hours` (None = never), `is_unique` (bool).

**FR-02:** `SpawnRegistry` MUST aggregate all spawn definitions per area. Load from authored content files on startup.

**FR-03:** `spawn_at_area_entry(area_id)` MUST be called when the player enters an area. It MUST iterate the area's spawn definitions and instantiate actors for fixed + random_point sources that are currently eligible.

**FR-04:** Random_point sources MUST pick `pool_size` random positions within the bounding box using the deterministic campaign RNG (seeded from campaign_id + area_id + spawn_id).

**FR-05:** Time-triggered sources MUST be checked on every macro tick (30s tick). If `current_hour == trigger_hour`, spawn the group.

**FR-06:** Script-triggered sources MUST expose `spawn_from_script(spawn_id)` that story events can call.

**FR-07:** `despawn_on_area_exit(area_id)` MUST remove all actors created by spawns in that area EXCEPT unique ones (unique=quest-critical NPCs persist across transitions).

**FR-08:** `respawn_dead_non_unique(area_id, since_hours)` MUST check whether any non-unique actor that died has had `respawn_hours` game-hours pass since death, and if so, re-spawn them (new actor instance, same definition).

**FR-09:** Every spawn MUST record provenance metadata on the spawned actor: `_spawn_source_id`, `_spawn_time`.

**FR-10:** Spawn success/failure MUST emit events for audit logging: `actor_spawned`, `actor_despawned`, `spawn_failed`.

## 4. Data Structures

    # frp-backend/engine/worldgen/spawn_registry.py
    
    from dataclasses import dataclass, field
    from enum import Enum
    from typing import Optional
    
    class SpawnSourceType(Enum):
        FIXED = "fixed"
        RANDOM_POINT = "random_point"
        TIME_TRIGGERED = "time_triggered"
        SCRIPT_TRIGGERED = "script_triggered"
    
    @dataclass
    class SpawnDefinition:
        spawn_id: str
        source_type: SpawnSourceType
        area_id: str
        creature_ref: str
        position: Optional[tuple[int, int]] = None
        bounding_box: Optional[tuple[int, int, int, int]] = None  # (x1, y1, x2, y2)
        pool_size: int = 1
        trigger_hour: Optional[int] = None
        trigger_script_flag: Optional[str] = None
        respawn_hours: Optional[int] = None
        is_unique: bool = False
        metadata: dict = field(default_factory=dict)
    
    @dataclass
    class SpawnResult:
        spawn_id: str
        actor_ids: list[str]
        success: bool
        reason: str = ""

## 5. Public API — methods that MUST exist

    # frp-backend/engine/worldgen/spawn_registry.py
    
    class SpawnRegistry:
        def __init__(self) -> None: ...
        def register(self, definition: SpawnDefinition) -> None
        def unregister(self, spawn_id: str) -> None
        def get(self, spawn_id: str) -> Optional[SpawnDefinition]
        def list_for_area(self, area_id: str) -> list[SpawnDefinition]
        def load_from_authored(self) -> None
    
    # frp-backend/engine/worldgen/spawner.py
    
    class AreaSpawner:
        def __init__(self, registry: SpawnRegistry, rng_seed: int): ...
        def spawn_at_area_entry(self, area_id: str, campaign_context) -> list[SpawnResult]
        def despawn_on_area_exit(self, area_id: str, campaign_context) -> int
        def check_time_triggered_spawns(self, area_id: str, current_hour: int, campaign_context) -> list[SpawnResult]
        def spawn_from_script(self, spawn_id: str, campaign_context) -> SpawnResult
        def respawn_dead_non_unique(self, area_id: str, since_hours: int, campaign_context) -> list[SpawnResult]
        def spawn_fixed(self, definition: SpawnDefinition, campaign_context) -> SpawnResult
        def spawn_random_point(self, definition: SpawnDefinition, campaign_context) -> SpawnResult
        def pick_random_position_in_box(self, bbox: tuple[int, int, int, int], rng) -> tuple[int, int]
        def instantiate_actor(self, creature_ref: str, position: tuple[int, int], spawn_id: str, campaign_context) -> str
        def apply_provenance(self, actor_id: str, spawn_id: str, campaign_context) -> None
        def is_unique_spawn_alive(self, spawn_id: str, campaign_context) -> bool
        def find_dead_non_unique_actors_for(self, area_id: str, campaign_context) -> list[dict]
        def should_respawn(self, actor_death_info: dict, current_hour: int) -> bool
        def log_spawn_event(self, event_type: str, payload: dict, campaign_context) -> None

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** `SpawnDefinition("test", SpawnSourceType.FIXED, "ar1000", "goblin", position=(10, 10))` creates a valid instance.

**AC-02 [FR-02]:** `SpawnRegistry().register(def)` then `registry.get("test")` returns the definition.

**AC-03 [FR-03]:** Calling `spawn_at_area_entry("ar1000", ctx)` with 3 fixed spawn defs returns 3 `SpawnResult` with `success == True` and instantiates 3 actors in the context.

**AC-04 [FR-04]:** `pick_random_position_in_box((0, 0, 10, 10), rng)` returns a tuple with both values in [0, 10]. Deterministic: same seed yields same result.

**AC-05 [FR-05]:** `check_time_triggered_spawns("ar1000", 18, ctx)` with a definition of `trigger_hour == 18` spawns the group.

**AC-06 [FR-06]:** `spawn_from_script("dragon_appears", ctx)` looks up the spawn_id and invokes its spawn logic.

**AC-07 [FR-07]:** `despawn_on_area_exit("ar1000", ctx)` removes non-unique actors but preserves actors where `_spawn_source_unique == True`.

**AC-08 [FR-08]:** `respawn_dead_non_unique("ar1000", 24, ctx)` re-spawns actors whose death was ≥24 hours ago in game time.

**AC-09 [FR-09]:** After spawning an actor, `actor.metadata._spawn_source_id` equals the spawn's `spawn_id`.

**AC-10 [FR-10]:** Every spawn operation MUST call `log_spawn_event` with the appropriate event type. Verified via spy.

**AC-11 [reflection]:** A test MUST verify every method in §5 exists on `SpawnRegistry` and `AreaSpawner`. Enumerated list (both classes combined):
`["register", "unregister", "get", "list_for_area", "load_from_authored", "spawn_at_area_entry", "despawn_on_area_exit", "check_time_triggered_spawns", "spawn_from_script", "respawn_dead_non_unique", "spawn_fixed", "spawn_random_point", "pick_random_position_in_box", "instantiate_actor", "apply_provenance", "is_unique_spawn_alive", "find_dead_non_unique_actors_for", "should_respawn", "log_spawn_event"]`

## 7. Performance Requirements

- `spawn_at_area_entry` for 10 spawns: **< 50ms**
- `check_time_triggered_spawns` per macro tick: **< 10ms** (hot path)
- Random position pick: **< 1ms** per call

## 8. Error Handling

- Missing creature_ref: skip spawn, log at WARNING, emit `spawn_failed`
- Invalid bounding box (empty): skip spawn, log at WARNING
- Unique spawn already alive when triggered: skip, log at DEBUG
- Dead actor with no respawn_hours: never respawn

## 9. Integration Points

**Backend (editable):**
- `frp-backend/engine/worldgen/spawn_registry.py` — NEW
- `frp-backend/engine/worldgen/spawner.py` — NEW
- `frp-backend/engine/worldgen/npc_authored.py` — existing; extend to feed `SpawnRegistry`
- `frp-backend/engine/api/campaign/region_projection.py` — existing; call `spawner.spawn_at_area_entry` on area load
- `frp-backend/engine/api/campaign/tick_loop.py` — existing; call `spawner.check_time_triggered_spawns` each macro tick
- `frp-backend/tests/test_spawn_registry.py` — NEW
- `frp-backend/tests/test_area_spawner.py` — NEW

**Backend (consumed, NOT modified):**
- `campaign_context` — must expose `actor_store` methods, `current_area_id`, `game_time`, RNG

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new HTTP endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_spawn_registry.py` + `test_area_spawner.py` cover AC-01..AC-11
- ≥85% branch coverage on both modules
- Full backend test suite stays green

## 11. Verification

    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_spawn_registry.py frp-backend\tests\test_area_spawner.py -q
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests -q

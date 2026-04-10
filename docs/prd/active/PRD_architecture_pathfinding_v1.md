# PRD: Architecture — Pathfinding (A*)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify an **A* pathfinding module** for tile-grid area maps, used by `GoToWaypointNode` (ambient life), player movement commands, and combat AI. Public API returns a list of tile steps from start to goal considering walkability, door state, creature blocking, and size-based collision.

### Reference sources
- **GemRB behavior:** `gemrb/core/PathFinder.{h,cpp}` (read top 200 lines for class interface) + `gemrb/core/Scriptable/Movable.{h,cpp}` (path execution, interruption, facing)
- **Ember target:** NEW `frp-backend/engine/world/pathfinding.py`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- `find_path(start, goal, map_data, constraints)` returning a step list or None
- `simplify_path(path)` removing redundant waypoints
- `step_along_path(current, path, distance)` for interpolated movement
- `is_path_blocked(path, map_data)` for re-planning
- `compute_movement_cost(path, terrain_costs)` for time accounting
- Walkability check with terrain type lookup
- Door state awareness (closed = blocked unless passable flag)
- Creature blocking (optional via constraint)
- Diagonal movement cost √2

**Out of scope:**
- Flow-field navigation (alternative algorithm)
- Dynamic obstacle avoidance during path execution (handled by the behavior tree re-planning)
- 3D / z-axis pathfinding

## 3. Functional Requirements (FR)

**FR-01:** `find_path(start, goal, map_data, constraints)` MUST return a list of `tuple[int, int]` tile positions from start to goal inclusive. If no path exists, returns `None`.

**FR-02:** The algorithm MUST be A* with Manhattan OR octile heuristic (octile for 8-directional movement).

**FR-03:** 8-directional movement with diagonal cost √2 ≈ 1.41 and straight cost 1.0.

**FR-04:** Walkability MUST be checked via `map_data["walkable_mask"][y][x]` OR via a terrain type lookup in `TERRAIN_COSTS`.

**FR-05:** Doors MUST be consulted via `constraints["doors"]` — a dict of `{(x, y): {"open": bool, "passable_when_closed": bool}}`.

**FR-06:** Creature blocking MUST be honored if `constraints["block_on_creatures"] == True`. The list of blocked tiles comes from `constraints["occupied_tiles"]`.

**FR-07:** `simplify_path(path)` MUST remove intermediate tiles that lie on a straight line between their neighbors.

**FR-08:** `step_along_path(current, path, distance)` MUST return `(new_pos, remaining_path)` after moving `distance` units along the path.

**FR-09:** `is_path_blocked(path, map_data)` MUST re-check every step of the path and return True if any step is no longer walkable.

**FR-10:** `compute_movement_cost(path, terrain_costs)` MUST sum the per-step terrain costs (default 1.0) across the path.

**FR-11:** Path search MUST have a configurable iteration limit (default 10000) to prevent runaway searches on large maps. On limit exceeded, return None.

**FR-12:** The module MUST handle size-based collision: `constraints["actor_size"]` (1 = 1×1 default, 2 = 2×2, etc.) requires all occupied cells to be walkable.

## 4. Data Structures

    # frp-backend/engine/world/pathfinding.py
    
    from heapq import heappush, heappop
    from math import sqrt
    from typing import Optional
    
    SQRT2 = sqrt(2.0)
    
    TERRAIN_COSTS = {
        "grass": 1.0,
        "dirt_path": 0.9,
        "cobblestone": 0.85,
        "stone_floor": 0.85,
        "wood_floor": 0.85,
        "sand": 1.2,
        "mud": 1.5,
        "shallow_water": 2.0,
        "deep_water": float("inf"),
        "wall": float("inf"),
        "door": 1.0,
    }
    
    DEFAULT_MAX_ITERATIONS = 10000
    
    # 8-directional neighbor offsets
    NEIGHBORS_8 = [
        ((1, 0), 1.0),
        ((-1, 0), 1.0),
        ((0, 1), 1.0),
        ((0, -1), 1.0),
        ((1, 1), SQRT2),
        ((-1, 1), SQRT2),
        ((1, -1), SQRT2),
        ((-1, -1), SQRT2),
    ]

## 5. Public API — methods that MUST exist

Module-level functions (no class):

    def find_path(
        start: tuple[int, int],
        goal: tuple[int, int],
        map_data: dict,
        constraints: Optional[dict] = None,
    ) -> Optional[list[tuple[int, int]]]
    
    def simplify_path(path: list[tuple[int, int]]) -> list[tuple[int, int]]
    
    def step_along_path(
        current: tuple[int, int],
        path: list[tuple[int, int]],
        distance: float,
    ) -> tuple[tuple[int, int], list[tuple[int, int]]]
    
    def is_path_blocked(path: list[tuple[int, int]], map_data: dict, constraints: Optional[dict] = None) -> bool
    
    def compute_movement_cost(
        path: list[tuple[int, int]],
        terrain_costs: Optional[dict] = None,
    ) -> float
    
    def octile_heuristic(a: tuple[int, int], b: tuple[int, int]) -> float
    
    def manhattan_heuristic(a: tuple[int, int], b: tuple[int, int]) -> int
    
    def is_walkable(
        pos: tuple[int, int],
        map_data: dict,
        constraints: Optional[dict] = None,
    ) -> bool
    
    def get_terrain_at(pos: tuple[int, int], map_data: dict) -> str
    
    def get_terrain_cost(terrain: str, terrain_costs: Optional[dict] = None) -> float
    
    def is_door_passable(
        pos: tuple[int, int],
        constraints: Optional[dict] = None,
    ) -> bool
    
    def is_creature_blocking(
        pos: tuple[int, int],
        constraints: Optional[dict] = None,
    ) -> bool
    
    def is_size_collision_free(
        top_left: tuple[int, int],
        size: int,
        map_data: dict,
        constraints: Optional[dict] = None,
    ) -> bool
    
    def reconstruct_path(came_from: dict, current: tuple[int, int]) -> list[tuple[int, int]]
    
    def get_neighbors(
        pos: tuple[int, int],
        map_data: dict,
        constraints: Optional[dict] = None,
    ) -> list[tuple[tuple[int, int], float]]
    
    def bresenham_line(
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> list[tuple[int, int]]                                                   # straight-line fallback

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** `find_path((0,0), (3,0), {...}, None)` with walkable straight line returns `[(0,0), (1,0), (2,0), (3,0)]`.

**AC-02 [FR-01]:** `find_path((0,0), (10,10), map_with_wall_between, None)` returns `None` if no path exists.

**AC-03 [FR-03]:** `get_neighbors((5,5), walkable_map, None)` returns 8 neighbors (4 straight cost 1, 4 diagonal cost √2).

**AC-04 [FR-04]:** `is_walkable((5,5), map_with_wall_at_5_5, None) == False`.

**AC-05 [FR-05]:** With a closed door at (3,3) and `passable_when_closed == False`, `is_walkable((3,3), ..., constraints) == False`.

**AC-06 [FR-06]:** With `constraints = {"block_on_creatures": True, "occupied_tiles": [(4,4)]}`, `is_walkable((4,4), ..., constraints) == False`.

**AC-07 [FR-07]:** `simplify_path([(0,0), (1,0), (2,0), (3,0)])` returns `[(0,0), (3,0)]` (all intermediate on a straight line).

**AC-08 [FR-08]:** `step_along_path((0,0), [(0,0), (1,0), (2,0)], 1.0)` returns `((1,0), [(1,0), (2,0)])`.

**AC-09 [FR-11]:** Calling `find_path` on a map larger than 10000 search iterations returns None (bailout safety).

**AC-10 [FR-12]:** With `actor_size == 2`, `is_size_collision_free((5,5), 2, map, None)` returns True only if (5,5), (6,5), (5,6), (6,6) are all walkable.

**AC-11 [reflection]:** A test MUST import the module and use `getattr` to verify every function in §5 is defined. Function name list:
`["find_path", "simplify_path", "step_along_path", "is_path_blocked", "compute_movement_cost", "octile_heuristic", "manhattan_heuristic", "is_walkable", "get_terrain_at", "get_terrain_cost", "is_door_passable", "is_creature_blocking", "is_size_collision_free", "reconstruct_path", "get_neighbors", "bresenham_line"]`

## 7. Performance Requirements

- `find_path` on 100×100 map: **< 20ms**
- `find_path` on 200×200 map: **< 100ms**
- `simplify_path` on 50-step path: **< 1ms**
- Heuristic calls: **< 0.01ms** each

## 8. Error Handling

- Start == goal: return `[start]` immediately
- Start out of bounds: return None
- Goal out of bounds: return None
- Goal not walkable: return None (cannot path TO a wall)
- Map data malformed (missing walkable_mask and terrain): assume all walkable, log at WARNING

## 9. Integration Points

**Backend (editable):**
- `frp-backend/engine/world/pathfinding.py` — NEW
- `frp-backend/engine/world/behavior_tree_leaves.py` — `GoToWaypointNode` imports `find_path`
- `frp-backend/tests/test_pathfinding.py` — NEW

**Backend (consumed, NOT modified):**
- Map data structure from `region_projection.py` — read-only

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new HTTP endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_pathfinding.py` covers AC-01..AC-11
- ≥90% branch coverage
- Includes performance benchmark tests

## 11. Verification

    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_pathfinding.py -q
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests -q

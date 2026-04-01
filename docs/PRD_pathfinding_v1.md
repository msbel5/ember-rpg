# PRD: Pathfinding System V1
**Project:** Ember RPG
**Phase:** 2
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the local-map pathfinding system synthesizing GemRB M11 (A* on search map grid, actor size, bumping, random walk, fog of war) with DF M15 (multi-z-level A*, door/ramp traversal, swim, burrow). Actors navigate 2D tile grids (settlement maps) using A* with terrain cost modifiers. Large creatures require multi-tile clearance. NPCs can bump past each other and perform random walks when idle.

## 2. Scope

### In scope
- `SearchMap`: 2D tile grid with passability flags per cell
- Passability types: impassable, normal, water, trap, underground, door (open/closed)
- A* pathfinding from source tile to target tile
- Actor size: small (1 tile), medium (1 tile), large (2x2), huge (3x3)
- Terrain cost modifiers: water = 2x, difficult terrain = 1.5x
- Path caching: cache recent paths, invalidate on map change
- Bumping: when blocked by friendly NPC, attempt to swap positions (max 16 attempts)
- Random walk: idle NPCs pick random nearby walkable tile
- Door handling: path through closed door if actor has key or strength to force
- Fog of war: actors path through unseen tiles (pathfinding ignores FoW)

### Out of scope
- Multi-level Z pathfinding (future, when multi-level maps added)
- Vehicle pathfinding
- Flying pathfinding
- World-map pathfinding (handled by Hybrid Commander PRD)

## 3. Functional Requirements (FR)

**FR-01 (SearchMap):** 2D grid of `TilePassability` values. Grid size matches settlement map (80x60 from settlement_generator). Each cell: passability flag, terrain_cost_modifier, occupant_id (or None).

**FR-02 (A* Algorithm):** Standard A* with Manhattan/diagonal heuristic. Open/closed sets. Neighbor expansion: 8 directions (cardinal + diagonal). Diagonal movement only if both adjacent cardinal cells are passable.

**FR-03 (Actor Size):** Large actors (2x2) require all 4 tiles to be passable. Huge actors (3x3) require all 9 tiles. Path segments check clearance for entire footprint.

**FR-04 (Terrain Cost):** Movement cost: normal=1.0, water=2.0, difficult=1.5, trap=1.0 (but triggers trap on entry). Diagonal movement cost = base * 1.414.

**FR-05 (Bumping):** When pathfinding finds path blocked by friendly actor, attempt bump: swap positions if partner is idle. Max 16 bump attempts before finding alternate path.

**FR-06 (Random Walk):** Idle actors with random_walk enabled pick random walkable tile within radius=10. Move there over multiple ticks at walk speed.

**FR-07 (Door Handling):** Closed doors are passable if actor has key_item or strength >= door.force_difficulty. Cost to traverse closed door = 5 (opening time). Locked doors without key: impassable.

**FR-08 (Path Result):** `find_path()` returns: list of (x, y) tiles from start to goal, total cost, success flag. If no path exists: returns ([], inf, False).

**FR-09 (Movement Execution):** Actor moves along path one tile per `movement_speed` ticks. Movement speed from actor stats: `ticks_per_tile = max(1, 10 - (AGI - 10) // 2)`. Encumbrance penalty: +1 tick per 25% encumbrance over 75%.

**FR-10 (Path Cache):** Cache last N paths per actor (default N=4). Invalidate cache when map changes (door open/close, building placed, obstacle moved).

## 4. Data Structures

```python
class TilePassability(IntEnum):
    IMPASSABLE = 0
    NORMAL = 1
    WATER = 2
    TRAP = 3
    DIFFICULT = 4
    DOOR_OPEN = 5
    DOOR_CLOSED = 6
    UNDERGROUND = 7


@dataclass
class SearchMap:
    width: int
    height: int
    tiles: list[list[TilePassability]]   # [y][x]
    occupants: dict[tuple[int, int], str]  # (x,y) → actor_id
    doors: dict[tuple[int, int], dict]     # (x,y) → {locked, key_id, force_difficulty}

    def is_passable(self, x: int, y: int, actor_size: int = 1) -> bool: ...
    def terrain_cost(self, x: int, y: int) -> float: ...
    def set_occupant(self, x: int, y: int, actor_id: str | None) -> None: ...
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchMap": ...


@dataclass
class PathResult:
    path: list[tuple[int, int]]  # Tile coordinates from start to goal
    total_cost: float
    success: bool
    tiles_explored: int = 0

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class MovementState:
    actor_id: str
    current_path: list[tuple[int, int]] = field(default_factory=list)
    path_index: int = 0
    ticks_per_tile: int = 10
    ticks_accumulated: int = 0
    moving: bool = False

    def current_tile(self) -> tuple[int, int] | None: ...
    def next_tile(self) -> tuple[int, int] | None: ...
    def is_complete(self) -> bool: ...
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MovementState": ...
```

## 5. Public API

```python
def find_path(
    search_map: SearchMap,
    start: tuple[int, int],
    goal: tuple[int, int],
    actor_size: int = 1,
    max_iterations: int = 5000,
    door_keys: set[str] | None = None,
    actor_strength: int = 10,
) -> PathResult:
    """A* pathfinding from start to goal. Returns PathResult."""

def tick_movement(
    actor: ActorRecord,
    movement: MovementState,
    search_map: SearchMap,
) -> tuple[tuple[int, int] | None, bool]:
    """Advance actor movement by one tick. Returns (new_tile_if_moved, path_complete)."""

def attempt_bump(
    actor: ActorRecord,
    blocked_tile: tuple[int, int],
    search_map: SearchMap,
    actors: dict[str, ActorRecord],
) -> bool:
    """Attempt to bump past actor at blocked_tile. Returns True if swap succeeded."""

def random_walk_target(
    actor_pos: tuple[int, int],
    search_map: SearchMap,
    radius: int = 10,
    rng: Random | None = None,
) -> tuple[int, int] | None:
    """Pick random walkable tile within radius. Returns None if none found."""

def compute_movement_speed(actor: ActorRecord, encumbrance_ratio: float) -> int:
    """Compute ticks_per_tile from AGI and encumbrance."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-02]: Given a 10x10 map with a wall from (5,0) to (5,8), pathfinding from (0,5) to (9,5) routes around the wall via (5,9).

AC-02 [FR-03]: Given a large (2x2) actor, pathfinding through a 1-tile-wide gap fails (returns success=False).

AC-03 [FR-04]: Given path through 3 water tiles and 2 normal tiles, total_cost = 3*2.0 + 2*1.0 = 8.0.

AC-04 [FR-05]: Given path blocked by friendly idle actor, bump succeeds and both actors swap tiles.

AC-05 [FR-06]: Given idle actor at (5,5), random_walk_target returns a walkable tile within radius 10.

AC-06 [FR-07]: Given closed door at (3,3) with force_difficulty=14 and actor strength=16, then door tile is passable with cost=5.

AC-07 [FR-07]: Given locked door and actor without key and strength < force_difficulty, then door tile is impassable.

AC-08 [FR-08]: Given no path exists (completely walled off), find_path returns ([], inf, False).

AC-09 [FR-09]: Given actor with AGI=14 (+2), ticks_per_tile = max(1, 10 - 2) = 8.

AC-10 [FR-02]: Given max_iterations=5000, if path requires >5000 expansions, return failure (prevents infinite search).

## 7-10. (Performance, Errors, Integration, Tests)
- find_path on 80x60 map: < 5 ms average, < 20 ms worst case
- Out of bounds coordinates: clamp to map edges
- Integration: Settlement Generator (map tiles), Actor (position, AGI), Combat (movement during engagement), Hybrid Commander (local map navigation)
- Tests: straight path, obstacle avoidance, large actor clearance, water cost, door traversal, bump swap, random walk, unreachable goal, max_iterations cutoff, serialization round-trip

# PRD: Tile Map Generator
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Implemented  

---

## 1. Purpose

The Map Generator creates procedural 2D tile-based maps for dungeons, towns, and wilderness areas. Maps are deterministic (same seed = same map), serializable, and readable by both the DM Agent (for narrative context) and the frontend renderer (for display). All room connectivity is guaranteed via BFS validation.

---

## 2. Scope

**In scope:**
- Dungeon map generation (BSP room placement + L-shaped corridors)
- Town map generation (grid streets + buildings)
- Wilderness map generation (cellular automata terrain)
- Tile type system (FLOOR, WALL, DOOR, CORRIDOR, STAIRS, WATER, TREE, ROAD)
- Room data (position, size, type, center)
- MapData serialization (to_dict, to_ascii)
- Walkability check + BFS reachability

**Out of scope:**
- Map rendering / display (→ Frontend)
- Dynamic tile updates during gameplay (→ GameEngine)
- Fog-of-war / visibility computation (→ future Phase)
- Multi-level dungeon stacking
- Pathfinding (→ AI Tactics, future)

---

## 3. Functional Requirements

**FR-01:** `DungeonGenerator.generate(width, height)` must return a `MapData` with `min 5, max 15` rooms.

**FR-02:** All dungeon rooms must be reachable from the spawn point (BFS connectivity guarantee).

**FR-03:** The spawn point must be located at the center of the entrance room, on a walkable tile.

**FR-04:** The boss room must contain a `STAIRS_DOWN` tile at its center.

**FR-05:** Two calls to any generator with the same `seed` must produce identical `to_ascii()` output (determinism).

**FR-06:** `MapData.to_dict()` must return a JSON-serializable dictionary with keys: `tiles`, `rooms`, `spawn_point`, `exit_points`, `metadata`, `width`, `height`.

**FR-07:** `TownGenerator.generate()` must produce at least 3 building rooms.

**FR-08:** `WildernessGenerator.generate()` must produce maps containing TREE tiles, WATER tiles, and at least one ROAD tile.

**FR-09:** `MapData.is_walkable(x, y)` must return True for FLOOR, CORRIDOR, DOOR, STAIRS, ROAD tiles and False for WALL, WATER, TREE, EMPTY.

**FR-10:** `Room.overlaps(other, margin)` must correctly detect spatial overlap accounting for the margin buffer.

---

## 4. Data Structures

```python
class TileType(Enum):
    FLOOR = "."       # walkable
    WALL = "#"        # blocking
    DOOR = "D"        # walkable, marks room entrance
    CORRIDOR = ","    # walkable, connects rooms
    STAIRS_DOWN = ">" # walkable, level exit
    STAIRS_UP = "<"   # walkable, level entrance
    WATER = "~"       # blocking (swim not implemented)
    TREE = "T"        # blocking
    ROAD = "="        # walkable
    EMPTY = " "       # void (out of bounds)

@dataclass
class Room:
    x: int              # top-left column
    y: int              # top-left row
    width: int          # tile count
    height: int         # tile count
    room_type: str      # "normal"|"entrance"|"boss"|"treasure"|"building"

    def center() -> (int, int)
    def inner_tiles() -> List[(int, int)]
    def overlaps(other, margin=1) -> bool

@dataclass
class MapData:
    width: int
    height: int
    tiles: List[List[TileType]]   # tiles[row][col]
    rooms: List[Room]
    spawn_point: (int, int)       # (col, row)
    exit_points: List[(int, int)]
    metadata: dict                # seed, map_type, level

    def get_tile(x, y) -> TileType
    def set_tile(x, y, tile) -> None
    def is_walkable(x, y) -> bool
    def to_ascii() -> str
    def to_dict() -> dict
    def reachable_from_spawn() -> set[(int, int)]
```

---

## 5. Public API

### `DungeonGenerator(seed=0).generate(width=50, height=30) -> MapData`
- Places 5–15 non-overlapping rectangular rooms (margin=1)
- Connects sequential room pairs with L-shaped corridors
- Assigns types: rooms[0]=entrance, rooms[-1]=boss, up to 2 middle rooms=treasure
- Places DOOR tiles at corridor–room wall intersections
- Places STAIRS_DOWN at boss room center

### `TownGenerator(seed=0).generate(width=60, height=40) -> MapData`
- Fills background with FLOOR
- Draws ROAD grid every 10 tiles
- Places buildings in grid cells; each building has WALL border + FLOOR interior
- Spawn at map center

### `WildernessGenerator(seed=0).generate(width=60, height=40) -> MapData`
- Seeds 35% of tiles as TREE randomly
- Applies 2 passes of cellular automata smoothing (≥5 tree neighbors → tree)
- Draws a horizontal ROAD at `height//2`
- Places a WATER body at `(width*3//4, height//4)` ±3 tiles

### `MapData.reachable_from_spawn() -> set`
- BFS from spawn_point; returns set of all reachable (x, y) positions

---

## 6. Acceptance Criteria

**AC-01 [FR-01]:** `DungeonGenerator(seed=42).generate(50, 30)` returns a MapData with `5 <= len(rooms) <= 15`.

**AC-02 [FR-02]:** All rooms in the generated dungeon have at least one inner tile reachable from spawn via BFS.

**AC-03 [FR-03]:** The spawn tile `map_data.get_tile(*spawn_point)` is walkable.

**AC-04 [FR-04]:** The boss room center tile is `TileType.STAIRS_DOWN`.

**AC-05 [FR-05]:** `DungeonGenerator(seed=42).generate(50,30).to_ascii() == DungeonGenerator(seed=42).generate(50,30).to_ascii()`.

**AC-06 [FR-05]:** `DungeonGenerator(seed=1).generate(50,30).to_ascii() != DungeonGenerator(seed=99).generate(50,30).to_ascii()`.

**AC-07 [FR-06]:** `json.dumps(map_data.to_dict())` succeeds without TypeError.

**AC-08 [FR-07]:** `TownGenerator(seed=42).generate(60,40)` returns MapData with `len(rooms) >= 3`.

**AC-09 [FR-08]:** `WildernessGenerator(seed=42).generate(40,30)` — `to_ascii()` contains "T", "~", and "=".

**AC-10 [FR-09]:** `is_walkable` returns True for FLOOR/CORRIDOR/DOOR/STAIRS/ROAD and False for WALL/WATER/TREE.

**AC-11 [FR-10]:** `Room(0,0,5,5).overlaps(Room(6,0,5,5), margin=1)` is True; `margin=0` is False.

**AC-12:** `MapData.get_tile(x,y)` returns `TileType.WALL` for out-of-bounds coordinates.

**AC-13:** Dungeon `metadata["seed"]` matches the generator's seed value.

---

## 7. Performance Requirements

- `DungeonGenerator.generate(80, 50)`: < 50ms
- `TownGenerator.generate(60, 40)`: < 20ms
- `WildernessGenerator.generate(60, 40)`: < 20ms
- `to_ascii()` on 80x50 map: < 5ms

---

## 8. Error Handling

- Width or height < 10: generator may produce maps with fewer than MIN_ROOMS (no exception; degenerate output acceptable)
- `get_tile` / `set_tile` with out-of-bounds coords: silently return WALL / no-op
- All room placement failures after MAX_ATTEMPTS: return map with however many rooms were placed (minimum 1 — the first room always succeeds)

---

## 9. Integration Points

- **Upstream:** `GameEngine.new_session()` calls `DungeonGenerator` to produce the starting map
- **Downstream:** `DMContext.location` is set from map metadata; future Frontend renders `to_dict()` tiles
- **API:** `GET /game/session/{id}/map` returns `map_data.to_dict()`

---

## 10. Test Coverage Target

- Minimum: **95%** on `engine/map/__init__.py`
- Must test: all 3 generators, determinism, connectivity (BFS), tile walkability, serialization, Room overlap

---

## Changelog

- 2026-03-23: Rewritten to PRD standard (post-implementation)

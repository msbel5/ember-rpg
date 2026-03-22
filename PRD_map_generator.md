# PRD: Phase 4 — Tile Map Generator
**Project:** Ember RPG  
**Phase:** 4  
**Date:** 2026-03-23  

---

## 1. Goal

Prosedürel olarak üretilebilen 2D tile tabanlı haritalar.  
Her dungeon, şehir veya açık alan haritası farklı seed ile üretilir.  
DM Agent harita verisini okur, narrative üretmek için kullanır.

---

## 2. Map Types

| Type | Description |
|------|-------------|
| DUNGEON | Odalar + koridorlar, Boss room, secrets |
| TOWN | Sokaklar, meyhaneler, dükkanlar, NPC spawn |
| WILDERNESS | Orman, dağ, nehir, açık alan encounters |

---

## 3. Tile System

```python
class TileType(Enum):
    FLOOR = "."
    WALL = "#"
    DOOR = "D"
    CORRIDOR = ","
    STAIRS_DOWN = ">"
    STAIRS_UP = "<"
    WATER = "~"
    TREE = "T"
    ROAD = "="
    EMPTY = " "
```

---

## 4. Map Data Structure

```python
@dataclass
class Room:
    x: int           # top-left corner
    y: int
    width: int
    height: int
    room_type: str   # "normal", "boss", "treasure", "entrance"
    
@dataclass  
class MapData:
    width: int
    height: int
    tiles: List[List[TileType]]
    rooms: List[Room]
    spawn_point: tuple[int, int]
    exit_points: List[tuple[int, int]]
    metadata: dict   # seed, map_type, level, etc.
    
    def get_tile(x, y) -> TileType
    def set_tile(x, y, tile) -> None
    def is_walkable(x, y) -> bool
    def to_dict() -> dict    # For API serialization
    def to_ascii() -> str    # For debugging / DM context
```

---

## 5. Generators

### DungeonGenerator
- BSP (Binary Space Partitioning) room placement
- Min 5, max 15 rooms
- Corridor connection (L-shaped tunnels)
- Special rooms: entrance (1), boss (1), treasure (0-2)
- Door placement on room entrances

### TownGenerator  
- Grid-based street layout
- Building placement (inn, shop, blacksmith, temple)
- Town square center

### WildernessGenerator
- Noise-based terrain (simplified cellular automata)
- Forest clusters, water bodies, road paths

---

## 6. Test Cases

### TC1: Dungeon Generation
```python
gen = DungeonGenerator(seed=42)
map_data = gen.generate(width=50, height=30)
assert map_data.width == 50
assert 5 <= len(map_data.rooms) <= 15
assert map_data.spawn_point is not None
```

### TC2: Deterministic Output (same seed = same map)
```python
map1 = DungeonGenerator(seed=42).generate(50, 30)
map2 = DungeonGenerator(seed=42).generate(50, 30)
assert map1.to_ascii() == map2.to_ascii()
```

### TC3: Room Connectivity
```python
map_data = DungeonGenerator(seed=42).generate(50, 30)
# All rooms must be reachable from spawn
assert all_rooms_connected(map_data)
```

### TC4: Walkable Tiles
```python
map_data = DungeonGenerator(seed=42).generate(50, 30)
sx, sy = map_data.spawn_point
assert map_data.is_walkable(sx, sy)
```

### TC5: Town Generation
```python
gen = TownGenerator(seed=42)
map_data = gen.generate(60, 40)
assert map_data.width == 60
assert len(map_data.rooms) >= 3  # min buildings
```

### TC6: ASCII Representation
```python
map_data = DungeonGenerator(seed=42).generate(20, 15)
ascii_str = map_data.to_ascii()
assert "#" in ascii_str   # walls
assert "." in ascii_str   # floors
```

### TC7: Map Serialization
```python
map_data = DungeonGenerator(seed=42).generate(20, 15)
d = map_data.to_dict()
assert "tiles" in d
assert "rooms" in d
assert "spawn_point" in d
```

### TC8: Wilderness Generation
```python
gen = WildernessGenerator(seed=42)
map_data = gen.generate(40, 30)
assert map_data.width == 40
assert map_data.spawn_point is not None
```

---

## 7. API Integration

```
GET /game/session/{id}/map          → Current map ASCII + metadata
POST /game/session/{id}/map/new     → Generate new map (type, seed)
GET /game/session/{id}/map/rooms    → Room list with descriptions
```

---

## 8. Success Metrics
- [ ] Dungeon generation < 50ms for 80x50 map
- [ ] 95%+ test coverage
- [ ] Deterministic (seed-based)
- [ ] All rooms connected (BFS reachability check)
- [ ] API endpoints working

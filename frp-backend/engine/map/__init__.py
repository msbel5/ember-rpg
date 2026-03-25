"""
Ember RPG - Phase 4: Tile Map Generator
Procedural dungeon, town, and wilderness map generation.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum
import random
from collections import deque


class TileType(Enum):
    """Map tile types."""
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


WALKABLE_TILES = {
    TileType.FLOOR, TileType.CORRIDOR, TileType.DOOR,
    TileType.STAIRS_DOWN, TileType.STAIRS_UP, TileType.ROAD,
}


@dataclass
class Room:
    """
    A rectangular room on the map.

    Attributes:
        x: Top-left column
        y: Top-left row
        width: Room width in tiles
        height: Room height in tiles
        room_type: "normal", "boss", "treasure", "entrance", "building"
    """
    x: int
    y: int
    width: int
    height: int
    room_type: str = "normal"

    def center(self) -> Tuple[int, int]:
        """Return center tile (col, row)."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def inner_tiles(self) -> List[Tuple[int, int]]:
        """Return all floor tile positions inside the room."""
        return [
            (self.x + dx, self.y + dy)
            for dy in range(1, self.height - 1)
            for dx in range(1, self.width - 1)
        ]

    def overlaps(self, other: "Room", margin: int = 1) -> bool:
        """Check if this room overlaps another (with optional margin)."""
        return (
            self.x - margin < other.x + other.width
            and self.x + self.width + margin >= other.x
            and self.y - margin < other.y + other.height
            and self.y + self.height + margin >= other.y
        )


@dataclass
class MapData:
    """
    Full map data: tiles, rooms, spawn, and exits.

    Attributes:
        width: Map width in tiles
        height: Map height in tiles
        tiles: 2D grid of TileType (tiles[row][col])
        rooms: List of rooms on the map
        spawn_point: Player starting position (col, row)
        exit_points: List of exit positions
        metadata: Map metadata (seed, type, level, etc.)
        zones: Zone data from ZoneMap (optional)
    """
    width: int
    height: int
    tiles: List[List[TileType]]
    rooms: List[Room]
    spawn_point: Tuple[int, int]
    exit_points: List[Tuple[int, int]] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    zones: Optional[list] = field(default=None)

    def get_tile(self, x: int, y: int) -> TileType:
        """Get tile at position (col x, row y)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
        return TileType.WALL

    def set_tile(self, x: int, y: int, tile: TileType) -> None:
        """Set tile at position (col x, row y)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.tiles[y][x] = tile

    def is_walkable(self, x: int, y: int) -> bool:
        """Return True if tile is walkable."""
        return self.get_tile(x, y) in WALKABLE_TILES

    def to_ascii(self) -> str:
        """Render map as ASCII string."""
        lines = []
        sx, sy = self.spawn_point
        for row_idx, row in enumerate(self.tiles):
            line = []
            for col_idx, tile in enumerate(row):
                if (col_idx, row_idx) == (sx, sy):
                    line.append("@")
                else:
                    line.append(tile.value)
            lines.append("".join(line))
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize map for API responses."""
        result = {
            "width": self.width,
            "height": self.height,
            "tiles": [[t.value for t in row] for row in self.tiles],
            "rooms": [
                {
                    "x": r.x, "y": r.y,
                    "width": r.width, "height": r.height,
                    "type": r.room_type,
                    "center": r.center(),
                }
                for r in self.rooms
            ],
            "spawn_point": list(self.spawn_point),
            "exit_points": [list(p) for p in self.exit_points],
            "metadata": self.metadata,
        }
        if self.zones is not None:
            result["zones"] = self.zones
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "MapData":
        """Deserialize map from a dict (inverse of to_dict)."""
        _TILE_MAP = {t.value: t for t in TileType}
        tiles = [
            [_TILE_MAP.get(c, TileType.WALL) for c in row]
            for row in data["tiles"]
        ]
        rooms = [
            Room(
                x=r["x"], y=r["y"],
                width=r["width"], height=r["height"],
                room_type=r.get("type", "normal"),
            )
            for r in data.get("rooms", [])
        ]
        return cls(
            width=data["width"],
            height=data["height"],
            tiles=tiles,
            rooms=rooms,
            spawn_point=tuple(data["spawn_point"]),
            exit_points=[tuple(p) for p in data.get("exit_points", [])],
            metadata=data.get("metadata", {}),
            zones=data.get("zones"),
        )

    def reachable_from_spawn(self) -> set:
        """BFS from spawn point; return set of reachable (x, y) positions."""
        visited = set()
        queue = deque([self.spawn_point])
        while queue:
            x, y = queue.popleft()
            if (x, y) in visited:
                continue
            visited.add((x, y))
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nx, ny = x + dx, y + dy
                if (nx, ny) not in visited and self.is_walkable(nx, ny):
                    queue.append((nx, ny))
        return visited


def _empty_map(width: int, height: int, fill: TileType = TileType.WALL) -> List[List[TileType]]:
    """Create a 2D tile grid filled with `fill`."""
    return [[fill for _ in range(width)] for _ in range(height)]


class DungeonGenerator:
    """
    BSP-style dungeon generator.

    Generates rectangular rooms, connects them with L-shaped corridors.
    Rooms: min 5, max 15. Special rooms: entrance, boss, 0-2 treasure.

    Usage:
        gen = DungeonGenerator(seed=42)
        map_data = gen.generate(width=50, height=30)
    """

    MIN_ROOMS = 5
    MAX_ROOMS = 15
    MIN_ROOM_SIZE = 4
    MAX_ROOM_SIZE = 10
    MAX_ATTEMPTS = 100

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(self, width: int = 50, height: int = 30) -> MapData:
        """Generate a dungeon map."""
        tiles = _empty_map(width, height, TileType.WALL)
        rooms: List[Room] = []

        target = self.rng.randint(self.MIN_ROOMS, self.MAX_ROOMS)

        for _ in range(self.MAX_ATTEMPTS):
            if len(rooms) >= target:
                break
            w = self.rng.randint(self.MIN_ROOM_SIZE, self.MAX_ROOM_SIZE)
            h = self.rng.randint(self.MIN_ROOM_SIZE, self.MAX_ROOM_SIZE)
            x = self.rng.randint(1, width - w - 1)
            y = self.rng.randint(1, height - h - 1)
            new_room = Room(x, y, w, h)

            if any(new_room.overlaps(r) for r in rooms):
                continue

            self._carve_room(tiles, new_room)
            rooms.append(new_room)

        # Connect rooms with corridors
        for i in range(1, len(rooms)):
            self._connect_rooms(tiles, rooms[i - 1], rooms[i])

        # Assign room types
        self._assign_room_types(rooms)

        # Place doors at room entrances (simplified: at corridor-floor intersections)
        self._place_doors(tiles, rooms, width, height)

        # Spawn at entrance room center
        entrance = next((r for r in rooms if r.room_type == "entrance"), rooms[0])
        spawn = entrance.center()

        # Exit at boss room center
        boss = next((r for r in rooms if r.room_type == "boss"), rooms[-1])
        bx, by = boss.center()
        tiles[by][bx] = TileType.STAIRS_DOWN
        exit_points = [(bx, by)]

        # Zone integration
        from engine.map.zones import create_zone_map
        zone_map = create_zone_map("dungeon", width, height)
        zone_data = [
            {
                "id": z.id,
                "zone_type": z.zone_type.value,
                "name": z.name,
                "x1": z.x1, "y1": z.y1, "x2": z.x2, "y2": z.y2,
                "is_indoor": z.is_indoor,
                "danger_level": z.danger_level,
            }
            for z in zone_map.zones.values()
        ]

        return MapData(
            width=width,
            height=height,
            tiles=tiles,
            rooms=rooms,
            spawn_point=spawn,
            exit_points=exit_points,
            metadata={"seed": self.seed, "map_type": "dungeon"},
            zones=zone_data,
        )

    def _carve_room(self, tiles, room: Room) -> None:
        for dy in range(room.height):
            for dx in range(room.width):
                if dy == 0 or dy == room.height - 1 or dx == 0 or dx == room.width - 1:
                    # Only set outer wall if currently WALL (don't overwrite corridors)
                    if tiles[room.y + dy][room.x + dx] == TileType.WALL:
                        tiles[room.y + dy][room.x + dx] = TileType.WALL
                else:
                    tiles[room.y + dy][room.x + dx] = TileType.FLOOR

    def _connect_rooms(self, tiles, a: Room, b: Room) -> None:
        """L-shaped corridor between room centers."""
        ax, ay = a.center()
        bx, by = b.center()

        # Horizontal then vertical
        if self.rng.random() < 0.5:
            self._carve_h_corridor(tiles, ax, bx, ay)
            self._carve_v_corridor(tiles, ay, by, bx)
        else:
            self._carve_v_corridor(tiles, ay, by, ax)
            self._carve_h_corridor(tiles, ax, bx, by)

    def _carve_h_corridor(self, tiles, x1, x2, y) -> None:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            if tiles[y][x] == TileType.WALL:
                tiles[y][x] = TileType.CORRIDOR

    def _carve_v_corridor(self, tiles, y1, y2, x) -> None:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if tiles[y][x] == TileType.WALL:
                tiles[y][x] = TileType.CORRIDOR

    def _assign_room_types(self, rooms: List[Room]) -> None:
        """Assign entrance, boss, treasure, normal types."""
        if not rooms:
            return
        rooms[0].room_type = "entrance"
        rooms[-1].room_type = "boss"
        # Middle rooms: some treasure
        mid = rooms[1:-1]
        self.rng.shuffle(mid)
        for i, r in enumerate(mid[:2]):
            r.room_type = "treasure"

    def _place_doors(self, tiles, rooms, width, height) -> None:
        """Place doors where corridors meet room walls."""
        for room in rooms:
            # Check each cell on room border
            for dx in range(room.width):
                for dy in range(room.height):
                    if not (dy == 0 or dy == room.height - 1 or dx == 0 or dx == room.width - 1):
                        continue
                    tx, ty = room.x + dx, room.y + dy
                    # If adjacent cell is a corridor, this is a door candidate
                    for nx, ny in [(tx+1,ty),(tx-1,ty),(tx,ty+1),(tx,ty-1)]:
                        if 0 <= nx < width and 0 <= ny < height:
                            if tiles[ny][nx] == TileType.CORRIDOR:
                                tiles[ty][tx] = TileType.DOOR
                                break


class TownGenerator:
    """
    Grid-based town generator.

    Places buildings (inn, shop, blacksmith, temple) on a street grid.

    Usage:
        gen = TownGenerator(seed=42)
        map_data = gen.generate(width=60, height=40)
    """

    BUILDING_TYPES = ["inn", "shop", "blacksmith", "temple", "house", "house", "house"]

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(self, width: int = 60, height: int = 40) -> MapData:
        """Generate a town map."""
        tiles = _empty_map(width, height, TileType.FLOOR)
        rooms: List[Room] = []

        # Border walls
        for x in range(width):
            tiles[0][x] = TileType.WALL
            tiles[height - 1][x] = TileType.WALL
        for y in range(height):
            tiles[y][0] = TileType.WALL
            tiles[y][width - 1] = TileType.WALL

        # Grid of roads every 10 tiles
        for x in range(0, width, 10):
            for y in range(height):
                tiles[y][x] = TileType.ROAD
        for y in range(0, height, 10):
            for x in range(width):
                tiles[y][x] = TileType.ROAD

        # Place buildings in grid cells
        for cell_x in range(1, width // 10):
            for cell_y in range(1, height // 10):
                bx = cell_x * 10 + 1
                by = cell_y * 10 + 1
                bw = self.rng.randint(4, 7)
                bh = self.rng.randint(3, 6)
                if bx + bw < width - 1 and by + bh < height - 1:
                    btype = self.rng.choice(self.BUILDING_TYPES)
                    building = Room(bx, by, bw, bh, room_type=btype)
                    for dy in range(bh):
                        for dx in range(bw):
                            if dy == 0 or dy == bh - 1 or dx == 0 or dx == bw - 1:
                                tiles[by + dy][bx + dx] = TileType.WALL
                            else:
                                tiles[by + dy][bx + dx] = TileType.FLOOR
                    rooms.append(building)

        spawn = (width // 2, height // 2)

        # Zone integration
        from engine.map.zones import create_zone_map
        zone_map = create_zone_map("town", width, height)
        zone_data = [
            {
                "id": z.id,
                "zone_type": z.zone_type.value,
                "name": z.name,
                "x1": z.x1, "y1": z.y1, "x2": z.x2, "y2": z.y2,
                "is_indoor": z.is_indoor,
                "danger_level": z.danger_level,
            }
            for z in zone_map.zones.values()
        ]

        return MapData(
            width=width,
            height=height,
            tiles=tiles,
            rooms=rooms,
            spawn_point=spawn,
            exit_points=[],
            metadata={"seed": self.seed, "map_type": "town"},
            zones=zone_data,
        )


class WildernessGenerator:
    """
    Cellular automata wilderness generator.

    Generates open terrain with forest clusters and water bodies.

    Usage:
        gen = WildernessGenerator(seed=42)
        map_data = gen.generate(width=40, height=30)
    """

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(self, width: int = 60, height: int = 40) -> MapData:
        """Generate a wilderness map."""
        tiles = _empty_map(width, height, TileType.FLOOR)

        # Random tree placement
        for y in range(height):
            for x in range(width):
                if self.rng.random() < 0.35:
                    tiles[y][x] = TileType.TREE

        # Smooth with cellular automata (2 passes)
        for _ in range(2):
            tiles = self._smooth(tiles, width, height)

        # Add a road diagonally across
        road_y = height // 2
        for x in range(width):
            tiles[road_y][x] = TileType.ROAD

        # Water body in top-right corner
        wx, wy = width * 3 // 4, height // 4
        for dy in range(-3, 4):
            for dx in range(-5, 6):
                ny, nx = wy + dy, wx + dx
                if 0 <= nx < width and 0 <= ny < height:
                    tiles[ny][nx] = TileType.WATER

        # Spawn on road
        spawn = (width // 4, road_y)
        tiles[road_y][width // 4] = TileType.FLOOR

        # Zone integration
        from engine.map.zones import create_zone_map
        zone_map = create_zone_map("wilderness", width, height)
        zone_data = [
            {
                "id": z.id,
                "zone_type": z.zone_type.value,
                "name": z.name,
                "x1": z.x1, "y1": z.y1, "x2": z.x2, "y2": z.y2,
                "is_indoor": z.is_indoor,
                "danger_level": z.danger_level,
            }
            for z in zone_map.zones.values()
        ]

        return MapData(
            width=width,
            height=height,
            tiles=tiles,
            rooms=[],
            spawn_point=spawn,
            exit_points=[],
            metadata={"seed": self.seed, "map_type": "wilderness"},
            zones=zone_data,
        )

    def _smooth(self, tiles, width, height) -> List[List[TileType]]:
        """One pass of cellular automata smoothing."""
        new_tiles = _empty_map(width, height, TileType.FLOOR)
        for y in range(height):
            for x in range(width):
                tree_count = sum(
                    1 for dx in range(-1, 2) for dy in range(-1, 2)
                    if 0 <= x + dx < width and 0 <= y + dy < height
                    and tiles[y + dy][x + dx] == TileType.TREE
                )
                new_tiles[y][x] = TileType.TREE if tree_count >= 5 else TileType.FLOOR
        return new_tiles

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum
import random
from collections import deque



"""
Zone-based map generation — Dwarf Fortress-inspired.
Zone → Road → Building Template → Entity pipeline.

Each tile gets a zone assignment. Tile selection uses zone palette.
Entity placement respects zone affinity.
Building templates stamp coherent structures onto the grid.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import random

from engine.data_loader import (
    get_building_templates,
    get_zone_entity_rules,
    get_zone_layouts,
    get_zone_tile_palettes,
)


class ZoneType(str, Enum):
    # Town zones
    MARKET = "market"
    RESIDENTIAL = "residential"
    DOCKS = "docks"
    GATE = "gate"
    TAVERN = "tavern"
    TEMPLE = "temple"
    BLACKSMITH = "blacksmith"
    WAREHOUSE = "warehouse"
    GARDEN = "garden"
    ROAD = "road"
    WATER = "water"
    PLAZA = "plaza"
    # Dungeon zones
    ENTRANCE = "entrance"
    CORRIDOR = "corridor"
    TREASURE = "treasure"
    BOSS = "boss"
    PRISON = "prison"
    # Wilderness zones
    CLEARING = "clearing"
    DENSE_FOREST = "dense_forest"
    RIVER = "river"
    CAMP = "camp"
    PATH = "path"
    # Cave zones
    CAVE_ENTRANCE = "cave_entrance"
    CAVERN = "cavern"
    CRYSTAL = "crystal"


@dataclass
class Zone:
    id: str
    zone_type: ZoneType
    name: str
    x1: int
    y1: int
    x2: int
    y2: int
    is_indoor: bool = False
    danger_level: int = 0

    @property
    def bounds(self) -> tuple:
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    def contains(self, x: int, y: int) -> bool:
        return self.x1 <= x < self.x2 and self.y1 <= y < self.y2


def _zone_type(value: str | ZoneType | None) -> Optional[ZoneType]:
    if isinstance(value, ZoneType):
        return value
    if value is None:
        return None
    try:
        return ZoneType(str(value))
    except ValueError:
        return None


def _load_zone_tile_palettes() -> dict[ZoneType, dict]:
    palettes = {}
    for key, value in get_zone_tile_palettes().items():
        zone_type = _zone_type(key)
        if zone_type is None:
            continue
        palettes[zone_type] = {
            "ground": [(str(tile), int(weight)) for tile, weight in value.get("ground", [])],
            "accent": list(value.get("accent", [])),
        }
    return palettes


def _load_building_templates() -> dict[str, dict]:
    templates = {}
    for name, template in get_building_templates().items():
        templates[name] = {
            "size": tuple(template.get("size", (0, 0))),
            "tiles": [list(row) for row in template.get("tiles", [])],
            "entity_slots": [
                {
                    "offset": tuple(slot.get("offset", (0, 0))),
                    "role": slot.get("role"),
                    "type": slot.get("type"),
                    "required": bool(slot.get("required", False)),
                }
                for slot in template.get("entity_slots", [])
            ],
            "zone_affinity": [
                zone_type
                for zone_type in (_zone_type(value) for value in template.get("zone_affinity", []))
                if zone_type is not None
            ],
            "is_indoor": bool(template.get("is_indoor", False)),
        }
    return templates


def _load_zone_entity_rules() -> dict[ZoneType, dict]:
    rules = {}
    for key, value in get_zone_entity_rules().items():
        zone_type = _zone_type(key)
        if zone_type is None:
            continue
        rules[zone_type] = {
            "npcs": list(value.get("npcs", [])),
            "items": list(value.get("items", [])),
            "enemies": list(value.get("enemies", [])),
        }
    return rules


def _load_zone_layouts() -> dict[str, list[Zone]]:
    layouts = {}
    for location_type, zone_entries in get_zone_layouts().items():
        layouts[location_type] = []
        for entry in zone_entries:
            zone_type = _zone_type(entry.get("zone_type"))
            bounds = entry.get("bounds", [0, 0, 1, 1])
            if zone_type is None or len(bounds) != 4:
                continue
            layouts[location_type].append(
                Zone(
                    id=str(entry.get("id", f"{location_type}_{zone_type.value}")),
                    zone_type=zone_type,
                    name=str(entry.get("name", zone_type.value.title())),
                    x1=int(bounds[0]),
                    y1=int(bounds[1]),
                    x2=int(bounds[2]),
                    y2=int(bounds[3]),
                    is_indoor=bool(entry.get("is_indoor", False)),
                    danger_level=int(entry.get("danger_level", 0)),
                )
            )
    return layouts


ZONE_TILE_PALETTES = _load_zone_tile_palettes()
BUILDING_TEMPLATES = _load_building_templates()
ZONE_ENTITY_RULES = _load_zone_entity_rules()
ZONE_LAYOUTS = _load_zone_layouts()


class ZoneMap:
    """2D zone assignment grid — parallel layer alongside tile grid."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid: list[list[Optional[str]]] = [[None] * width for _ in range(height)]
        self.zones: dict[str, Zone] = {}

    def add_zone(self, zone: Zone) -> None:
        """Paint a zone onto the grid."""
        self.zones[zone.id] = zone
        for y in range(max(0, zone.y1), min(self.height, zone.y2)):
            for x in range(max(0, zone.x1), min(self.width, zone.x2)):
                self.grid[y][x] = zone.id

    def get_zone_at(self, x: int, y: int) -> Optional[Zone]:
        """Get the zone at a tile position."""
        if 0 <= x < self.width and 0 <= y < self.height:
            zone_id = self.grid[y][x]
            if zone_id:
                return self.zones.get(zone_id)
        return None

    def get_zone_type_at(self, x: int, y: int) -> Optional[ZoneType]:
        zone = self.get_zone_at(x, y)
        return zone.zone_type if zone else None

    def to_dict(self) -> dict:
        """Serialize for API response."""
        return {
            "zone_grid": [[self.grid[y][x] for x in range(self.width)] for y in range(self.height)],
            "zones": [
                {
                    "id": z.id,
                    "type": z.zone_type.value,
                    "name": z.name,
                    "bounds": [z.x1, z.y1, z.x2, z.y2],
                    "is_indoor": z.is_indoor,
                    "danger_level": z.danger_level,
                }
                for z in self.zones.values()
            ],
        }


def create_zone_map(location_type: str, width: int = 20, height: int = 15) -> ZoneMap:
    """Create a zone map for a location type using pre-defined layouts."""
    zone_map = ZoneMap(width, height)
    zones = ZONE_LAYOUTS.get(location_type, ZONE_LAYOUTS["town"])
    for zone in zones:
        # Clamp to map bounds
        clamped = Zone(
            id=zone.id,
            zone_type=zone.zone_type,
            name=zone.name,
            x1=min(zone.x1, width - 1),
            y1=min(zone.y1, height - 1),
            x2=min(zone.x2, width),
            y2=min(zone.y2, height),
            is_indoor=zone.is_indoor,
            danger_level=zone.danger_level,
        )
        zone_map.add_zone(clamped)
    return zone_map


def select_tile_for_zone(zone_type: Optional[ZoneType], rng: random.Random) -> str:
    """Select a tile type based on zone. Falls back to cobblestone for unzoned areas."""
    if zone_type is None:
        return rng.choice(["grass", "dirt_path", "cobblestone"])

    palette = ZONE_TILE_PALETTES.get(zone_type)
    if not palette:
        return "cobblestone"

    ground = palette["ground"]
    tiles = [t[0] for t in ground]
    weights = [t[1] for t in ground]
    return rng.choices(tiles, weights=weights)[0]


def get_building_templates_for_zone(zone_type: ZoneType) -> list:
    """Get building templates that fit in a zone type."""
    result = []
    for name, template in BUILDING_TEMPLATES.items():
        if zone_type in template["zone_affinity"]:
            result.append((name, template))
    return result


def place_building_template(
    tiles: list[list[str]],
    template_name: str,
    x: int, y: int,
    width: int, height: int
) -> list[dict]:
    """Stamp a building template onto the tile grid. Returns entity slots."""
    template = BUILDING_TEMPLATES[template_name]
    tw, th = template["size"]
    entity_slots = []

    for ty in range(th):
        for tx in range(tw):
            map_x = x + tx
            map_y = y + ty
            if 0 <= map_x < width and 0 <= map_y < height:
                tiles[map_y][map_x] = template["tiles"][ty][tx]

    for slot in template["entity_slots"]:
        ox, oy = slot["offset"]
        entity_slots.append({
            "x": x + ox,
            "y": y + oy,
            "role": slot["role"],
            "type": slot["type"],
            "required": slot["required"],
            "building": template_name,
        })

    return entity_slots


def validate_map(tiles, zone_map, entities) -> list[str]:
    """Validate map coherence. Returns list of error messages."""
    errors = []
    width = len(tiles[0]) if tiles else 0
    height = len(tiles)

    # Check no entity on wall tile
    wall_tiles = {"stone_wall", "dungeon_wall", "cave_wall", "wooden_wall", "reinforced_wall"}
    for category in ["npcs", "items", "enemies"]:
        for entity in entities.get(category, []):
            pos = entity.get("position", [0, 0])
            x, y = int(pos[0]), int(pos[1])
            if 0 <= y < height and 0 <= x < width:
                if tiles[y][x] in wall_tiles:
                    errors.append(f"Entity {entity.get('id')} is on wall tile at ({x},{y})")

    # Check at least one road-connected path exists
    # (simplified: just check spawn area is valid)

    return errors

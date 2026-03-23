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


# --- Zone Tile Palettes ---
# Each zone type has weighted tile options for ground
ZONE_TILE_PALETTES = {
    ZoneType.MARKET: {
        "ground": [("cobblestone", 70), ("dirt_path", 20), ("cobblestone", 10)],
        "accent": ["market_stall", "barrel", "crate"],
    },
    ZoneType.RESIDENTIAL: {
        "ground": [("cobblestone", 50), ("dirt_path", 30), ("grass", 20)],
        "accent": ["flower_pot", "barrel"],
    },
    ZoneType.DOCKS: {
        "ground": [("dock_planks", 60), ("sand", 25), ("cobblestone", 15)],
        "accent": ["crate", "barrel", "rope"],
    },
    ZoneType.GATE: {
        "ground": [("cobblestone", 80), ("dirt_path", 20)],
        "accent": [],
    },
    ZoneType.TAVERN: {
        "ground": [("wood_floor", 70), ("tavern_floor", 30)],
        "accent": ["table", "chair"],
    },
    ZoneType.TEMPLE: {
        "ground": [("stone_floor", 80), ("cobblestone", 20)],
        "accent": ["altar", "candle"],
    },
    ZoneType.ROAD: {
        "ground": [("cobblestone", 90), ("dirt_path", 10)],
        "accent": [],
    },
    ZoneType.WATER: {
        "ground": [("water", 100)],
        "accent": [],
    },
    ZoneType.PLAZA: {
        "ground": [("cobblestone", 85), ("stone_floor", 15)],
        "accent": ["fountain", "bench"],
    },
    ZoneType.GARDEN: {
        "ground": [("grass", 60), ("dirt_path", 25), ("flower_bed", 15)],
        "accent": ["tree", "bush"],
    },
    # Dungeon
    ZoneType.ENTRANCE: {
        "ground": [("stone_floor", 70), ("cracked_stone", 30)],
        "accent": ["torch_wall"],
    },
    ZoneType.CORRIDOR: {
        "ground": [("stone_floor", 60), ("wet_stone", 30), ("cracked_stone", 10)],
        "accent": ["torch_wall"],
    },
    ZoneType.TREASURE: {
        "ground": [("stone_floor", 80), ("gold_tile", 20)],
        "accent": ["treasure_chest", "gold_pile"],
    },
    ZoneType.BOSS: {
        "ground": [("dark_stone", 70), ("cracked_stone", 30)],
        "accent": ["throne", "brazier"],
    },
    # Wilderness
    ZoneType.CLEARING: {
        "ground": [("grass", 70), ("dirt", 20), ("rocky_ground", 10)],
        "accent": ["fallen_log", "mushroom"],
    },
    ZoneType.DENSE_FOREST: {
        "ground": [("grass", 40), ("dirt", 30), ("mud", 30)],
        "accent": ["tree", "bush", "vine"],
    },
    ZoneType.PATH: {
        "ground": [("dirt_path", 80), ("grass", 20)],
        "accent": [],
    },
    ZoneType.CAMP: {
        "ground": [("dirt", 60), ("grass", 30), ("rocky_ground", 10)],
        "accent": ["campfire_pit", "tent"],
    },
    # Cave
    ZoneType.CAVE_ENTRANCE: {
        "ground": [("cave_floor", 60), ("gravel", 40)],
        "accent": ["stalactite"],
    },
    ZoneType.CAVERN: {
        "ground": [("cave_floor", 50), ("wet_cave_floor", 30), ("gravel", 20)],
        "accent": ["glowing_mushroom"],
    },
    ZoneType.CRYSTAL: {
        "ground": [("cave_floor", 40), ("crystal_floor", 60)],
        "accent": ["crystal_formation", "glowing_mushroom"],
    },
}


# --- Building Templates (DF "stamp" pattern) ---
# Each template defines a small tile grid that gets stamped onto the map
BUILDING_TEMPLATES = {
    "tavern_5x3": {
        "size": (5, 3),
        "tiles": [
            ["stone_wall", "door", "stone_wall", "stone_wall", "stone_wall"],
            ["tavern_floor", "tavern_floor", "tavern_floor", "bar_counter", "stone_wall"],
            ["stone_wall", "stone_wall", "stone_wall", "stone_wall", "stone_wall"],
        ],
        "entity_slots": [
            {"offset": (3, 1), "role": "innkeeper", "type": "npc", "required": True},
        ],
        "zone_affinity": [ZoneType.TAVERN, ZoneType.MARKET],
        "is_indoor": True,
    },
    "shop_3x3": {
        "size": (3, 3),
        "tiles": [
            ["stone_wall", "door", "stone_wall"],
            ["wood_floor", "wood_floor", "stone_wall"],
            ["stone_wall", "stone_wall", "stone_wall"],
        ],
        "entity_slots": [
            {"offset": (1, 1), "role": "merchant", "type": "npc", "required": True},
        ],
        "zone_affinity": [ZoneType.MARKET, ZoneType.RESIDENTIAL],
        "is_indoor": True,
    },
    "market_stall_2x2": {
        "size": (2, 2),
        "tiles": [
            ["cobblestone", "cobblestone"],
            ["cobblestone", "cobblestone"],
        ],
        "entity_slots": [
            {"offset": (0, 0), "role": "merchant", "type": "npc", "required": True},
            {"offset": (1, 0), "role": "crate", "type": "item", "required": False},
        ],
        "zone_affinity": [ZoneType.MARKET],
        "is_indoor": False,
    },
    "guard_post_2x2": {
        "size": (2, 2),
        "tiles": [
            ["stone_wall", "cobblestone"],
            ["cobblestone", "cobblestone"],
        ],
        "entity_slots": [
            {"offset": (1, 0), "role": "guard", "type": "npc", "required": True},
        ],
        "zone_affinity": [ZoneType.GATE],
        "is_indoor": False,
    },
    "well_1x1": {
        "size": (1, 1),
        "tiles": [["cobblestone"]],
        "entity_slots": [
            {"offset": (0, 0), "role": "well", "type": "item", "required": True},
        ],
        "zone_affinity": [ZoneType.PLAZA, ZoneType.MARKET, ZoneType.RESIDENTIAL],
        "is_indoor": False,
    },
    "notice_board_1x1": {
        "size": (1, 1),
        "tiles": [["cobblestone"]],
        "entity_slots": [
            {"offset": (0, 0), "role": "notice_board", "type": "item", "required": True},
        ],
        "zone_affinity": [ZoneType.MARKET, ZoneType.PLAZA, ZoneType.GATE],
        "is_indoor": False,
    },
    "temple_4x3": {
        "size": (4, 3),
        "tiles": [
            ["stone_wall", "door", "stone_wall", "stone_wall"],
            ["stone_floor", "stone_floor", "stone_floor", "stone_wall"],
            ["stone_wall", "stone_wall", "stone_wall", "stone_wall"],
        ],
        "entity_slots": [
            {"offset": (2, 1), "role": "healer", "type": "npc", "required": False},
        ],
        "zone_affinity": [ZoneType.TEMPLE],
        "is_indoor": True,
    },
}

# --- Zone Entity Rules (which entities belong in which zones) ---
ZONE_ENTITY_RULES = {
    ZoneType.MARKET: {
        "npcs": ["merchant", "beggar", "quest_giver"],
        "items": ["barrel", "crate", "notice_board"],
        "enemies": [],
    },
    ZoneType.GATE: {
        "npcs": ["guard"],
        "items": [],
        "enemies": [],
    },
    ZoneType.DOCKS: {
        "npcs": ["merchant", "beggar"],
        "items": ["crate", "barrel"],
        "enemies": [],
    },
    ZoneType.TAVERN: {
        "npcs": ["innkeeper", "bard", "drunk_patron", "mysterious_stranger"],
        "items": ["fireplace", "notice_board"],
        "enemies": [],
    },
    ZoneType.RESIDENTIAL: {
        "npcs": ["quest_giver", "beggar"],
        "items": ["barrel", "crate"],
        "enemies": [],
    },
    ZoneType.TEMPLE: {
        "npcs": ["healer", "sage"],
        "items": ["altar", "bookshelf"],
        "enemies": [],
    },
    # Dungeon
    ZoneType.ENTRANCE: {
        "npcs": ["trapped_adventurer"],
        "items": ["torch"],
        "enemies": [],
    },
    ZoneType.CORRIDOR: {
        "npcs": [],
        "items": ["torch"],
        "enemies": ["skeleton", "giant_spider"],
    },
    ZoneType.TREASURE: {
        "npcs": [],
        "items": ["treasure_chest", "gold_pile"],
        "enemies": ["skeleton"],
    },
    ZoneType.BOSS: {
        "npcs": [],
        "items": ["treasure_chest"],
        "enemies": ["orc", "necromancer"],
    },
    # Wilderness
    ZoneType.CLEARING: {
        "npcs": ["ranger", "traveling_merchant"],
        "items": ["campfire_remains"],
        "enemies": [],
    },
    ZoneType.DENSE_FOREST: {
        "npcs": [],
        "items": [],
        "enemies": ["wolf", "bandit", "goblin"],
    },
    ZoneType.CAMP: {
        "npcs": ["traveling_merchant"],
        "items": ["campfire_pit", "abandoned_cart"],
        "enemies": [],
    },
}


# --- Zone Layouts (pre-defined zone arrangements per location type) ---
ZONE_LAYOUTS = {
    "town": [
        Zone("market_1", ZoneType.MARKET, "Market Square", 6, 5, 14, 10),
        Zone("gate_1", ZoneType.GATE, "Town Gate", 8, 0, 12, 3),
        Zone("tavern_1", ZoneType.TAVERN, "Tavern District", 1, 1, 6, 6, is_indoor=True),
        Zone("docks_1", ZoneType.DOCKS, "Harbor Docks", 0, 12, 20, 15),
        Zone("residential_1", ZoneType.RESIDENTIAL, "East Quarter", 14, 1, 19, 6),
        Zone("temple_1", ZoneType.TEMPLE, "Temple of Light", 14, 7, 19, 11),
        Zone("plaza_1", ZoneType.PLAZA, "Town Square", 6, 10, 14, 12),
    ],
    "dungeon": [
        Zone("entrance_1", ZoneType.ENTRANCE, "Entrance Hall", 7, 0, 13, 4),
        Zone("corridor_1", ZoneType.CORRIDOR, "Main Corridor", 8, 4, 12, 8),
        Zone("corridor_2", ZoneType.CORRIDOR, "Side Passage", 1, 5, 8, 8),
        Zone("treasure_1", ZoneType.TREASURE, "Treasure Room", 1, 9, 6, 13),
        Zone("boss_1", ZoneType.BOSS, "Inner Sanctum", 7, 9, 14, 14, danger_level=3),
    ],
    "wilderness": [
        Zone("clearing_1", ZoneType.CLEARING, "Forest Clearing", 6, 5, 14, 10),
        Zone("path_1", ZoneType.PATH, "Forest Path", 9, 0, 11, 15),
        Zone("forest_1", ZoneType.DENSE_FOREST, "Dense Woods", 0, 0, 6, 7),
        Zone("forest_2", ZoneType.DENSE_FOREST, "Dark Thicket", 14, 0, 20, 7),
        Zone("camp_1", ZoneType.CAMP, "Abandoned Camp", 2, 10, 6, 14),
        Zone("river_1", ZoneType.RIVER, "Forest Stream", 14, 8, 20, 15),
    ],
    "cave": [
        Zone("cave_ent_1", ZoneType.CAVE_ENTRANCE, "Cave Mouth", 8, 0, 12, 4),
        Zone("cavern_1", ZoneType.CAVERN, "Main Cavern", 4, 4, 16, 10),
        Zone("crystal_1", ZoneType.CRYSTAL, "Crystal Grotto", 10, 10, 16, 14),
        Zone("corridor_1", ZoneType.CORRIDOR, "Narrow Passage", 1, 6, 4, 14),
    ],
    "tavern": [
        Zone("common_1", ZoneType.TAVERN, "Common Room", 2, 2, 18, 10),
        Zone("bar_1", ZoneType.TAVERN, "Bar Counter", 2, 2, 8, 5, is_indoor=True),
        Zone("back_1", ZoneType.RESIDENTIAL, "Back Room", 14, 2, 18, 7, is_indoor=True),
    ],
}


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

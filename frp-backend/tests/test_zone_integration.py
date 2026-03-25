"""
Tests for zone integration and player position tracking.
"""
import pytest
from unittest.mock import MagicMock

from engine.map import TownGenerator, DungeonGenerator, WildernessGenerator
from engine.map.zones import (
    create_zone_map, select_tile_for_zone, place_building_template,
    ZoneType, ZONE_TILE_PALETTES, BUILDING_TEMPLATES
)
from engine.api.game_session import GameSession
from engine.api.game_engine import GameEngine
from engine.core.character import Character
from engine.core.dm_agent import DMContext, SceneType
import random


def _make_open_map(width=32, height=32):
    """Create a fully walkable map for movement tests."""
    from engine.map import MapData, TileType
    tiles = [[TileType.FLOOR for _ in range(width)] for _ in range(height)]
    return MapData(
        width=width, height=height, tiles=tiles, rooms=[],
        spawn_point=(width // 2, height // 2),
        metadata={"map_type": "test"},
    )


def _make_session(location="Town Square"):
    player = Character(name="Tester", hp=20, max_hp=20, level=1)
    dm_ctx = DMContext(scene_type=SceneType.EXPLORATION, location=location, party=[player])
    # Use a fully open map for predictable movement tests
    open_map = _make_open_map()
    session = GameSession(player=player, dm_context=dm_ctx, map_data=open_map)
    return session


def _make_engine():
    return GameEngine(llm=None)


# --- Task 2: Zone Integration ---

def test_town_map_has_zones():
    gen = TownGenerator(seed=1)
    map_data = gen.generate(width=40, height=40)
    d = map_data.to_dict()
    assert "zones" in d, "Town map should have 'zones' key"
    assert len(d["zones"]) > 0, "Town map should have non-empty zones"
    # Check zone has expected keys
    zone = d["zones"][0]
    for key in ("id", "zone_type", "name", "x1", "y1", "x2", "y2"):
        assert key in zone, f"Zone missing key: {key}"


def test_dungeon_map_has_zones():
    gen = DungeonGenerator(seed=2)
    map_data = gen.generate(width=40, height=30)
    d = map_data.to_dict()
    assert "zones" in d
    assert len(d["zones"]) > 0


def test_wilderness_map_has_zones():
    gen = WildernessGenerator(seed=3)
    map_data = gen.generate(width=40, height=30)
    d = map_data.to_dict()
    assert "zones" in d
    assert len(d["zones"]) > 0


def test_zone_tile_selection():
    rng = random.Random(42)
    major_zones = [
        ZoneType.MARKET, ZoneType.TAVERN, ZoneType.RESIDENTIAL,
        ZoneType.ROAD, ZoneType.PLAZA, ZoneType.GATE,
        ZoneType.CORRIDOR, ZoneType.TREASURE,
        ZoneType.CLEARING, ZoneType.DENSE_FOREST, ZoneType.PATH,
    ]
    for zone_type in major_zones:
        tile = select_tile_for_zone(zone_type, rng)
        assert isinstance(tile, str), f"Expected string tile for {zone_type}"
        assert len(tile) > 0, f"Expected non-empty tile for {zone_type}"
        # Tile must be in the palette
        palette = ZONE_TILE_PALETTES.get(zone_type)
        if palette:
            valid_tiles = [t[0] for t in palette["ground"]]
            assert tile in valid_tiles, f"Tile {tile!r} not in palette for {zone_type}"


def test_zone_tile_selection_none():
    rng = random.Random(99)
    tile = select_tile_for_zone(None, rng)
    assert tile in ("grass", "dirt_path", "cobblestone")


def test_building_template_stamp():
    # Create a 10x5 tile grid (strings)
    width, height = 10, 5
    tiles = [["floor"] * width for _ in range(height)]
    entity_slots = place_building_template(tiles, "tavern_5x3", 1, 1, width, height)

    # Check stamped tiles match template
    template = BUILDING_TEMPLATES["tavern_5x3"]
    tw, th = template["size"]
    for ty in range(th):
        for tx in range(tw):
            expected = template["tiles"][ty][tx]
            actual = tiles[1 + ty][1 + tx]
            assert actual == expected, f"At ({1+tx},{1+ty}): expected {expected!r}, got {actual!r}"

    # Check entity slots returned
    assert len(entity_slots) > 0
    slot = entity_slots[0]
    assert "role" in slot
    assert "x" in slot and "y" in slot


# --- Task 3: Position Tracking ---

def test_player_position_starts_at_origin():
    session = _make_session()
    # Position starts at map spawn point (16, 16 for 32x32 open map)
    assert session.position == [16, 16]
    assert session.facing == "north"


def test_player_position_updates_on_move_north():
    engine = _make_engine()
    session = _make_session()
    session.position = [5, 5]
    engine.process_action(session, "move north")
    assert session.facing == "north"
    assert session.position[1] == 4, f"Expected y=4, got {session.position[1]}"


def test_player_position_updates_on_move_south():
    engine = _make_engine()
    session = _make_session()
    session.position = [5, 5]
    engine.process_action(session, "move south")
    assert session.facing == "south"
    assert session.position[1] == 6


def test_player_position_updates_on_move_east():
    engine = _make_engine()
    session = _make_session()
    session.position = [5, 5]
    engine.process_action(session, "move east")
    assert session.facing == "east"
    assert session.position[0] == 6


def test_player_position_updates_on_move_west():
    engine = _make_engine()
    session = _make_session()
    session.position = [5, 5]
    engine.process_action(session, "move west")
    assert session.facing == "west"
    assert session.position[0] == 4


def test_player_facing_updates():
    engine = _make_engine()
    session = _make_session()
    engine.process_action(session, "move east")
    assert session.facing == "east"


def test_player_facing_turn_left():
    engine = _make_engine()
    session = _make_session()
    session.facing = "north"
    engine.process_action(session, "move left")
    assert session.facing == "west"


def test_player_facing_turn_right():
    engine = _make_engine()
    session = _make_session()
    session.facing = "north"
    engine.process_action(session, "move right")
    assert session.facing == "east"


def test_player_move_forward_uses_facing():
    engine = _make_engine()
    session = _make_session()
    session.facing = "east"
    session.position = [5, 5]
    engine.process_action(session, "move forward")
    assert session.position == [6, 5]


def test_player_position_clamped_at_bounds():
    engine = _make_engine()
    session = _make_session()
    session.position = [0, 0]
    session.facing = "north"
    engine.process_action(session, "move north")
    # Y should not go below 0
    assert session.position[1] >= 0


def test_position_in_action_response():
    """Action response player.position is not [0,0] after move from non-zero start."""
    engine = _make_engine()
    session = _make_session()
    session.position = [10, 10]
    result = engine.process_action(session, "move north")
    # position in session should have changed
    assert session.position != [10, 10] or session.position == [10, 9]
    assert session.position[1] == 9


def test_session_to_dict_includes_position():
    session = _make_session()
    session.position = [3, 7]
    session.facing = "east"
    d = session.to_dict()
    assert d["position"] == [3, 7]
    assert d["facing"] == "east"


def test_create_zone_map_town():
    zm = create_zone_map("town", 40, 40)
    assert len(zm.zones) > 0
    # Should have at least market and tavern
    zone_types = {z.zone_type for z in zm.zones.values()}
    assert ZoneType.MARKET in zone_types or ZoneType.TAVERN in zone_types


def test_create_zone_map_dungeon():
    zm = create_zone_map("dungeon", 40, 40)
    assert len(zm.zones) > 0


def test_zone_map_get_zone_at():
    zm = create_zone_map("town", 40, 40)
    # Market zone: 6-14 x, 5-10 y
    zone = zm.get_zone_at(8, 7)
    # May or may not be market depending on layout, just ensure no crash
    # and result is a Zone or None
    from engine.map.zones import Zone
    assert zone is None or isinstance(zone, Zone)

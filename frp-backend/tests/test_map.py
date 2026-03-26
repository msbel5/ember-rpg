"""
Ember RPG - Phase 4: Map Generator Tests
"""
import pytest
from engine.map import (
    TileType, Room, MapData, DungeonGenerator, TownGenerator, WildernessGenerator
)


class TestRoom:
    def test_center(self):
        r = Room(0, 0, 10, 8)
        assert r.center() == (5, 4)

    def test_inner_tiles(self):
        r = Room(0, 0, 5, 4)
        inner = r.inner_tiles()
        assert len(inner) > 0
        assert (1, 1) in inner
        # Borders not included
        assert (0, 0) not in inner

    def test_overlaps_true(self):
        a = Room(0, 0, 10, 10)
        b = Room(5, 5, 10, 10)
        assert a.overlaps(b)

    def test_overlaps_false(self):
        a = Room(0, 0, 5, 5)
        b = Room(10, 10, 5, 5)
        assert not a.overlaps(b)

    def test_overlaps_with_margin(self):
        a = Room(0, 0, 5, 5)
        b = Room(6, 0, 5, 5)
        # Adjacent with 1 margin → overlaps
        assert a.overlaps(b, margin=1)
        assert not a.overlaps(b, margin=0)


class TestMapData:
    def _make_map(self, w=20, h=15):
        tiles = [[TileType.WALL for _ in range(w)] for _ in range(h)]
        # Add a floor at center
        tiles[7][10] = TileType.FLOOR
        tiles[7][11] = TileType.FLOOR
        return MapData(
            width=w, height=h, tiles=tiles,
            rooms=[], spawn_point=(10, 7),
        )

    def test_get_tile(self):
        m = self._make_map()
        assert m.get_tile(10, 7) == TileType.FLOOR
        assert m.get_tile(0, 0) == TileType.WALL

    def test_get_tile_oob(self):
        m = self._make_map()
        assert m.get_tile(999, 999) == TileType.WALL

    def test_set_tile(self):
        m = self._make_map()
        m.set_tile(5, 5, TileType.DOOR)
        assert m.get_tile(5, 5) == TileType.DOOR

    def test_is_walkable_floor(self):
        m = self._make_map()
        assert m.is_walkable(10, 7) is True

    def test_is_walkable_wall(self):
        m = self._make_map()
        assert m.is_walkable(0, 0) is False

    def test_to_ascii_contains_tiles(self):
        m = self._make_map()
        ascii_str = m.to_ascii()
        assert "#" in ascii_str  # walls
        assert "@" in ascii_str  # spawn marker

    def test_to_dict_structure(self):
        m = self._make_map()
        d = m.to_dict()
        assert "tiles" in d
        assert "rooms" in d
        assert "spawn_point" in d
        assert "exit_points" in d
        assert "metadata" in d
        assert d["width"] == 20
        assert d["height"] == 15

    def test_reachable_from_spawn(self):
        m = self._make_map()
        reachable = m.reachable_from_spawn()
        assert (10, 7) in reachable
        assert (11, 7) in reachable


class TestDungeonGenerator:
    def test_generate_returns_map(self):
        gen = DungeonGenerator(seed=42)
        m = gen.generate(50, 30)
        assert isinstance(m, MapData)
        assert m.width == 50
        assert m.height == 30

    def test_room_count_in_range(self):
        gen = DungeonGenerator(seed=42)
        m = gen.generate(50, 30)
        assert DungeonGenerator.MIN_ROOMS <= len(m.rooms) <= DungeonGenerator.MAX_ROOMS

    def test_spawn_point_exists(self):
        gen = DungeonGenerator(seed=42)
        m = gen.generate(50, 30)
        assert m.spawn_point is not None
        sx, sy = m.spawn_point
        assert 0 <= sx < 50
        assert 0 <= sy < 30

    def test_spawn_is_walkable(self):
        gen = DungeonGenerator(seed=42)
        m = gen.generate(50, 30)
        sx, sy = m.spawn_point
        assert m.is_walkable(sx, sy)

    def test_exit_point_exists(self):
        gen = DungeonGenerator(seed=42)
        m = gen.generate(50, 30)
        assert len(m.exit_points) >= 1

    def test_deterministic_output(self):
        m1 = DungeonGenerator(seed=42).generate(50, 30)
        m2 = DungeonGenerator(seed=42).generate(50, 30)
        assert m1.to_ascii() == m2.to_ascii()

    def test_different_seeds_different_maps(self):
        m1 = DungeonGenerator(seed=1).generate(50, 30)
        m2 = DungeonGenerator(seed=99).generate(50, 30)
        assert m1.to_ascii() != m2.to_ascii()

    def test_rooms_have_types(self):
        gen = DungeonGenerator(seed=42)
        m = gen.generate(50, 30)
        types = [r.room_type for r in m.rooms]
        assert "entrance" in types
        assert "boss" in types

    def test_has_walls_and_floors(self):
        gen = DungeonGenerator(seed=42)
        m = gen.generate(50, 30)
        ascii_str = m.to_ascii()
        assert "#" in ascii_str
        assert "." in ascii_str

    def test_metadata(self):
        gen = DungeonGenerator(seed=42)
        m = gen.generate(50, 30)
        assert m.metadata["seed"] == 42
        assert m.metadata["map_type"] == "dungeon"

    def test_all_rooms_connected(self):
        """All rooms must be reachable from spawn via BFS."""
        gen = DungeonGenerator(seed=42)
        m = gen.generate(50, 30)
        reachable = m.reachable_from_spawn()
        for room in m.rooms:
            cx, cy = room.center()
            # At least one inner tile should be reachable
            inner = room.inner_tiles()
            assert any((x, y) in reachable for x, y in inner), \
                f"Room {room.room_type} at ({room.x},{room.y}) not reachable"

    def test_large_map(self):
        gen = DungeonGenerator(seed=7)
        m = gen.generate(80, 50)
        assert m.width == 80
        assert len(m.rooms) >= DungeonGenerator.MIN_ROOMS

    def test_to_dict_serializable(self):
        import json
        gen = DungeonGenerator(seed=42)
        m = gen.generate(30, 20)
        d = m.to_dict()
        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert len(json_str) > 0

    @pytest.mark.parametrize("seed", [1, 7, 13, 21, 42])
    def test_spawn_has_two_cardinal_walkable_neighbors(self, seed):
        gen = DungeonGenerator(seed=seed)
        m = gen.generate(50, 30)
        sx, sy = m.spawn_point
        cardinal_neighbors = sum(
            1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if m.is_walkable(sx + dx, sy + dy)
        )
        assert cardinal_neighbors >= 2


class TestTownGenerator:
    def test_generate_returns_map(self):
        gen = TownGenerator(seed=42)
        m = gen.generate(60, 40)
        assert isinstance(m, MapData)
        assert m.width == 60
        assert m.height == 40

    def test_has_buildings(self):
        gen = TownGenerator(seed=42)
        m = gen.generate(60, 40)
        assert len(m.rooms) >= 3

    def test_spawn_on_map(self):
        gen = TownGenerator(seed=42)
        m = gen.generate(60, 40)
        sx, sy = m.spawn_point
        assert 0 <= sx < 60 and 0 <= sy < 40

    def test_has_roads(self):
        gen = TownGenerator(seed=42)
        m = gen.generate(60, 40)
        ascii_str = m.to_ascii()
        assert TileType.ROAD.value in ascii_str

    def test_deterministic(self):
        m1 = TownGenerator(seed=5).generate(40, 30)
        m2 = TownGenerator(seed=5).generate(40, 30)
        assert m1.to_ascii() == m2.to_ascii()

    def test_metadata(self):
        m = TownGenerator(seed=5).generate(40, 30)
        assert m.metadata["map_type"] == "town"

    @pytest.mark.parametrize("seed", [1, 7, 13, 21, 42])
    def test_spawn_has_two_cardinal_walkable_neighbors(self, seed):
        m = TownGenerator(seed=seed).generate(60, 40)
        sx, sy = m.spawn_point
        cardinal_neighbors = sum(
            1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if m.is_walkable(sx + dx, sy + dy)
        )
        assert cardinal_neighbors >= 2


class TestWildernessGenerator:
    def test_generate_returns_map(self):
        gen = WildernessGenerator(seed=42)
        m = gen.generate(40, 30)
        assert isinstance(m, MapData)
        assert m.width == 40
        assert m.height == 30

    def test_spawn_exists(self):
        gen = WildernessGenerator(seed=42)
        m = gen.generate(40, 30)
        assert m.spawn_point is not None

    def test_has_trees_and_water(self):
        gen = WildernessGenerator(seed=42)
        m = gen.generate(40, 30)
        ascii_str = m.to_ascii()
        assert TileType.TREE.value in ascii_str
        assert TileType.WATER.value in ascii_str

    @pytest.mark.parametrize("seed", [1, 7, 13, 21, 42])
    def test_spawn_has_two_cardinal_walkable_neighbors(self, seed):
        m = WildernessGenerator(seed=seed).generate(40, 30)
        sx, sy = m.spawn_point
        cardinal_neighbors = sum(
            1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if m.is_walkable(sx + dx, sy + dy)
        )
        assert cardinal_neighbors >= 2

    def test_has_road(self):
        gen = WildernessGenerator(seed=42)
        m = gen.generate(40, 30)
        ascii_str = m.to_ascii()
        assert TileType.ROAD.value in ascii_str

    def test_deterministic(self):
        m1 = WildernessGenerator(seed=3).generate(40, 30)
        m2 = WildernessGenerator(seed=3).generate(40, 30)
        assert m1.to_ascii() == m2.to_ascii()

    def test_metadata(self):
        m = WildernessGenerator(seed=42).generate(40, 30)
        assert m.metadata["map_type"] == "wilderness"

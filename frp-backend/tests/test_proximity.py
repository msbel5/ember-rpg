"""Tests for Module 10: Proximity Rules (FR-42..FR-45)"""
import pytest
from engine.world.proximity import (
    distance, manhattan_distance, in_range, check_proximity,
    move_cardinal, astar_path, has_line_of_sight,
    RANGE_MELEE, RANGE_RANGED, RANGE_SHOUT, MAX_MOVE_PER_TURN,
)


class TestDistance:
    def test_same_position(self):
        assert distance([5, 5], [5, 5]) == 0

    def test_adjacent(self):
        assert distance([5, 5], [5, 6]) == 1
        assert distance([5, 5], [6, 5]) == 1

    def test_diagonal(self):
        assert distance([0, 0], [3, 3]) == 3  # Chebyshev

    def test_far_away(self):
        assert distance([0, 0], [10, 5]) == 10

    def test_manhattan(self):
        assert manhattan_distance([0, 0], [3, 4]) == 7


class TestInRange:
    def test_melee_adjacent(self):
        assert in_range([5, 5], [5, 6], RANGE_MELEE) is True

    def test_melee_too_far(self):
        assert in_range([5, 5], [5, 8], RANGE_MELEE) is False

    def test_ranged_5_tiles(self):
        assert in_range([0, 0], [5, 0], RANGE_RANGED) is True

    def test_ranged_too_far(self):
        assert in_range([0, 0], [6, 0], RANGE_RANGED) is False

    def test_shout_3_tiles(self):
        assert in_range([5, 5], [5, 8], RANGE_SHOUT) is True


class TestCheckProximity:
    def test_talk_adjacent_ok(self):
        ok, msg = check_proximity([5, 5], [5, 6], "talk")
        assert ok is True
        assert msg == ""

    def test_talk_too_far(self):
        ok, msg = check_proximity([5, 5], [5, 8], "talk")
        assert ok is False
        assert "Too far away" in msg

    def test_look_always_ok(self):
        ok, _ = check_proximity([0, 0], [99, 99], "look")
        assert ok is True

    def test_ranged_attack_in_range(self):
        ok, _ = check_proximity([0, 0], [4, 0], "attack_ranged")
        assert ok is True


class TestMoveCardinal:
    def test_move_north(self):
        pos, ok, msg = move_cardinal([5, 5], "north")
        assert ok is True
        assert pos == [5, 4]

    def test_move_south(self):
        pos, ok, msg = move_cardinal([5, 5], "south")
        assert ok is True
        assert pos == [5, 6]

    def test_move_east(self):
        pos, ok, msg = move_cardinal([5, 5], "east")
        assert ok is True
        assert pos == [6, 5]

    def test_move_west(self):
        pos, ok, msg = move_cardinal([5, 5], "west")
        assert ok is True
        assert pos == [4, 5]

    def test_invalid_direction(self):
        pos, ok, msg = move_cardinal([5, 5], "up")
        assert ok is False
        assert "Unknown direction" in msg


class TestAstarPath:
    def test_no_map_straight_line(self):
        path = astar_path(None, [0, 0], [3, 0])
        assert len(path) == 3
        assert path[-1] == [3, 0]

    def test_no_map_capped_at_5(self):
        path = astar_path(None, [0, 0], [10, 0])
        assert len(path) == MAX_MOVE_PER_TURN

    def test_same_position(self):
        path = astar_path(None, [5, 5], [5, 5])
        assert path == []

    def test_diagonal_movement(self):
        path = astar_path(None, [0, 0], [3, 3])
        assert len(path) <= MAX_MOVE_PER_TURN
        final = path[-1]
        assert abs(final[0] - 3) + abs(final[1] - 3) < abs(0 - 3) + abs(0 - 3)

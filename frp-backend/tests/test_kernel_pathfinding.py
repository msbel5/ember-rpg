from __future__ import annotations

from math import isinf
from random import Random

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.pathfinding import (
    MovementState,
    SearchMap,
    TilePassability,
    attempt_bump,
    compute_movement_speed,
    find_path,
    random_walk_target,
    tick_movement,
)


def _actor(
    actor_id: str,
    *,
    x: int,
    y: int,
    faction: str = "allies",
    agi: int = 10,
    strength: int = 10,
    idle: bool = True,
) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc", faction_id=faction),
        position=ActorPosition(x=x, y=y),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"AGI": agi, "MIG": strength},
        raw_payload={"idle": idle},
    )


def _normal_map(width: int, height: int) -> SearchMap:
    return SearchMap(
        width=width,
        height=height,
        tiles=[[TilePassability.NORMAL for _x in range(width)] for _y in range(height)],
    )


def test_ac01_find_path_routes_around_wall_gap():
    search_map = _normal_map(10, 10)
    for y in range(9):
        search_map.tiles[y][5] = TilePassability.IMPASSABLE

    result = find_path(search_map, (0, 5), (9, 5))

    assert result.success is True
    assert (5, 9) in result.path


def test_ac02_large_actor_cannot_fit_through_one_tile_gap():
    search_map = _normal_map(6, 6)
    for y in range(6):
        if y != 3:
            search_map.tiles[y][2] = TilePassability.IMPASSABLE
            search_map.tiles[y][4] = TilePassability.IMPASSABLE

    result = find_path(search_map, (0, 2), (5, 2), actor_size=2)

    assert result.success is False


def test_ac03_total_cost_counts_water_and_normal_tiles():
    search_map = SearchMap(
        width=6,
        height=1,
        tiles=[[
            TilePassability.NORMAL,
            TilePassability.WATER,
            TilePassability.WATER,
            TilePassability.WATER,
            TilePassability.NORMAL,
            TilePassability.NORMAL,
        ]],
    )

    result = find_path(search_map, (0, 0), (5, 0))

    assert result.success is True
    assert result.total_cost == 8.0


def test_ac04_attempt_bump_swaps_friendly_idle_actors():
    search_map = _normal_map(5, 5)
    actor = _actor("a", x=1, y=1, faction="allies")
    blocker = _actor("b", x=2, y=1, faction="allies", idle=True)
    search_map.set_occupant(1, 1, "a")
    search_map.set_occupant(2, 1, "b")

    bumped = attempt_bump(actor, (2, 1), search_map, {"a": actor, "b": blocker})

    assert bumped is True
    assert (actor.position.x, actor.position.y) == (2, 1)
    assert (blocker.position.x, blocker.position.y) == (1, 1)


def test_ac05_random_walk_target_returns_walkable_tile_within_radius():
    search_map = _normal_map(20, 20)

    target = random_walk_target((5, 5), search_map, radius=10, rng=Random(42))

    assert target is not None
    assert abs(target[0] - 5) <= 10
    assert abs(target[1] - 5) <= 10
    assert search_map.is_passable(*target)


def test_ac06_closed_door_passable_with_enough_strength():
    search_map = _normal_map(5, 5)
    for y in range(5):
        if y != 3:
            search_map.tiles[y][3] = TilePassability.IMPASSABLE
    search_map.tiles[3][3] = TilePassability.DOOR_CLOSED
    search_map.doors[(3, 3)] = {"locked": False, "key_id": "", "force_difficulty": 14}

    result = find_path(search_map, (2, 3), (4, 3), actor_strength=16)

    assert result.success is True
    assert (3, 3) in result.path
    assert search_map.terrain_cost(3, 3, actor_strength=16) == 5.0


def test_ac07_locked_door_without_key_or_strength_is_impassable():
    search_map = _normal_map(5, 5)
    for y in range(5):
        if y != 3:
            search_map.tiles[y][3] = TilePassability.IMPASSABLE
    search_map.tiles[3][3] = TilePassability.DOOR_CLOSED
    search_map.doors[(3, 3)] = {"locked": True, "key_id": "vault_key", "force_difficulty": 14}

    result = find_path(search_map, (2, 3), (4, 3), actor_strength=10, door_keys=set())

    assert result.success is False


def test_ac08_find_path_returns_failure_when_no_path_exists():
    search_map = _normal_map(5, 5)
    for x in range(5):
        search_map.tiles[2][x] = TilePassability.IMPASSABLE

    result = find_path(search_map, (1, 1), (3, 3))

    assert result.success is False
    assert result.path == []
    assert isinf(result.total_cost)


def test_ac09_compute_movement_speed_uses_agility():
    actor = _actor("swift", x=0, y=0, agi=14)

    assert compute_movement_speed(actor, encumbrance_ratio=0.0) == 8


def test_ac10_find_path_respects_max_iterations_cutoff():
    search_map = _normal_map(80, 60)

    result = find_path(search_map, (0, 0), (79, 59), max_iterations=1)

    assert result.success is False
    assert result.tiles_explored >= 1


def test_tick_movement_advances_actor_along_path_when_enough_ticks_accumulate():
    search_map = _normal_map(5, 5)
    actor = _actor("mover", x=0, y=0, agi=14)
    movement = MovementState(
        actor_id="mover",
        current_path=[(1, 0), (2, 0)],
        ticks_per_tile=2,
        ticks_accumulated=1,
        moving=True,
    )

    moved_tile, complete = tick_movement(actor, movement, search_map)

    assert moved_tile == (1, 0)
    assert complete is False
    assert (actor.position.x, actor.position.y) == (1, 0)


def test_search_map_round_trip_preserves_doors_and_occupants():
    search_map = _normal_map(4, 4)
    search_map.tiles[1][1] = TilePassability.DOOR_CLOSED
    search_map.doors[(1, 1)] = {"locked": True, "key_id": "k1", "force_difficulty": 12}
    search_map.set_occupant(2, 2, "actor_1")

    restored = SearchMap.from_dict(search_map.to_dict())

    assert restored.tiles == search_map.tiles
    assert restored.doors == search_map.doors
    assert restored.occupants == search_map.occupants

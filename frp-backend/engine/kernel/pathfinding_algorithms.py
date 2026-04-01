from __future__ import annotations

import heapq
import math
from random import Random

from engine.kernel.actor import ActorRecord

from .pathfinding_types import MovementState, PathResult, SearchMap


def find_path(
    search_map: SearchMap,
    start: tuple[int, int],
    goal: tuple[int, int],
    actor_size: int = 1,
    max_iterations: int = 5000,
    door_keys: set[str] | None = None,
    actor_strength: int = 10,
) -> PathResult:
    start = clamp_coord(search_map, start)
    goal = clamp_coord(search_map, goal)
    cache_key = (search_map.cache_revision, start, goal, int(actor_size), frozenset(door_keys or set()), int(actor_strength))
    cached = search_map.path_cache.get(cache_key)
    if cached is not None:
        return PathResult(list(cached.path), cached.total_cost, cached.success, cached.tiles_explored)

    if not search_map.is_passable(*start, actor_size=actor_size, door_keys=door_keys, actor_strength=actor_strength):
        return PathResult([], math.inf, False, 0)
    if not search_map.is_passable(*goal, actor_size=actor_size, door_keys=door_keys, actor_strength=actor_strength):
        return PathResult([], math.inf, False, 0)

    open_heap: list[tuple[float, int, tuple[int, int]]] = []
    counter = 0
    heapq.heappush(open_heap, (heuristic(start, goal), counter, start))
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score = {start: 0.0}
    explored = 0

    while open_heap and explored < int(max_iterations):
        _, _, current = heapq.heappop(open_heap)
        explored += 1
        if current == goal:
            path = reconstruct_path(came_from, current)
            result = PathResult(path=path, total_cost=float(g_score[current]), success=True, tiles_explored=explored)
            search_map.cache_result(cache_key, result)
            return result
        for neighbor in neighbors(search_map, current, actor_size=actor_size, door_keys=door_keys, actor_strength=actor_strength):
            tentative = g_score[current] + search_map.terrain_cost(*neighbor, door_keys=door_keys, actor_strength=actor_strength)
            if tentative >= g_score.get(neighbor, math.inf):
                continue
            came_from[neighbor] = current
            g_score[neighbor] = tentative
            counter += 1
            heapq.heappush(open_heap, (tentative + heuristic(neighbor, goal), counter, neighbor))

    result = PathResult([], math.inf, False, explored)
    search_map.cache_result(cache_key, result)
    return result


def tick_movement(
    actor: ActorRecord,
    movement: MovementState,
    search_map: SearchMap,
) -> tuple[tuple[int, int] | None, bool]:
    if not movement.moving or movement.is_complete():
        movement.moving = False
        return None, movement.is_complete()
    movement.ticks_accumulated += 1
    if movement.ticks_accumulated < movement.ticks_per_tile:
        return None, False
    movement.ticks_accumulated = 0
    next_tile = movement.next_tile()
    if next_tile is None:
        movement.moving = False
        return None, True
    if not search_map.is_passable(*next_tile, ignore_occupants=False):
        movement.moving = False
        return None, False
    previous = movement.current_tile()
    if previous is not None:
        search_map.set_occupant(previous[0], previous[1], None)
    search_map.set_occupant(next_tile[0], next_tile[1], actor.identity.actor_id)
    actor.position.x = next_tile[0]
    actor.position.y = next_tile[1]
    movement.path_index += 1
    if movement.is_complete():
        movement.moving = False
        return next_tile, True
    return next_tile, False


def attempt_bump(
    actor: ActorRecord,
    target: tuple[int, int],
    search_map: SearchMap,
    actors: dict[str, ActorRecord],
) -> bool:
    target = clamp_coord(search_map, target)
    occupant_id = search_map.occupants.get(target)
    if occupant_id is None:
        return False
    other = actors.get(occupant_id)
    if other is None:
        return False
    if other.identity.faction_id != actor.identity.faction_id:
        return False
    if not bool(other.raw_payload.get("idle", False)):
        return False
    origin = (actor.position.x, actor.position.y)
    actor.position.x, actor.position.y = target
    other.position.x, other.position.y = origin
    search_map.set_occupant(origin[0], origin[1], other.identity.actor_id)
    search_map.set_occupant(target[0], target[1], actor.identity.actor_id)
    return True


def random_walk_target(
    origin: tuple[int, int],
    search_map: SearchMap,
    radius: int = 6,
    rng: Random | None = None,
) -> tuple[int, int]:
    resolved_rng = rng or Random(0)
    ox, oy = origin
    candidates: list[tuple[int, int]] = []
    for _ in range(40):
        tx = ox + resolved_rng.randint(-radius, radius)
        ty = oy + resolved_rng.randint(-radius, radius)
        candidate = clamp_coord(search_map, (tx, ty))
        if search_map.is_passable(*candidate):
            candidates.append(candidate)
    if not candidates:
        return clamp_coord(search_map, origin)
    return candidates[resolved_rng.randrange(len(candidates))]


def compute_movement_speed(actor: ActorRecord, encumbrance_ratio: float) -> int:
    agility = int(actor.stats.get("AGI", actor.stats.get("DEX", 10)))
    base = max(4, 10 - ((agility - 10) // 2))
    if encumbrance_ratio >= 1.0:
        return base + 8
    if encumbrance_ratio >= 0.75:
        return base + 4
    if encumbrance_ratio >= 0.5:
        return base + 2
    return base


def neighbors(
    search_map: SearchMap,
    current: tuple[int, int],
    *,
    actor_size: int,
    door_keys: set[str] | None,
    actor_strength: int,
) -> list[tuple[int, int]]:
    cx, cy = current
    result: list[tuple[int, int]] = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = cx + dx, cy + dy
        if search_map.is_passable(
            nx,
            ny,
            actor_size=actor_size,
            door_keys=door_keys,
            actor_strength=actor_strength,
        ):
            result.append((nx, ny))
    return result


def heuristic(left: tuple[int, int], right: tuple[int, int]) -> float:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def reconstruct_path(
    came_from: dict[tuple[int, int], tuple[int, int]],
    current: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def clamp_coord(search_map: SearchMap, coord: tuple[int, int]) -> tuple[int, int]:
    return (
        max(0, min(search_map.width - 1, int(coord[0]))),
        max(0, min(search_map.height - 1, int(coord[1]))),
    )


__all__ = [
    "attempt_bump",
    "compute_movement_speed",
    "find_path",
    "random_walk_target",
    "tick_movement",
]

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from enum import IntEnum
from random import Random
from typing import Any

from engine.kernel.actor import ActorRecord


class TilePassability(IntEnum):
    IMPASSABLE = 0
    NORMAL = 1
    WATER = 2
    TRAP = 3
    DIFFICULT = 4
    DOOR_OPEN = 5
    DOOR_CLOSED = 6
    UNDERGROUND = 7


@dataclass
class SearchMap:
    width: int
    height: int
    tiles: list[list[TilePassability]]
    occupants: dict[tuple[int, int], str] = field(default_factory=dict)
    doors: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)
    cache_revision: int = 0
    path_cache: dict[tuple[Any, ...], "PathResult"] = field(default_factory=dict, repr=False)
    _cache_order: list[tuple[Any, ...]] = field(default_factory=list, repr=False)

    def is_passable(
        self,
        x: int,
        y: int,
        actor_size: int = 1,
        *,
        door_keys: set[str] | None = None,
        actor_strength: int = 10,
        ignore_occupants: bool = True,
    ) -> bool:
        for py in range(y, y + max(1, int(actor_size))):
            for px in range(x, x + max(1, int(actor_size))):
                if not self._tile_passable(
                    px,
                    py,
                    door_keys=door_keys,
                    actor_strength=actor_strength,
                    ignore_occupants=ignore_occupants,
                ):
                    return False
        return True

    def terrain_cost(
        self,
        x: int,
        y: int,
        *,
        door_keys: set[str] | None = None,
        actor_strength: int = 10,
    ) -> float:
        if not self._in_bounds(x, y):
            return math.inf
        tile = self.tiles[y][x]
        if tile == TilePassability.IMPASSABLE:
            return math.inf
        if tile == TilePassability.WATER:
            return 2.0
        if tile == TilePassability.DIFFICULT:
            return 1.5
        if tile == TilePassability.DOOR_CLOSED:
            if not self._door_passable(x, y, door_keys=door_keys, actor_strength=actor_strength):
                return math.inf
            return 5.0
        return 1.0

    def set_occupant(self, x: int, y: int, actor_id: str | None) -> None:
        coord = (int(x), int(y))
        if actor_id is None:
            self.occupants.pop(coord, None)
        else:
            self.occupants[coord] = str(actor_id)
        self.invalidate_cache()

    def invalidate_cache(self) -> None:
        self.cache_revision += 1
        self.path_cache.clear()
        self._cache_order.clear()

    def cache_result(self, key: tuple[Any, ...], result: "PathResult", limit: int = 4) -> None:
        self.path_cache[key] = result
        if key in self._cache_order:
            self._cache_order.remove(key)
        self._cache_order.append(key)
        while len(self._cache_order) > int(limit):
            oldest = self._cache_order.pop(0)
            self.path_cache.pop(oldest, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": int(self.width),
            "height": int(self.height),
            "tiles": [[int(tile) for tile in row] for row in self.tiles],
            "occupants": {f"{x},{y}": actor_id for (x, y), actor_id in self.occupants.items()},
            "doors": {f"{x},{y}": dict(data) for (x, y), data in self.doors.items()},
            "cache_revision": int(self.cache_revision),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchMap":
        occupants = {
            tuple(int(part) for part in key.split(",", 1)): str(value)
            for key, value in dict(data.get("occupants", {})).items()
        }
        doors = {
            tuple(int(part) for part in key.split(",", 1)): dict(value)
            for key, value in dict(data.get("doors", {})).items()
        }
        return cls(
            width=int(data["width"]),
            height=int(data["height"]),
            tiles=[[TilePassability(int(tile)) for tile in row] for row in data.get("tiles", [])],
            occupants=occupants,
            doors=doors,
            cache_revision=int(data.get("cache_revision", 0)),
        )

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= int(x) < self.width and 0 <= int(y) < self.height

    def _door_passable(self, x: int, y: int, *, door_keys: set[str] | None, actor_strength: int) -> bool:
        door = self.doors.get((x, y), {})
        locked = bool(door.get("locked", False))
        key_id = str(door.get("key_id", ""))
        if not locked:
            return True
        if key_id and door_keys and key_id in door_keys:
            return True
        return int(actor_strength) >= int(door.get("force_difficulty", 10))

    def _tile_passable(
        self,
        x: int,
        y: int,
        *,
        door_keys: set[str] | None,
        actor_strength: int,
        ignore_occupants: bool,
    ) -> bool:
        if not self._in_bounds(x, y):
            return False
        tile = self.tiles[y][x]
        if tile == TilePassability.IMPASSABLE:
            return False
        if tile == TilePassability.DOOR_CLOSED and not self._door_passable(
            x,
            y,
            door_keys=door_keys,
            actor_strength=actor_strength,
        ):
            return False
        if not ignore_occupants and (x, y) in self.occupants:
            return False
        return True


@dataclass
class PathResult:
    path: list[tuple[int, int]]
    total_cost: float
    success: bool
    tiles_explored: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": [[x, y] for x, y in self.path],
            "total_cost": float(self.total_cost),
            "success": bool(self.success),
            "tiles_explored": int(self.tiles_explored),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PathResult":
        return cls(
            path=[(int(x), int(y)) for x, y in data.get("path", [])],
            total_cost=float(data.get("total_cost", math.inf)),
            success=bool(data.get("success", False)),
            tiles_explored=int(data.get("tiles_explored", 0)),
        )


@dataclass
class MovementState:
    actor_id: str
    current_path: list[tuple[int, int]] = field(default_factory=list)
    path_index: int = 0
    ticks_per_tile: int = 10
    ticks_accumulated: int = 0
    moving: bool = False

    def current_tile(self) -> tuple[int, int] | None:
        if self.path_index <= 0 or self.path_index > len(self.current_path):
            return None
        return self.current_path[self.path_index - 1]

    def next_tile(self) -> tuple[int, int] | None:
        if self.path_index >= len(self.current_path):
            return None
        return self.current_path[self.path_index]

    def is_complete(self) -> bool:
        return self.path_index >= len(self.current_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "current_path": [[x, y] for x, y in self.current_path],
            "path_index": int(self.path_index),
            "ticks_per_tile": int(self.ticks_per_tile),
            "ticks_accumulated": int(self.ticks_accumulated),
            "moving": bool(self.moving),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MovementState":
        return cls(
            actor_id=str(data["actor_id"]),
            current_path=[(int(x), int(y)) for x, y in data.get("current_path", [])],
            path_index=int(data.get("path_index", 0)),
            ticks_per_tile=int(data.get("ticks_per_tile", 10)),
            ticks_accumulated=int(data.get("ticks_accumulated", 0)),
            moving=bool(data.get("moving", False)),
        )


def find_path(
    search_map: SearchMap,
    start: tuple[int, int],
    goal: tuple[int, int],
    actor_size: int = 1,
    max_iterations: int = 5000,
    door_keys: set[str] | None = None,
    actor_strength: int = 10,
) -> PathResult:
    start = _clamp_coord(search_map, start)
    goal = _clamp_coord(search_map, goal)
    cache_key = (search_map.cache_revision, start, goal, int(actor_size), frozenset(door_keys or set()), int(actor_strength))
    cached = search_map.path_cache.get(cache_key)
    if cached is not None:
        return PathResult(list(cached.path), cached.total_cost, cached.success, cached.tiles_explored)

    if not search_map.is_passable(*start, actor_size=actor_size, door_keys=door_keys, actor_strength=actor_strength):
        return PathResult([], math.inf, False, 0)
    if not search_map.is_passable(*goal, actor_size=actor_size, door_keys=door_keys, actor_strength=actor_strength):
        return PathResult([], math.inf, False, 0)

    open_heap: list[tuple[float, int, tuple[int, int]]] = []
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start: 0.0}
    closed: set[tuple[int, int]] = set()
    counter = 0
    heapq.heappush(open_heap, (_heuristic(start, goal), counter, start))
    explored = 0

    while open_heap:
        _f_score, _idx, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        closed.add(current)
        explored += 1
        if explored > int(max_iterations):
            result = PathResult([], math.inf, False, explored)
            search_map.cache_result(cache_key, result)
            return result
        if current == goal:
            path = _reconstruct_path(came_from, current)
            result = PathResult(path=path, total_cost=float(g_score[current]), success=True, tiles_explored=explored)
            search_map.cache_result(cache_key, result)
            return result

        for neighbor, step_cost in _neighbors(
            search_map,
            current,
            actor_size=actor_size,
            door_keys=door_keys,
            actor_strength=actor_strength,
        ):
            tentative = g_score[current] + step_cost
            if tentative < g_score.get(neighbor, math.inf):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                counter += 1
                heapq.heappush(open_heap, (tentative + _heuristic(neighbor, goal), counter, neighbor))

    result = PathResult([], math.inf, False, explored)
    search_map.cache_result(cache_key, result)
    return result


def tick_movement(
    actor: ActorRecord,
    movement: MovementState,
    search_map: SearchMap,
) -> tuple[tuple[int, int] | None, bool]:
    if not movement.moving or not movement.current_path or movement.is_complete():
        movement.moving = False
        return None, True

    movement.ticks_accumulated += 1
    if movement.ticks_accumulated < max(1, int(movement.ticks_per_tile)):
        return None, False

    next_tile = movement.next_tile()
    if next_tile is None:
        movement.moving = False
        return None, True
    if not search_map.is_passable(*next_tile, ignore_occupants=True):
        movement.moving = False
        return None, True

    search_map.set_occupant(actor.position.x, actor.position.y, None)
    actor.position.x, actor.position.y = int(next_tile[0]), int(next_tile[1])
    search_map.set_occupant(actor.position.x, actor.position.y, actor.identity.actor_id)
    movement.path_index += 1
    movement.ticks_accumulated = 0
    complete = movement.is_complete()
    if complete:
        movement.moving = False
    return next_tile, complete


def attempt_bump(
    actor: ActorRecord,
    blocked_tile: tuple[int, int],
    search_map: SearchMap,
    actors: dict[str, ActorRecord],
) -> bool:
    blocked_id = search_map.occupants.get((int(blocked_tile[0]), int(blocked_tile[1])))
    if blocked_id is None:
        return False
    other = actors.get(blocked_id)
    if other is None:
        return False
    if other.identity.faction_id != actor.identity.faction_id:
        return False
    if not bool(other.raw_payload.get("idle", True)):
        return False

    original = (int(actor.position.x), int(actor.position.y))
    search_map.set_occupant(original[0], original[1], other.identity.actor_id)
    search_map.set_occupant(int(blocked_tile[0]), int(blocked_tile[1]), actor.identity.actor_id)
    actor.position.x, actor.position.y = int(blocked_tile[0]), int(blocked_tile[1])
    other.position.x, other.position.y = original
    return True


def random_walk_target(
    actor_pos: tuple[int, int],
    search_map: SearchMap,
    radius: int = 10,
    rng: Random | None = None,
) -> tuple[int, int] | None:
    rng = rng or Random(0)
    candidates: list[tuple[int, int]] = []
    for y in range(max(0, actor_pos[1] - radius), min(search_map.height, actor_pos[1] + radius + 1)):
        for x in range(max(0, actor_pos[0] - radius), min(search_map.width, actor_pos[0] + radius + 1)):
            if (x, y) == actor_pos:
                continue
            if abs(x - actor_pos[0]) > radius or abs(y - actor_pos[1]) > radius:
                continue
            if search_map.is_passable(x, y):
                candidates.append((x, y))
    if not candidates:
        return None
    return candidates[rng.randrange(len(candidates))]


def compute_movement_speed(actor: ActorRecord, encumbrance_ratio: float) -> int:
    agility = int(actor.stats.get("AGI", actor.stats.get("DEX", 10)))
    base = max(1, 10 - max(0, (agility - 10) // 2))
    penalty = 0
    if float(encumbrance_ratio) > 0.75:
        penalty = math.ceil((float(encumbrance_ratio) - 0.75) / 0.25)
    return base + penalty


def _neighbors(
    search_map: SearchMap,
    current: tuple[int, int],
    *,
    actor_size: int,
    door_keys: set[str] | None,
    actor_strength: int,
) -> list[tuple[tuple[int, int], float]]:
    results: list[tuple[tuple[int, int], float]] = []
    directions = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
        (-1, -1),
        (1, -1),
        (-1, 1),
        (1, 1),
    ]
    for dx, dy in directions:
        nx, ny = current[0] + dx, current[1] + dy
        if not search_map.is_passable(
            nx,
            ny,
            actor_size=actor_size,
            door_keys=door_keys,
            actor_strength=actor_strength,
        ):
            continue
        diagonal = dx != 0 and dy != 0
        if diagonal:
            side_a = (current[0] + dx, current[1])
            side_b = (current[0], current[1] + dy)
            if not search_map.is_passable(*side_a, actor_size=actor_size, door_keys=door_keys, actor_strength=actor_strength):
                continue
            if not search_map.is_passable(*side_b, actor_size=actor_size, door_keys=door_keys, actor_strength=actor_strength):
                continue
        base_cost = search_map.terrain_cost(nx, ny, door_keys=door_keys, actor_strength=actor_strength)
        if math.isinf(base_cost):
            continue
        if diagonal:
            base_cost *= 1.414
        results.append(((nx, ny), float(base_cost)))
    return results


def _heuristic(start: tuple[int, int], goal: tuple[int, int]) -> float:
    dx = abs(goal[0] - start[0])
    dy = abs(goal[1] - start[1])
    diagonal = min(dx, dy)
    straight = max(dx, dy) - diagonal
    return (diagonal * 1.414) + straight


def _reconstruct_path(
    came_from: dict[tuple[int, int], tuple[int, int]],
    current: tuple[int, int],
) -> list[tuple[int, int]]:
    path: list[tuple[int, int]] = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path[1:]


def _clamp_coord(search_map: SearchMap, coord: tuple[int, int]) -> tuple[int, int]:
    x = min(max(0, int(coord[0])), search_map.width - 1)
    y = min(max(0, int(coord[1])), search_map.height - 1)
    return x, y

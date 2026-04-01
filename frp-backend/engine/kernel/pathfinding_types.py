from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


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


__all__ = ["MovementState", "PathResult", "SearchMap", "TilePassability"]

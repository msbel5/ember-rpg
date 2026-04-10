from __future__ import annotations

import hashlib
from typing import Any

from engine.map import MapData, TileType

from .behavior_tree import BehaviorContext, BehaviorNode, PriorityNode, Status

_PASSABLE_TILES = {
    TileType.FLOOR,
    TileType.CORRIDOR,
    TileType.DOOR,
    TileType.ROAD,
    TileType.STAIRS_DOWN,
    TileType.STAIRS_UP,
}

_DIRECTION_BY_VECTOR = {
    (-1, -1): "nw",
    (0, -1): "north",
    (1, -1): "ne",
    (-1, 0): "west",
    (0, 0): "south",
    (1, 0): "east",
    (-1, 1): "sw",
    (0, 1): "south",
    (1, 1): "se",
}


def _position_tuple(value: Any, fallback: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError):
            return fallback
    return fallback


def _current_hour(ctx: BehaviorContext) -> int:
    hour = getattr(getattr(ctx, "game_time", None), "hour", ctx.blackboard.get("current_hour", 0))
    try:
        return int(hour) % 24
    except (TypeError, ValueError):
        return 0


def _current_tick(ctx: BehaviorContext) -> int:
    try:
        return int(ctx.blackboard.get("visual_tick_index", 0))
    except (TypeError, ValueError):
        return 0


def _set_entity_facing(entity: Any, facing: str) -> None:
    setattr(entity, "facing", str(facing or "south"))


def _set_entity_state(entity: Any, state: str) -> None:
    setattr(entity, "state", str(state or "stand"))


def _map_dimensions(map_data: Any) -> tuple[int, int]:
    if isinstance(map_data, MapData):
        return (int(map_data.width), int(map_data.height))
    if isinstance(map_data, dict):
        tiles = map_data.get("tiles", [])
        height = len(tiles) if isinstance(tiles, list) else 0
        width = len(tiles[0]) if height and isinstance(tiles[0], list) else 0
        return (width, height)
    return (0, 0)


def _tile_at(map_data: Any, x: int, y: int) -> Any:
    if isinstance(map_data, MapData):
        return map_data.get_tile(int(x), int(y))
    if isinstance(map_data, dict):
        tiles = map_data.get("tiles", [])
        if isinstance(tiles, list) and 0 <= int(y) < len(tiles) and isinstance(tiles[int(y)], list) and 0 <= int(x) < len(tiles[int(y)]):
            return tiles[int(y)][int(x)]
    return TileType.WALL


def _is_passable(map_data: Any, position: tuple[int, int]) -> bool:
    width, height = _map_dimensions(map_data)
    if width > 0 and height > 0:
        if position[0] < 0 or position[1] < 0 or position[0] >= width or position[1] >= height:
            return False
    if map_data is None:
        return True
    tile = _tile_at(map_data, position[0], position[1])
    if isinstance(tile, dict):
        return bool(tile.get("passable", False))
    if isinstance(tile, TileType):
        return tile in _PASSABLE_TILES
    return str(tile).lower() not in {"wall", "water", "tree"}


def _facing_for_points(origin: tuple[int, int], target: tuple[int, int]) -> str:
    dx = 0 if target[0] == origin[0] else (1 if target[0] > origin[0] else -1)
    dy = 0 if target[1] == origin[1] else (1 if target[1] > origin[1] else -1)
    return _DIRECTION_BY_VECTOR.get((dx, dy), "south")


def _deterministic_index(seed_parts: list[str], size: int) -> int:
    if size <= 0:
        return 0
    seed = "|".join(seed_parts).encode("utf-8")
    digest = hashlib.sha1(seed).hexdigest()
    return int(digest[:8], 16) % size


def _step_candidates(position: tuple[int, int], target: tuple[int, int]) -> list[tuple[int, int]]:
    dx = 0 if target[0] == position[0] else (1 if target[0] > position[0] else -1)
    dy = 0 if target[1] == position[1] else (1 if target[1] > position[1] else -1)
    candidates: list[tuple[int, int]] = []
    if dx != 0 or dy != 0:
        candidates.append((position[0] + dx, position[1] + dy))
    if dx != 0:
        candidates.append((position[0] + dx, position[1]))
    if dy != 0:
        candidates.append((position[0], position[1] + dy))
    for extra_dx in (-1, 0, 1):
        for extra_dy in (-1, 0, 1):
            if extra_dx == 0 and extra_dy == 0:
                continue
            candidate = (position[0] + extra_dx, position[1] + extra_dy)
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def step_toward(position: tuple[int, int], target: tuple[int, int], map_data: Any) -> tuple[int, int]:
    if position == target:
        return position
    try:
        from engine.world.pathfinding import find_path  # type: ignore

        if callable(find_path):
            path = find_path(position, target, map_data)
            if isinstance(path, list) and len(path) >= 2:
                return _position_tuple(path[1], fallback=position)
    except Exception:
        pass
    for candidate in _step_candidates(position, target):
        if _is_passable(map_data, candidate):
            return candidate
    return position


class GoToWaypointNode(BehaviorNode):
    def __init__(self, target: tuple[int, int], name: str = "GoToWaypoint") -> None:
        super().__init__(name)
        self.target = _position_tuple(target)

    def tick(self, ctx: BehaviorContext) -> Status:
        entity = ctx.entity
        origin = _position_tuple(getattr(entity, "position", (0, 0)))
        if origin == self.target:
            _set_entity_state(entity, "stand")
            return Status.SUCCESS
        next_pos = step_toward(origin, self.target, ctx.map_data)
        _set_entity_facing(entity, _facing_for_points(origin, self.target))
        ctx.blackboard["target_pos"] = self.target
        if next_pos == origin:
            _set_entity_state(entity, "stand")
            return Status.FAILURE
        entity.position = next_pos
        _set_entity_state(entity, "walk")
        return Status.RUNNING


class FaceTargetNode(BehaviorNode):
    def __init__(self, target: tuple[int, int], name: str = "FaceTarget") -> None:
        super().__init__(name)
        self.target = _position_tuple(target)

    def tick(self, ctx: BehaviorContext) -> Status:
        origin = _position_tuple(getattr(ctx.entity, "position", (0, 0)))
        facing = _facing_for_points(origin, self.target)
        _set_entity_facing(ctx.entity, facing)
        ctx.blackboard["facing"] = facing
        return Status.SUCCESS


class WaitNode(BehaviorNode):
    def __init__(self, ticks: int, name: str = "Wait") -> None:
        super().__init__(name)
        self.ticks = max(0, int(ticks))

    def tick(self, ctx: BehaviorContext) -> Status:
        counter_key = f"{self.name}_elapsed"
        elapsed = int(ctx.blackboard.get(counter_key, 0))
        if elapsed < self.ticks:
            ctx.blackboard[counter_key] = elapsed + 1
            _set_entity_state(ctx.entity, "stand")
            return Status.RUNNING
        ctx.blackboard[counter_key] = 0
        return Status.SUCCESS


class FollowScheduleNode(BehaviorNode):
    def __init__(self, schedule: dict[int, str], waypoints: dict[str, tuple[int, int]], name: str = "FollowSchedule") -> None:
        super().__init__(name)
        self.schedule = {int(hour) % 24: str(name) for hour, name in dict(schedule).items()}
        self.waypoints = {str(key): _position_tuple(value) for key, value in dict(waypoints).items()}

    def tick(self, ctx: BehaviorContext) -> Status:
        if not self.schedule:
            return Status.FAILURE
        hour = _current_hour(ctx)
        waypoint_name: str | None = None
        for offset in range(24):
            candidate_hour = (hour - offset) % 24
            if candidate_hour in self.schedule:
                waypoint_name = self.schedule[candidate_hour]
                ctx.blackboard["schedule_hour"] = candidate_hour
                break
        if waypoint_name is None:
            return Status.FAILURE
        target = self.waypoints.get(waypoint_name)
        if target is None:
            return Status.FAILURE
        ctx.blackboard["schedule_waypoint"] = waypoint_name
        result = GoToWaypointNode(target).tick(ctx)
        if result == Status.SUCCESS:
            _set_entity_state(ctx.entity, "stand")
        return result


class SleepAtNightNode(BehaviorNode):
    def __init__(self, bed: tuple[int, int], night_hours: range, name: str = "SleepAtNight") -> None:
        super().__init__(name)
        self.bed = _position_tuple(bed)
        self.night_hours = range(night_hours.start, night_hours.stop, night_hours.step)

    def tick(self, ctx: BehaviorContext) -> Status:
        if _current_hour(ctx) not in self.night_hours:
            return Status.FAILURE
        result = GoToWaypointNode(self.bed).tick(ctx)
        if result == Status.FAILURE:
            return Status.FAILURE
        if _position_tuple(getattr(ctx.entity, "position", (0, 0))) == self.bed:
            _set_entity_state(ctx.entity, "sleep")
            return Status.SUCCESS
        return Status.RUNNING


class WanderInBoundsNode(BehaviorNode):
    def __init__(self, center: tuple[int, int], radius: int, step_cadence: int = 15, name: str = "WanderInBounds") -> None:
        super().__init__(name)
        self.center = _position_tuple(center)
        self.radius = max(0, int(radius))
        self.step_cadence = max(1, int(step_cadence))

    def _candidate_tiles(self, ctx: BehaviorContext) -> list[tuple[int, int]]:
        candidates: list[tuple[int, int]] = []
        for y in range(self.center[1] - self.radius, self.center[1] + self.radius + 1):
            for x in range(self.center[0] - self.radius, self.center[0] + self.radius + 1):
                if max(abs(x - self.center[0]), abs(y - self.center[1])) > self.radius:
                    continue
                candidate = (x, y)
                if candidate == _position_tuple(getattr(ctx.entity, "position", (0, 0))):
                    continue
                if _is_passable(ctx.map_data, candidate):
                    candidates.append(candidate)
        return candidates

    def tick(self, ctx: BehaviorContext) -> Status:
        current_tick = _current_tick(ctx)
        last_step_tick = int(ctx.blackboard.get("last_step_tick", -self.step_cadence))
        target_key = f"{self.name}_target"
        target = _position_tuple(ctx.blackboard.get(target_key), fallback=self.center)
        entity_position = _position_tuple(getattr(ctx.entity, "position", (0, 0)))

        if target != self.center or ctx.blackboard.get(target_key) is not None:
            if entity_position == target:
                ctx.blackboard.pop(target_key, None)
                _set_entity_state(ctx.entity, "stand")
                return Status.SUCCESS
            if current_tick - last_step_tick < self.step_cadence:
                _set_entity_state(ctx.entity, "walk")
                return Status.RUNNING
            result = GoToWaypointNode(target).tick(ctx)
            if _position_tuple(getattr(ctx.entity, "position", (0, 0))) != entity_position:
                ctx.blackboard["last_step_tick"] = current_tick
            if result == Status.SUCCESS:
                ctx.blackboard.pop(target_key, None)
            return result

        if current_tick - last_step_tick < self.step_cadence:
            _set_entity_state(ctx.entity, "stand")
            return Status.SUCCESS

        candidates = self._candidate_tiles(ctx)
        if not candidates:
            return Status.FAILURE
        index = _deterministic_index(
            [str(getattr(ctx.entity, "id", "npc")), str(current_tick), self.name, str(self.center), str(self.radius)],
            len(candidates),
        )
        target = candidates[index]
        ctx.blackboard[target_key] = target
        result = GoToWaypointNode(target).tick(ctx)
        if _position_tuple(getattr(ctx.entity, "position", (0, 0))) != entity_position:
            ctx.blackboard["last_step_tick"] = current_tick
        return result


def build_default_ambient_tree(npc_record: dict[str, Any]) -> BehaviorNode:
    record = dict(npc_record)
    ambient_profile = dict(record.get("ambient_profile", {})) if isinstance(record.get("ambient_profile"), dict) else {}
    waypoints = dict(record.get("waypoints", ambient_profile.get("waypoints", {})))
    schedule = dict(ambient_profile.get("schedule", {}))
    home_tile = _position_tuple(ambient_profile.get("home_tile", record.get("position", (0, 0))))
    wander_center = _position_tuple(ambient_profile.get("wander_center", home_tile))
    wander_radius = int(ambient_profile.get("wander_radius", 4) or 4)
    night_hours = ambient_profile.get("night_hours", range(22, 24))
    if isinstance(night_hours, list):
        hours = [int(hour) % 24 for hour in night_hours]
        start = hours[0] if hours else 22
        stop = (hours[-1] + 1) if hours else 24
        night_hours = range(start, stop)
    return PriorityNode(
        [
            SleepAtNightNode(home_tile, night_hours),
            FollowScheduleNode(schedule=schedule, waypoints=waypoints),
            WanderInBoundsNode(center=wander_center, radius=wander_radius),
        ],
        name="AmbientLife",
    )


__all__ = [
    "FaceTargetNode",
    "FollowScheduleNode",
    "GoToWaypointNode",
    "SleepAtNightNode",
    "WaitNode",
    "WanderInBoundsNode",
    "build_default_ambient_tree",
    "step_toward",
]

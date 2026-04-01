from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord
from engine.kernel.common import serialize_value
from engine.kernel.pathfinding import SearchMap, TilePassability


@dataclass
class RegionDef:
    region_id: str
    region_type: str
    bounds: tuple[int, int, int, int]
    destination_area_id: str = ""
    destination_pos: tuple[int, int] = (0, 0)
    trigger_once: bool = True
    detect_difficulty: int = 0
    disarm_difficulty: int = 0
    effect_def_ids: list[str] = field(default_factory=list)
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegionDef":
        payload = dict(data)
        payload["bounds"] = tuple(int(value) for value in payload.get("bounds", (0, 0, 0, 0)))
        payload["destination_pos"] = tuple(int(value) for value in payload.get("destination_pos", (0, 0)))
        payload["effect_def_ids"] = [str(item) for item in payload.get("effect_def_ids", [])]
        return cls(**payload)


@dataclass
class ContainerDef:
    container_id: str
    position: tuple[int, int]
    inventory: list[dict] = field(default_factory=list)
    locked: bool = False
    lock_difficulty: int = 0
    key_id: str = ""
    trapped: bool = False
    trap_effect_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContainerDef":
        payload = dict(data)
        payload["position"] = tuple(int(value) for value in payload.get("position", (0, 0)))
        payload["inventory"] = [dict(item) for item in payload.get("inventory", [])]
        payload["trap_effect_ids"] = [str(item) for item in payload.get("trap_effect_ids", [])]
        return cls(**payload)


@dataclass
class DoorDef:
    door_id: str
    position: tuple[int, int]
    open: bool = False
    locked: bool = False
    lock_difficulty: int = 0
    key_id: str = ""
    force_difficulty: int = 20
    trapped: bool = False
    trap_effect_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DoorDef":
        payload = dict(data)
        payload["position"] = tuple(int(value) for value in payload.get("position", (0, 0)))
        payload["trap_effect_ids"] = [str(item) for item in payload.get("trap_effect_ids", [])]
        return cls(**payload)


@dataclass
class SpawnPointDef:
    spawn_id: str
    position: tuple[int, int]
    creature_def_ids: list[str] = field(default_factory=list)
    max_count: int = 3
    spawn_interval_ticks: int = 100
    schedule_start_hour: int = 0
    schedule_end_hour: int = 24
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpawnPointDef":
        payload = dict(data)
        payload["position"] = tuple(int(value) for value in payload.get("position", (0, 0)))
        payload["creature_def_ids"] = [str(item) for item in payload.get("creature_def_ids", [])]
        return cls(**payload)


@dataclass
class RoomDef:
    room_id: str
    room_type: str
    bounds: tuple[int, int, int, int]
    furniture_ids: list[str] = field(default_factory=list)
    assigned_actor_id: str | None = None
    quality: int = 0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomDef":
        payload = dict(data)
        payload["bounds"] = tuple(int(value) for value in payload.get("bounds", (0, 0, 0, 0)))
        payload["furniture_ids"] = [str(item) for item in payload.get("furniture_ids", [])]
        return cls(**payload)


@dataclass
class AreaDef:
    area_id: str
    label: str
    width: int
    height: int
    regions: list[RegionDef] = field(default_factory=list)
    containers: list[ContainerDef] = field(default_factory=list)
    doors: list[DoorDef] = field(default_factory=list)
    spawn_points: list[SpawnPointDef] = field(default_factory=list)
    rooms: list[RoomDef] = field(default_factory=list)
    day_night_enabled: bool = True
    connected_areas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AreaDef":
        payload = dict(data)
        payload["regions"] = [RegionDef.from_dict(item) for item in payload.get("regions", [])]
        payload["containers"] = [ContainerDef.from_dict(item) for item in payload.get("containers", [])]
        payload["doors"] = [DoorDef.from_dict(item) for item in payload.get("doors", [])]
        payload["spawn_points"] = [SpawnPointDef.from_dict(item) for item in payload.get("spawn_points", [])]
        payload["rooms"] = [RoomDef.from_dict(item) for item in payload.get("rooms", [])]
        payload["connected_areas"] = [str(item) for item in payload.get("connected_areas", [])]
        return cls(**payload)


@dataclass
class AreaState:
    area_id: str
    current_hour: int = 12
    doors_state: dict[str, bool] = field(default_factory=dict)
    containers_looted: dict[str, bool] = field(default_factory=dict)
    traps_triggered: dict[str, bool] = field(default_factory=dict)
    spawn_counts: dict[str, int] = field(default_factory=dict)
    spawn_cooldowns: dict[str, int] = field(default_factory=dict)
    explored_tiles: set[tuple[int, int]] = field(default_factory=set)
    room_assignments: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "area_id": self.area_id,
            "current_hour": int(self.current_hour),
            "doors_state": {str(key): bool(value) for key, value in self.doors_state.items()},
            "containers_looted": {str(key): bool(value) for key, value in self.containers_looted.items()},
            "traps_triggered": {str(key): bool(value) for key, value in self.traps_triggered.items()},
            "spawn_counts": {str(key): int(value) for key, value in self.spawn_counts.items()},
            "spawn_cooldowns": {str(key): int(value) for key, value in self.spawn_cooldowns.items()},
            "explored_tiles": [[x, y] for x, y in sorted(self.explored_tiles)],
            "room_assignments": {str(key): str(value) for key, value in self.room_assignments.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AreaState":
        return cls(
            area_id=str(data["area_id"]),
            current_hour=int(data.get("current_hour", 12)),
            doors_state={str(key): bool(value) for key, value in dict(data.get("doors_state", {})).items()},
            containers_looted={str(key): bool(value) for key, value in dict(data.get("containers_looted", {})).items()},
            traps_triggered={str(key): bool(value) for key, value in dict(data.get("traps_triggered", {})).items()},
            spawn_counts={str(key): int(value) for key, value in dict(data.get("spawn_counts", {})).items()},
            spawn_cooldowns={str(key): int(value) for key, value in dict(data.get("spawn_cooldowns", {})).items()},
            explored_tiles={tuple(int(v) for v in item) for item in data.get("explored_tiles", [])},
            room_assignments={str(key): str(value) for key, value in dict(data.get("room_assignments", {})).items()},
        )


def open_door(actor: ActorRecord, door: DoorDef, area_state: AreaState, search_map: SearchMap) -> tuple[bool, str]:
    has_key = _actor_has_key(actor, door.key_id)
    lockpick = int(actor.skills.get("lockpick", 0))
    strength = int(actor.stats.get("STR", actor.stats.get("MIG", 10)))
    if door.locked and not has_key and lockpick < int(door.lock_difficulty) and strength < int(door.force_difficulty):
        return False, "door remains locked"

    area_state.doors_state[door.door_id] = True
    door.open = True
    search_map.tiles[door.position[1]][door.position[0]] = TilePassability.DOOR_OPEN
    message = "door opened"
    if door.trapped:
        area_state.traps_triggered[door.door_id] = True
        message = f"{message}; trap triggered: {', '.join(door.trap_effect_ids)}"
    return True, message


def open_container(actor: ActorRecord, container: ContainerDef, area_state: AreaState) -> tuple[bool, list[dict], str]:
    has_key = _actor_has_key(actor, container.key_id)
    lockpick = int(actor.skills.get("lockpick", 0))
    if container.locked and not has_key and lockpick < int(container.lock_difficulty):
        return False, [], "container locked"

    if container.trapped:
        area_state.traps_triggered[container.container_id] = True
    area_state.containers_looted[container.container_id] = True
    return True, [dict(item) for item in container.inventory], "opened"


def tick_spawns(area_def: AreaDef, area_state: AreaState, current_tick: int) -> list[dict]:
    events: list[dict] = []
    for spawn in area_def.spawn_points:
        if not spawn.enabled:
            continue
        if not _hour_in_schedule(area_state.current_hour, spawn.schedule_start_hour, spawn.schedule_end_hour):
            continue
        current_count = int(area_state.spawn_counts.get(spawn.spawn_id, 0))
        if current_count >= int(spawn.max_count):
            continue
        ready_tick = int(area_state.spawn_cooldowns.get(spawn.spawn_id, 0))
        if int(current_tick) < ready_tick:
            continue
        creature_id = spawn.creature_def_ids[0] if spawn.creature_def_ids else ""
        if not creature_id:
            continue
        area_state.spawn_counts[spawn.spawn_id] = current_count + 1
        area_state.spawn_cooldowns[spawn.spawn_id] = int(current_tick) + int(spawn.spawn_interval_ticks)
        events.append(
            {
                "type": "spawn",
                "spawn_id": spawn.spawn_id,
                "creature_def_id": creature_id,
                "position": tuple(spawn.position),
            }
        )
    return events


def check_region_entry(actor_pos: tuple[int, int], area_def: AreaDef, area_state: AreaState) -> list[dict]:
    events: list[dict] = []
    for region in area_def.regions:
        if not _point_in_bounds(actor_pos, region.bounds):
            continue
        if region.region_type == "travel":
            events.append(
                {
                    "type": "travel",
                    "region_id": region.region_id,
                    "destination_area_id": region.destination_area_id,
                    "destination_pos": tuple(region.destination_pos),
                }
            )
        elif region.region_type == "trap":
            if region.trigger_once and area_state.traps_triggered.get(region.region_id, False):
                continue
            area_state.traps_triggered[region.region_id] = True
            events.append({"type": "trap", "region_id": region.region_id, "effect_def_ids": list(region.effect_def_ids)})
        elif region.region_type == "info":
            events.append({"type": "info", "region_id": region.region_id, "text": region.text})
    return events


def compute_room_quality(room: RoomDef, furniture_defs: dict) -> int:
    x, y, width, height = room.bounds
    size_bonus = max(0, int(width) * int(height) // 4)
    furniture_bonus = sum(int(furniture_defs.get(item_id, 1)) for item_id in room.furniture_ids)
    type_bonus = {
        "bedroom": 4,
        "dining": 3,
        "workshop": 2,
        "hospital": 5,
        "temple": 4,
        "meeting_hall": 2,
        "stockpile": 1,
        "barracks": 2,
    }.get(room.room_type, 0)
    return int(room.quality) + size_bonus + furniture_bonus + type_bonus


def assign_room(actor_id: str, room_id: str, area_state: AreaState) -> None:
    area_state.room_assignments[str(room_id)] = str(actor_id)


def apply_room_assignment_bonus(actor_id: str, room: RoomDef, area_state: AreaState) -> int:
    if area_state.room_assignments.get(room.room_id) != actor_id:
        return 0
    quality = int(room.quality)
    if room.room_type == "bedroom":
        return max(1, quality // 5)
    if room.room_type == "dining":
        return max(1, quality // 6)
    if room.room_type == "workshop":
        return max(1, quality // 7)
    if room.room_type == "hospital":
        return max(1, quality // 4)
    return max(0, quality // 10)


def update_fog_of_war(actor_pos: tuple[int, int], visual_range: int, area_state: AreaState) -> set[tuple[int, int]]:
    newly_explored: set[tuple[int, int]] = set()
    for y in range(actor_pos[1] - visual_range, actor_pos[1] + visual_range + 1):
        for x in range(actor_pos[0] - visual_range, actor_pos[0] + visual_range + 1):
            tile = (int(x), int(y))
            if tile not in area_state.explored_tiles:
                newly_explored.add(tile)
                area_state.explored_tiles.add(tile)
    return newly_explored


def transition_area(actor: ActorRecord, region: RegionDef) -> dict:
    return {
        "destination_area_id": region.destination_area_id,
        "destination_pos": tuple(region.destination_pos),
        "source_actor_id": actor.identity.actor_id,
    }


def day_night_state(area_state: AreaState) -> str:
    hour = int(area_state.current_hour) % 24
    return "day" if 6 <= hour <= 18 else "night"


def _actor_has_key(actor: ActorRecord, key_id: str) -> bool:
    if not key_id:
        return False
    return any(getattr(item, "item_def_id", "") == key_id for item in actor.inventory)


def _point_in_bounds(point: tuple[int, int], bounds: tuple[int, int, int, int]) -> bool:
    x, y = point
    bx, by, width, height = bounds
    return bx <= x < bx + width and by <= y < by + height


def _hour_in_schedule(current_hour: int, start_hour: int, end_hour: int) -> bool:
    current = int(current_hour) % 24
    start = int(start_hour) % 24
    end = int(end_hour) % 24
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end

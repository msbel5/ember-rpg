# PRD: Area & Map System V1
**Project:** Ember RPG
**Phase:** 2
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the local area/map kernel synthesizing GemRB M10 (Area — search map, regions, containers, doors, spawn points, ambient, day/night) with DF M16 (Building/Room — room types, furniture placement, meeting areas, dormitory/dining assignment). An area is a self-contained map (settlement, dungeon, wilderness) with tile grid, interactive objects, spawn logic, and environmental state.

## 2. Scope

### In scope
- `AreaDef`: static area template (size, tile grid, regions, objects, spawns, ambient)
- `AreaState`: runtime area state (doors open/closed, containers looted, spawns active, time)
- Tile grid: passability from Pathfinding PRD, plus height map and light map
- Regions: InfoPoint (travel, trap, info), Container, Door, SpawnPoint
- Containers: inventory (loot), locked, trapped
- Doors: open/closed, locked/unlocked, trapped, key requirement
- Spawn points: creature spawn with schedule, frequency, max count, enabled flag
- Day/night cycle: time-of-day affects lighting, NPC schedules, spawn activation
- Room/zone types (DF): bedroom, dining, workshop, hospital, temple, meeting_hall, stockpile, barracks
- Room assignment: actors assigned to rooms, quality scoring
- Fog of war: tiles explored/unexplored per player
- Area transitions: travel regions linking to other areas

### Out of scope
- Area visual rendering (Godot client handles this)
- Background music/ambient sound selection
- Map editor

## 3. Functional Requirements (FR)

**FR-01 (AreaDef):** Defines: area_id, label, width, height, tile_grid (from SearchMap), regions, containers, doors, spawn_points, ambient_flags, day_night_enabled, connected_areas.

**FR-02 (Regions):** Three region types:
- TRAVEL: boundary that transitions to another area. Has destination_area_id and destination_position.
- TRAP: area that triggers effect when entered. Has trigger_once flag, detect_difficulty, disarm_difficulty, effect_def_ids.
- INFO: displays text/tooltip when entered. Has text template.

**FR-03 (Containers):** Loot containers: inventory (list of ItemInstance), locked (bool), lock_difficulty, key_id, trapped (bool), trap_effect_ids. `open_container(actor, container)` checks lock → check trap → reveal inventory.

**FR-04 (Doors):** State: open/closed/locked/trapped. Opening a locked door: require key_id OR `lockpick_skill >= lock_difficulty` OR `STR >= force_difficulty`. Trapped doors trigger effects on open attempt without disarm. Door state changes update SearchMap passability.

**FR-05 (Spawn Points):** Each spawn point: creature_def_ids, max_count, spawn_interval_ticks, schedule (active hours), enabled. Each tick: if enabled AND within schedule AND current_count < max_count AND spawn_cooldown expired → spawn creature at position.

**FR-06 (Day/Night):** Area tracks current_hour (0-23). Day (6-18): normal lighting. Night (19-5): reduced visibility, different NPC schedules active, some spawns only at night. Light sources (torches, magic) create illuminated radius.

**FR-07 (Room/Zone System):** Rooms defined as rectangular regions with type: bedroom, dining, workshop, hospital, temple, meeting_hall, stockpile, barracks. Room quality: `quality = base + furniture_bonus + size_bonus + cleanliness`. Actors assigned to rooms gain morale bonuses/penalties based on quality.

**FR-08 (Room Assignment):** `assign_room(actor, room)`: actor gets ownership. Bedroom: reduces stress. Dining: eating buff. Workshop: crafting speed bonus. Hospital: healing rate bonus. Unassigned actors use communal rooms at lower quality.

**FR-09 (Fog of War):** Per-player explored tiles set. Entering a tile marks it and surrounding tiles (visual range) as explored. Actors/objects in unexplored tiles are hidden from player. Pathfinding ignores FoW (actors know the map).

**FR-10 (Area Transition):** When actor enters TRAVEL region: check transition conditions → save current area state → load destination area → place actor at destination_position.

**FR-11 (Serialization):** AreaDef (static, loaded from data), AreaState (runtime) both round-trip via to_dict()/from_dict().

## 4. Data Structures

```python
@dataclass
class RegionDef:
    region_id: str
    region_type: str         # "travel" | "trap" | "info"
    bounds: tuple[int, int, int, int]  # x, y, width, height
    # Travel
    destination_area_id: str = ""
    destination_pos: tuple[int, int] = (0, 0)
    # Trap
    trigger_once: bool = True
    detect_difficulty: int = 0
    disarm_difficulty: int = 0
    effect_def_ids: list[str] = field(default_factory=list)
    # Info
    text: str = ""

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class ContainerDef:
    container_id: str
    position: tuple[int, int]
    inventory: list[dict] = field(default_factory=list)  # [{item_def_id, quantity, material_id}]
    locked: bool = False
    lock_difficulty: int = 0
    key_id: str = ""
    trapped: bool = False
    trap_effect_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...


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

    def to_dict(self) -> dict[str, Any]: ...


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

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class RoomDef:
    room_id: str
    room_type: str           # "bedroom" | "dining" | "workshop" | "hospital" | "temple" | "meeting_hall" | "stockpile" | "barracks"
    bounds: tuple[int, int, int, int]
    furniture_ids: list[str] = field(default_factory=list)
    assigned_actor_id: str | None = None
    quality: int = 0

    def to_dict(self) -> dict[str, Any]: ...


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

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AreaDef": ...


@dataclass
class AreaState:
    area_id: str
    current_hour: int = 12
    doors_state: dict[str, bool] = field(default_factory=dict)  # door_id → open
    containers_looted: dict[str, bool] = field(default_factory=dict)
    traps_triggered: dict[str, bool] = field(default_factory=dict)
    spawn_counts: dict[str, int] = field(default_factory=dict)
    spawn_cooldowns: dict[str, int] = field(default_factory=dict)
    explored_tiles: set[tuple[int, int]] = field(default_factory=set)
    room_assignments: dict[str, str] = field(default_factory=dict)  # room_id → actor_id

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AreaState": ...
```

## 5. Public API

```python
def open_door(actor: ActorRecord, door: DoorDef, area_state: AreaState, search_map: "SearchMap") -> tuple[bool, str]:
    """Attempt to open door. Returns (success, message)."""

def open_container(actor: ActorRecord, container: ContainerDef, area_state: AreaState) -> tuple[bool, list[dict], str]:
    """Open container. Returns (success, items_revealed, message)."""

def tick_spawns(area_def: AreaDef, area_state: AreaState, current_tick: int) -> list[dict]:
    """Tick spawn points. Returns list of spawn events."""

def check_region_entry(actor_pos: tuple[int, int], area_def: AreaDef, area_state: AreaState) -> list[dict]:
    """Check if actor position triggers any region. Returns events."""

def compute_room_quality(room: RoomDef, furniture_defs: dict) -> int:
    """Compute room quality from size + furniture + type bonuses."""

def assign_room(actor_id: str, room_id: str, area_state: AreaState) -> None:
    """Assign actor to room."""

def update_fog_of_war(actor_pos: tuple[int, int], visual_range: int, area_state: AreaState) -> set[tuple[int, int]]:
    """Mark tiles as explored. Returns newly explored tiles."""

def transition_area(actor: ActorRecord, region: RegionDef) -> dict:
    """Execute area transition. Returns {destination_area_id, destination_pos}."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-04]: Given locked door with key_id="gold_key" and actor has that item, when open_door called, door opens.
AC-02 [FR-04]: Given locked door and actor without key but lockpick=15 >= difficulty=12, door opens.
AC-03 [FR-04]: Given trapped door, when opened without disarm, trap effects trigger.
AC-04 [FR-03]: Given locked container with lock_difficulty=20 and actor lockpick=18, open fails.
AC-05 [FR-05]: Given spawn with max_count=3 and current_count=2, within schedule, cooldown expired, one creature spawns.
AC-06 [FR-05]: Given spawn outside schedule hours, no spawn occurs.
AC-07 [FR-06]: Given area at hour=22 (night), day_night state is "night".
AC-08 [FR-07]: Given bedroom with quality=15 assigned to actor, actor gains morale bonus.
AC-09 [FR-09]: Given actor at (10,10) with visual_range=5, tiles (5-15, 5-15) become explored.
AC-10 [FR-11]: AreaState round-trip via to_dict()/from_dict() preserves all state.

## 7-10. (Performance, Errors, Integration, Tests)
- tick_spawns for 20 spawn points: < 1 ms
- Integration: Pathfinding (SearchMap), Settlement Generator (initial area layout), Item System (container inventory), Effect System (trap effects), Colony (room quality → morale)
- Tests: all door states, container lock/trap, spawn schedule, day/night, room assignment, fog of war, area transition, serialization round-trip

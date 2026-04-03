from __future__ import annotations

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.area import (
    AreaDef,
    AreaState,
    ContainerDef,
    DoorDef,
    RegionDef,
    RoomDef,
    SpawnPointDef,
    apply_room_assignment_bonus,
    assign_room,
    check_region_entry,
    day_night_state,
    open_container,
    open_door,
    tick_spawns,
    transition_area,
    update_fog_of_war,
)
from engine.kernel.items import ItemInstance
from engine.kernel.pathfinding import SearchMap, TilePassability


def _actor(
    actor_id: str,
    *,
    strength: int = 10,
    lockpick: int = 0,
    inventory: list[ItemInstance] | None = None,
) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="pc"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"MIG": strength},
        skills={"lockpick": lockpick},
        inventory=inventory or [],
        raw_payload={},
    )


def _search_map() -> SearchMap:
    return SearchMap(
        width=10,
        height=10,
        tiles=[[TilePassability.NORMAL for _x in range(10)] for _y in range(10)],
    )


def test_ac01_open_door_succeeds_with_matching_key():
    actor = _actor("pc", inventory=[ItemInstance(instance_id="k1", item_def_id="gold_key")])
    door = DoorDef(door_id="door_1", position=(3, 3), locked=True, key_id="gold_key")
    area_state = AreaState(area_id="area_1")
    search_map = _search_map()
    search_map.tiles[3][3] = TilePassability.DOOR_CLOSED

    success, _message = open_door(actor, door, area_state, search_map)

    assert success is True
    assert area_state.doors_state["door_1"] is True
    assert search_map.tiles[3][3] == TilePassability.DOOR_OPEN


def test_ac02_open_door_succeeds_with_lockpick_skill():
    actor = _actor("pc", lockpick=15)
    door = DoorDef(door_id="door_1", position=(3, 3), locked=True, lock_difficulty=12)
    area_state = AreaState(area_id="area_1")
    search_map = _search_map()
    search_map.tiles[3][3] = TilePassability.DOOR_CLOSED

    success, _message = open_door(actor, door, area_state, search_map)

    assert success is True


def test_ac03_trapped_door_triggers_trap_effects_on_open():
    actor = _actor("pc", strength=18)
    door = DoorDef(
        door_id="door_trap",
        position=(2, 2),
        locked=False,
        trapped=True,
        trap_effect_ids=["poison_needle"],
    )
    area_state = AreaState(area_id="area_1")
    search_map = _search_map()
    search_map.tiles[2][2] = TilePassability.DOOR_CLOSED

    success, message = open_door(actor, door, area_state, search_map)

    assert success is True
    assert area_state.traps_triggered["door_trap"] is True
    assert "poison_needle" in message


def test_ac04_locked_container_fails_when_lockpick_too_low():
    actor = _actor("pc", lockpick=18)
    container = ContainerDef(container_id="chest_1", position=(1, 1), locked=True, lock_difficulty=20)
    area_state = AreaState(area_id="area_1")

    success, items, _message = open_container(actor, container, area_state)

    assert success is False
    assert items == []


def test_ac05_tick_spawns_emits_event_when_within_schedule_and_capacity():
    area_def = AreaDef(
        area_id="area_1",
        label="Area",
        width=10,
        height=10,
        spawn_points=[
            SpawnPointDef(
                spawn_id="spawn_1",
                position=(4, 4),
                creature_def_ids=["wolf", "boar"],
                max_count=3,
                spawn_interval_ticks=100,
                schedule_start_hour=0,
                schedule_end_hour=23,
            )
        ],
    )
    area_state = AreaState(area_id="area_1", current_hour=12, spawn_counts={"spawn_1": 2}, spawn_cooldowns={"spawn_1": 0})

    events = tick_spawns(area_def, area_state, current_tick=150)

    assert len(events) == 1
    assert events[0]["creature_def_id"] == "wolf"
    assert area_state.spawn_counts["spawn_1"] == 3


def test_ac06_tick_spawns_skips_when_outside_schedule():
    area_def = AreaDef(
        area_id="area_1",
        label="Area",
        width=10,
        height=10,
        spawn_points=[
            SpawnPointDef(
                spawn_id="spawn_1",
                position=(4, 4),
                creature_def_ids=["wolf"],
                max_count=3,
                spawn_interval_ticks=100,
                schedule_start_hour=18,
                schedule_end_hour=22,
            )
        ],
    )
    area_state = AreaState(area_id="area_1", current_hour=9, spawn_counts={"spawn_1": 0}, spawn_cooldowns={"spawn_1": 0})

    events = tick_spawns(area_def, area_state, current_tick=150)

    assert events == []


def test_ac07_day_night_state_reports_night_at_22():
    assert day_night_state(AreaState(area_id="area_1", current_hour=22)) == "night"


def test_ac08_assigned_bedroom_quality_grants_morale_bonus():
    area_state = AreaState(area_id="area_1")
    room = RoomDef(room_id="room_1", room_type="bedroom", bounds=(0, 0, 3, 3), quality=15)

    assign_room("pc", "room_1", area_state)
    bonus = apply_room_assignment_bonus("pc", room, area_state)

    assert bonus > 0


def test_ac09_update_fog_of_war_marks_square_visibility_window():
    area_state = AreaState(area_id="area_1")

    newly_explored = update_fog_of_war((10, 10), 5, area_state)

    assert (5, 5) in newly_explored
    assert (15, 15) in newly_explored
    assert (10, 10) in area_state.explored_tiles


def test_ac10_area_state_round_trip_preserves_state():
    area_state = AreaState(
        area_id="area_1",
        current_hour=20,
        doors_state={"door_1": True},
        containers_looted={"chest_1": True},
        traps_triggered={"trap_1": True},
        spawn_counts={"spawn_1": 2},
        spawn_cooldowns={"spawn_1": 99},
        explored_tiles={(1, 1), (2, 2)},
        room_assignments={"room_1": "pc"},
    )

    restored = AreaState.from_dict(area_state.to_dict())

    assert restored == area_state


def test_check_region_entry_and_transition_area_emit_expected_travel_event():
    actor = _actor("pc")
    actor.position.x = 8
    actor.position.y = 8
    region = RegionDef(
        region_id="travel_1",
        region_type="travel",
        bounds=(8, 8, 2, 2),
        destination_area_id="area_2",
        destination_pos=(1, 1),
    )
    area_def = AreaDef(area_id="area_1", label="Area", width=10, height=10, regions=[region])
    area_state = AreaState(area_id="area_1")

    events = check_region_entry((8, 8), area_def, area_state)
    transition = transition_area(actor, region)

    assert events[0]["type"] == "travel"
    assert transition["destination_area_id"] == "area_2"
    assert transition["destination_pos"] == (1, 1)

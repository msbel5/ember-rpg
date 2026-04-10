from __future__ import annotations

import inspect

from engine.map import MapData, Room, TileType
from engine.world.behavior_tree import BehaviorContext, PriorityNode, Status
from engine.world.behavior_tree_leaves import (
    FaceTargetNode,
    FollowScheduleNode,
    GoToWaypointNode,
    SleepAtNightNode,
    WaitNode,
    WanderInBoundsNode,
    build_default_ambient_tree,
)
from engine.world.entity import Entity, EntityType


def _entity(x: int = 1, y: int = 1) -> Entity:
    entity = Entity(
        id="npc_ambient",
        entity_type=EntityType.NPC,
        name="Ambient NPC",
        position=(x, y),
        glyph="N",
        color="white",
        blocking=True,
    )
    setattr(entity, "facing", "south")
    setattr(entity, "state", "stand")
    return entity


def _map(width: int = 8, height: int = 8) -> MapData:
    return MapData(
        width=width,
        height=height,
        tiles=[[TileType.FLOOR for _x in range(width)] for _y in range(height)],
        rooms=[Room(x=0, y=0, width=width, height=height, room_type="test")],
        spawn_point=(1, 1),
        exit_points=[],
        metadata={},
    )


def _ctx(entity: Entity | None = None, *, hour: int = 9, tick: int = 0) -> BehaviorContext:
    return BehaviorContext(
        entity=entity or _entity(),
        game_time=type("GameTime", (), {"hour": hour})(),
        map_data=_map(),
        blackboard={"visual_tick_index": tick},
    )


def test_reflection_leaf_public_api_matches_prd_contract() -> None:
    expected = {
        "WanderInBoundsNode": ["self", "center", "radius", "step_cadence", "name"],
        "FollowScheduleNode": ["self", "schedule", "waypoints", "name"],
        "GoToWaypointNode": ["self", "target", "name"],
        "FaceTargetNode": ["self", "target", "name"],
        "WaitNode": ["self", "ticks", "name"],
        "SleepAtNightNode": ["self", "bed", "night_hours", "name"],
    }
    classes = [
        WanderInBoundsNode,
        FollowScheduleNode,
        GoToWaypointNode,
        FaceTargetNode,
        WaitNode,
        SleepAtNightNode,
    ]
    assert inspect.signature(build_default_ambient_tree).parameters.keys() == {"npc_record"}
    for cls in classes:
        assert inspect.isclass(cls)
        assert list(inspect.signature(cls.__init__).parameters.keys()) == expected[cls.__name__]
        assert list(inspect.signature(cls.tick).parameters.keys()) == ["self", "ctx"]


def test_face_target_node_sets_compass_direction() -> None:
    entity = _entity(3, 3)
    ctx = _ctx(entity)
    result = FaceTargetNode((4, 2)).tick(ctx)
    assert result == Status.SUCCESS
    assert getattr(entity, "facing") == "ne"


def test_go_to_waypoint_moves_one_tile_toward_target() -> None:
    entity = _entity(1, 1)
    ctx = _ctx(entity)
    result = GoToWaypointNode((4, 4)).tick(ctx)
    assert result == Status.RUNNING
    assert entity.position == (2, 2)
    assert getattr(entity, "state") == "walk"
    assert getattr(entity, "facing") == "se"


def test_follow_schedule_uses_previous_scheduled_hour_when_exact_hour_missing() -> None:
    entity = _entity(1, 1)
    ctx = _ctx(entity, hour=10)
    node = FollowScheduleNode(schedule={8: "market", 14: "temple"}, waypoints={"market": (3, 1), "temple": (5, 5)})
    result = node.tick(ctx)
    assert result == Status.RUNNING
    assert ctx.blackboard["schedule_hour"] == 8
    assert ctx.blackboard["schedule_waypoint"] == "market"
    assert entity.position == (2, 1)


def test_wait_node_counts_then_resets() -> None:
    node = WaitNode(2)
    ctx = _ctx()
    assert node.tick(ctx) == Status.RUNNING
    assert node.tick(ctx) == Status.RUNNING
    assert node.tick(ctx) == Status.SUCCESS
    assert ctx.blackboard["Wait_elapsed"] == 0


def test_sleep_at_night_sleeps_only_in_night_range() -> None:
    entity = _entity(1, 1)
    day_ctx = _ctx(entity, hour=12)
    night_ctx = _ctx(entity, hour=2)
    node = SleepAtNightNode((1, 1), range(0, 7))
    assert node.tick(day_ctx) == Status.FAILURE
    assert node.tick(night_ctx) == Status.SUCCESS
    assert getattr(entity, "state") == "sleep"


def test_wander_in_bounds_respects_cadence_and_updates_last_step_tick() -> None:
    entity = _entity(2, 2)
    node = WanderInBoundsNode(center=(2, 2), radius=2, step_cadence=3)
    ctx = _ctx(entity, tick=1)
    ctx.blackboard["last_step_tick"] = 0
    assert node.tick(ctx) == Status.SUCCESS
    assert entity.position == (2, 2)
    late_ctx = _ctx(entity, tick=3)
    late_ctx.blackboard = ctx.blackboard
    late_ctx.blackboard["visual_tick_index"] = 3
    result = node.tick(late_ctx)
    assert result == Status.RUNNING
    assert late_ctx.blackboard["last_step_tick"] == 3
    assert entity.position != (2, 2)


def test_build_default_ambient_tree_returns_priority_node() -> None:
    tree = build_default_ambient_tree(
        {
            "position": [2, 2],
            "ambient_profile": {
                "home_tile": (1, 1),
                "wander_center": (2, 2),
                "wander_radius": 4,
                "schedule": {8: "market"},
                "waypoints": {"market": (3, 3)},
                "night_hours": range(0, 7),
            },
        }
    )
    assert isinstance(tree, PriorityNode)
    assert len(tree.children) == 3

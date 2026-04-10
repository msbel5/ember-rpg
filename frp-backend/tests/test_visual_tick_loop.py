from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from engine.map import MapData, Room, TileType
from engine.world.behavior_tree_leaves import WanderInBoundsNode
from engine.world.entity import Entity, EntityType
from engine.api.campaign.visual_tick_loop import (
    DEFAULT_VISUAL_TICK_INTERVAL,
    VisualTickLoop,
    get_visual_tick_loop,
    is_visual_tick_env_disabled,
    resolve_visual_tick_interval,
    start_visual_tick_loop,
    stop_visual_tick_loop,
)


class _SpatialIndex:
    def __init__(self) -> None:
        self.positions: dict[str, tuple[int, int]] = {}

    def add(self, entity) -> None:
        self.positions[str(entity.id)] = tuple(entity.position)

    def move(self, entity, x: int, y: int) -> None:
        self.positions[str(entity.id)] = (int(x), int(y))

    def get_position(self, entity_id: str):
        return self.positions.get(str(entity_id))


class _Runtime:
    def __init__(self, context) -> None:
        self.context = context

    def get_campaign(self, campaign_id: str):
        assert campaign_id == self.context.campaign_id
        return self.context


def _map() -> MapData:
    return MapData(
        width=6,
        height=6,
        tiles=[[TileType.FLOOR for _x in range(6)] for _y in range(6)],
        rooms=[Room(x=0, y=0, width=6, height=6, room_type="test")],
        spawn_point=(1, 1),
        exit_points=[],
        metadata={},
    )


def _context():
    entity = Entity(
        id="npc_visual",
        entity_type=EntityType.NPC,
        name="Visual NPC",
        position=(2, 2),
        glyph="N",
        color="white",
        blocking=True,
    )
    setattr(entity, "facing", "south")
    setattr(entity, "state", "stand")
    record = {
        "type": "npc",
        "name": "Visual NPC",
        "position": [2, 2],
        "ambient_life": True,
        "entity_ref": entity,
        "ambient_profile": {
            "home_tile": (2, 2),
            "wander_center": (2, 2),
            "wander_radius": 2,
            "schedule": {},
            "waypoints": {"settlement_square": (2, 2)},
            "night_hours": range(0, 1),
            "state": "stand",
            "facing": "south",
        },
        "waypoints": {"settlement_square": (2, 2)},
        "wander_tree": WanderInBoundsNode(center=(2, 2), radius=2, step_cadence=1),
    }
    spatial_index = _SpatialIndex()
    spatial_index.add(entity)
    context = SimpleNamespace(
        campaign_id="ambient-campaign",
        entities={"npc_visual": record},
        campaign_state={"visual_tick_enabled": True},
        kernel_runtime={},
        spatial_index=spatial_index,
        map_data=_map(),
        position=[1, 1],
        region_snapshot=SimpleNamespace(region_id="region-1"),
        world=SimpleNamespace(simulation_snapshot=SimpleNamespace(current_hour=9, region_states={"region-1": {"npcs": [{"id": "npc_visual", "x": 2, "y": 2}]}})),
        in_combat=lambda: False,
    )
    return context


@pytest.mark.asyncio
async def test_reflection_visual_tick_public_api_matches_prd_contract() -> None:
    assert list(inspect.signature(VisualTickLoop.__init__).parameters.keys()) == [
        "self",
        "runtime",
        "campaign_id",
        "tick_interval",
        "on_tick",
    ]
    for method_name in ("start", "stop", "pause", "resume", "set_on_tick", "tick_once"):
        assert hasattr(VisualTickLoop, method_name)
    assert list(inspect.signature(start_visual_tick_loop).parameters.keys()) == [
        "runtime",
        "campaign_id",
        "on_tick",
        "tick_interval",
    ]
    assert list(inspect.signature(stop_visual_tick_loop).parameters.keys()) == ["campaign_id"]


@pytest.mark.asyncio
async def test_visual_tick_emits_delta_without_advancing_game_time() -> None:
    context = _context()
    captured: list[dict] = []

    async def _capture(_campaign_id: str, payload: dict) -> None:
        captured.append(payload)

    loop = VisualTickLoop(_Runtime(context), context.campaign_id, on_tick=_capture)
    starting_hour = int(context.world.simulation_snapshot.current_hour)
    payload = await loop.tick_once()
    assert payload is not None
    assert payload["type"] == "visual_delta"
    assert payload["actors"]
    assert int(context.world.simulation_snapshot.current_hour) == starting_hour
    assert captured and captured[-1]["tick_index"] == 1


@pytest.mark.asyncio
async def test_visual_tick_respects_pause_and_env_kill_switch(monkeypatch) -> None:
    context = _context()
    loop = VisualTickLoop(_Runtime(context), context.campaign_id)
    loop.pause("manual")
    assert await loop.tick_once() is None
    loop.resume("manual")
    monkeypatch.setenv("EMBER_DISABLE_VISUAL_TICK", "1")
    assert is_visual_tick_env_disabled() is True
    assert await loop.tick_once() is None


@pytest.mark.asyncio
async def test_visual_tick_loop_registry_start_and_stop() -> None:
    context = _context()
    runtime = _Runtime(context)
    loop = await start_visual_tick_loop(runtime, context.campaign_id)
    assert get_visual_tick_loop(context.campaign_id) is loop
    assert loop.running is True
    await stop_visual_tick_loop(context.campaign_id)
    assert get_visual_tick_loop(context.campaign_id) is None


def test_visual_tick_interval_resolution_clamps_to_valid_range(monkeypatch) -> None:
    monkeypatch.setenv("EMBER_VISUAL_TICK_INTERVAL", "9.5")
    assert resolve_visual_tick_interval() == 1.0
    monkeypatch.setenv("EMBER_VISUAL_TICK_INTERVAL", "0.001")
    assert resolve_visual_tick_interval() == 0.016
    monkeypatch.setenv("EMBER_VISUAL_TICK_INTERVAL", str(DEFAULT_VISUAL_TICK_INTERVAL))
    assert resolve_visual_tick_interval() == DEFAULT_VISUAL_TICK_INTERVAL

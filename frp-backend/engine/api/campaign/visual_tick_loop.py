"""Fast visual-only tick loop for ambient actor movement."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from types import SimpleNamespace
from typing import Any, Callable, Coroutine, Optional

from engine.world.behavior_tree import BehaviorContext

from engine.world.behavior_tree_leaves import build_default_ambient_tree
from .tick_loop import schedule_tick_loop_coroutine

logger = logging.getLogger(__name__)

DEFAULT_VISUAL_TICK_INTERVAL = 0.033
MIN_VISUAL_TICK_INTERVAL = 0.016
MAX_VISUAL_TICK_INTERVAL = 1.0
_KEEPALIVE_PERIOD = 5


def _clamp_interval(value: float) -> float:
    return max(MIN_VISUAL_TICK_INTERVAL, min(MAX_VISUAL_TICK_INTERVAL, float(value)))


def resolve_visual_tick_interval(default: float = DEFAULT_VISUAL_TICK_INTERVAL) -> float:
    raw = os.getenv("EMBER_VISUAL_TICK_INTERVAL", "").strip()
    if not raw:
        return _clamp_interval(default)
    try:
        return _clamp_interval(float(raw))
    except ValueError:
        return _clamp_interval(default)


def is_visual_tick_env_disabled() -> bool:
    value = os.getenv("EMBER_DISABLE_VISUAL_TICK", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


class VisualTickLoop:
    def __init__(
        self,
        runtime: Any,
        campaign_id: str,
        *,
        tick_interval: float = DEFAULT_VISUAL_TICK_INTERVAL,
        on_tick: Optional[Callable[[str, dict[str, Any]], Coroutine[Any, Any, Any]]] = None,
    ) -> None:
        self._runtime = runtime
        self._campaign_id = campaign_id
        self._interval = resolve_visual_tick_interval(tick_interval)
        self._on_tick = on_tick
        self._task: Optional[asyncio.Task] = None
        self._pause_reasons: set[str] = set()
        self._tick_index: int = 0
        self._last_actor_snapshots: dict[str, dict[str, Any]] = {}
        self._last_keepalive_tick: int = -_KEEPALIVE_PERIOD
        self._last_tick_duration_ms: float = 0.0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def paused(self) -> bool:
        return bool(self._pause_reasons)

    @property
    def pause_reasons(self) -> tuple[str, ...]:
        return tuple(sorted(self._pause_reasons))

    @property
    def tick_index(self) -> int:
        return self._tick_index

    @property
    def interval_seconds(self) -> float:
        return self._interval

    @property
    def last_tick_duration_ms(self) -> float:
        return self._last_tick_duration_ms

    async def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._loop(), name=f"visual_tick_{self._campaign_id[:8]}")
        logger.info("Visual tick loop started for %s (interval=%.3fs)", self._campaign_id[:8], self._interval)

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Visual tick loop stopped for %s", self._campaign_id[:8])

    def pause(self, reason: str = "manual") -> None:
        self._pause_reasons.add(str(reason or "manual"))

    def resume(self, reason: str = "manual") -> None:
        self._pause_reasons.discard(str(reason or "manual"))

    def set_on_tick(self, callback: Optional[Callable[[str, dict[str, Any]], Coroutine[Any, Any, Any]]]) -> None:
        self._on_tick = callback

    async def tick_once(self) -> dict[str, Any] | None:
        if is_visual_tick_env_disabled():
            return None
        try:
            context = self._runtime.get_campaign(self._campaign_id)
        except (KeyError, ValueError):
            return None
        if bool(context.campaign_state.get("visual_tick_enabled", True)) is False:
            return None
        if self.paused or context.in_combat():
            return None
        start_time = time.perf_counter()
        actors: list[dict[str, Any]] = []
        self._tick_index += 1
        current_hour = self._current_hour(context)
        for actor_id, record in self._iter_ambient_records(context):
            before = self._snapshot_actor(actor_id, record)
            self._ensure_wander_tree(record)
            tree = record.get("wander_tree")
            if tree is None:
                continue
            blackboard = record.setdefault("_ambient_blackboard", {})
            if not isinstance(blackboard, dict):
                blackboard = {}
                record["_ambient_blackboard"] = blackboard
            blackboard["visual_tick_index"] = self._tick_index
            blackboard["current_hour"] = current_hour
            entity = record.get("entity_ref")
            if entity is None:
                continue
            ctx = BehaviorContext(
                entity=entity,
                spatial_index=getattr(context, "spatial_index", None),
                game_time=SimpleNamespace(hour=current_hour),
                map_data=getattr(context, "map_data", None),
                blackboard=blackboard,
            )
            tree.tick(ctx)
            self._sync_record_from_entity(context, actor_id, record)
            after = self._snapshot_actor(actor_id, record)
            delta = self._diff_actor(before, after)
            if delta is not None:
                actors.append(delta)
        self._last_tick_duration_ms = (time.perf_counter() - start_time) * 1000.0
        if not actors and (self._tick_index - self._last_keepalive_tick) < _KEEPALIVE_PERIOD:
            return None
        payload = {
            "type": "visual_delta",
            "tick_index": self._tick_index,
            "actors": actors,
        }
        if not actors:
            self._last_keepalive_tick = self._tick_index
        if self._on_tick is not None:
            await self._on_tick(self._campaign_id, payload)
        return payload

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.tick_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Visual tick error for %s", self._campaign_id[:8])

    def _current_hour(self, context: Any) -> int:
        snapshot = getattr(getattr(context, "world", None), "simulation_snapshot", None)
        if snapshot is not None:
            return int(getattr(snapshot, "current_hour", 0)) % 24
        return int(getattr(getattr(context, "game_time", None), "hour", 0)) % 24

    def _iter_ambient_records(self, context: Any):
        runtime = context.kernel_runtime or {}
        game_state = runtime.get("game_state")
        active_party_ids = {
            str(actor_id)
            for actor_id in list(getattr(game_state, "party", []))
            if str(actor_id)
        } if game_state is not None else set()
        for actor_id, record in list(getattr(context, "entities", {}).items()):
            if actor_id == "player" or actor_id in active_party_ids:
                continue
            if not isinstance(record, dict) or str(record.get("type", "")).strip().lower() != "npc":
                continue
            if not bool(record.get("ambient_life", False)):
                continue
            if record.get("party_member_active"):
                continue
            if record.get("entity_ref") is None:
                continue
            yield str(actor_id), record

    def _ensure_wander_tree(self, record: dict[str, Any]) -> None:
        if record.get("wander_tree") is None and bool(record.get("ambient_life", False)):
            record["wander_tree"] = build_default_ambient_tree(record)

    def _snapshot_actor(self, actor_id: str, record: dict[str, Any]) -> dict[str, Any]:
        entity = record.get("entity_ref")
        position = record.get("position", getattr(entity, "position", (0, 0)))
        facing = record.get("facing", getattr(entity, "facing", "south"))
        state = record.get("state", getattr(entity, "state", "stand"))
        snapshot = {
            "id": str(actor_id),
            "position": [int(position[0]), int(position[1])],
            "facing": str(facing or "south"),
            "state": str(state or "stand"),
        }
        self._last_actor_snapshots[str(actor_id)] = dict(snapshot)
        return snapshot

    def _diff_actor(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any] | None:
        if before == after:
            return None
        return {
            "id": str(after["id"]),
            "position": [int(after["position"][0]), int(after["position"][1])],
            "facing": str(after["facing"]),
            "state": str(after["state"]),
        }

    def _sync_record_from_entity(self, context: Any, actor_id: str, record: dict[str, Any]) -> None:
        entity = record.get("entity_ref")
        if entity is None:
            return
        position = getattr(entity, "position", record.get("position", (0, 0)))
        next_position = [int(position[0]), int(position[1])]
        previous = record.get("position", next_position)
        if list(previous) != next_position and getattr(context, "spatial_index", None) is not None:
            if context.spatial_index.get_position(actor_id) is None:
                context.spatial_index.add(entity)
            else:
                context.spatial_index.move(entity, next_position[0], next_position[1])
        record["position"] = next_position
        record["facing"] = str(getattr(entity, "facing", record.get("facing", "south")) or "south")
        record["state"] = str(getattr(entity, "state", record.get("state", "stand")) or "stand")
        live_entry = self._live_region_npc_entry(context, actor_id)
        if live_entry is not None:
            live_entry["x"] = next_position[0]
            live_entry["y"] = next_position[1]
            live_entry["facing"] = record["facing"]
            live_entry["state"] = record["state"]

    def _live_region_npc_entry(self, context: Any, actor_id: str) -> dict[str, Any] | None:
        snapshot = getattr(getattr(context, "world", None), "simulation_snapshot", None)
        region_id = str(getattr(getattr(context, "region_snapshot", None), "region_id", ""))
        if snapshot is None or not region_id:
            return None
        region_state = snapshot.region_states.get(region_id)
        if not isinstance(region_state, dict):
            return None
        for entry in list(region_state.get("npcs", [])):
            if isinstance(entry, dict) and str(entry.get("id", "")) == actor_id:
                return entry
        return None


_visual_tick_loops: dict[str, VisualTickLoop] = {}


async def start_visual_tick_loop(
    runtime: Any,
    campaign_id: str,
    on_tick: Optional[Callable[[str, dict[str, Any]], Coroutine[Any, Any, Any]]] = None,
    tick_interval: float = DEFAULT_VISUAL_TICK_INTERVAL,
) -> VisualTickLoop:
    existing = _visual_tick_loops.get(campaign_id)
    if existing is not None and existing.running:
        if on_tick is not None:
            existing.set_on_tick(on_tick)
        return existing
    loop = VisualTickLoop(runtime, campaign_id, tick_interval=tick_interval, on_tick=on_tick)
    _visual_tick_loops[campaign_id] = loop
    await loop.start()
    return loop


async def stop_visual_tick_loop(campaign_id: str) -> None:
    loop = _visual_tick_loops.pop(campaign_id, None)
    if loop is not None:
        await loop.stop()


def get_visual_tick_loop(campaign_id: str) -> Optional[VisualTickLoop]:
    return _visual_tick_loops.get(campaign_id)


def try_start_visual_tick_loop(runtime: Any, campaign_id: str, *, on_tick: Optional[Callable[[str, dict[str, Any]], Coroutine[Any, Any, Any]]] = None, tick_interval: float = DEFAULT_VISUAL_TICK_INTERVAL) -> None:
    coro = start_visual_tick_loop(runtime, campaign_id, on_tick=on_tick, tick_interval=tick_interval)
    if not schedule_tick_loop_coroutine(coro):
        coro.close()


def try_stop_visual_tick_loop(campaign_id: str) -> None:
    coro = stop_visual_tick_loop(campaign_id)
    if not schedule_tick_loop_coroutine(coro):
        coro.close()


__all__ = [
    "DEFAULT_VISUAL_TICK_INTERVAL",
    "MAX_VISUAL_TICK_INTERVAL",
    "MIN_VISUAL_TICK_INTERVAL",
    "VisualTickLoop",
    "get_visual_tick_loop",
    "is_visual_tick_env_disabled",
    "resolve_visual_tick_interval",
    "start_visual_tick_loop",
    "stop_visual_tick_loop",
    "try_start_visual_tick_loop",
    "try_stop_visual_tick_loop",
]

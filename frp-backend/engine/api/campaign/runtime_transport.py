"""Transport/runtime-mode helpers shared by campaign runtime and websocket flow."""
from __future__ import annotations

from typing import Any, Optional

from engine.api.websocket_support import websocket_support_payload

from .dialog import build_dialog_payload
from .tick_loop import (
    DEFAULT_TICK_HOURS,
    DEFAULT_TICK_INTERVAL,
    get_tick_loop,
    schedule_tick_loop_coroutine,
)


def build_transport_payload(context: Any) -> dict[str, Any]:
    tick_loop = get_tick_loop(context.campaign_id)
    interval = float(getattr(tick_loop, "_interval", DEFAULT_TICK_INTERVAL))
    tick_hours = int(getattr(tick_loop, "_tick_hours", DEFAULT_TICK_HOURS))
    websocket_support = websocket_support_payload()
    return {
        "mode": "ws",
        "bootstrap": "http",
        "command_transport": "ws",
        "snapshot_mode": "full",
        "idle_world_ticks": not context.in_combat(),
        "tick_interval_seconds": interval,
        "tick_hours_per_interval": tick_hours,
        "ws_path": f"/game/ws/campaigns/{context.campaign_id}",
        "ws_url": "",
        "websocket_ready": bool(websocket_support["websocket_transport"]),
        "websocket_library": str(websocket_support["websocket_library"]),
    }


def build_tick_state(context: Any) -> dict[str, Any]:
    tick_loop = get_tick_loop(context.campaign_id)
    if tick_loop is None:
        return {
            "running": False,
            "paused": False,
            "pause_reasons": [],
            "interval_seconds": DEFAULT_TICK_INTERVAL,
            "tick_hours_per_interval": DEFAULT_TICK_HOURS,
            "tick_index": 0,
        }
    return {
        "running": bool(tick_loop.running),
        "paused": bool(tick_loop.paused),
        "pause_reasons": list(tick_loop.pause_reasons),
        "interval_seconds": float(getattr(tick_loop, "_interval", DEFAULT_TICK_INTERVAL)),
        "tick_hours_per_interval": int(getattr(tick_loop, "_tick_hours", DEFAULT_TICK_HOURS)),
        "tick_index": int(getattr(tick_loop, "tick_index", 0)),
    }


def build_world_ready(campaign_payload: dict[str, Any]) -> bool:
    map_data = campaign_payload.get("map_data", {})
    tiles = map_data.get("tiles", []) if isinstance(map_data, dict) else []
    if not isinstance(tiles, list) or not tiles:
        return False
    player = campaign_payload.get("player", {})
    if not isinstance(player, dict) or not player:
        return False
    world_entities = campaign_payload.get("world_entities", [])
    if not isinstance(world_entities, list) or not world_entities:
        return False
    has_talkable = False
    has_service_prop = False
    for entity in world_entities:
        if not isinstance(entity, dict):
            continue
        actions = {
            str(action).strip().lower()
            for action in list(entity.get("context_actions", []))
            if str(action).strip()
        }
        entity_kind = str(entity.get("entity_kind", entity.get("entity_type", ""))).strip().lower()
        anchor_kind = str(entity.get("anchor_kind", "")).strip().lower()
        if "talk" in actions and entity_kind in {"npc", "actor", "friendly", "companion"}:
            has_talkable = True
        if "examine" in actions and (
            entity_kind in {"furniture", "fixture", "object", "prop"}
            or anchor_kind in {"service", "landmark"}
        ):
            has_service_prop = True
        if has_talkable and has_service_prop:
            return True
    return False


def resolve_runtime_mode(
    context: Any,
    *,
    dialog_payload: Optional[dict[str, Any]] = None,
    campaign_payload: Optional[dict[str, Any]] = None,
) -> str:
    if context.in_combat():
        return "combat_turn_based"
    if dialog_payload is None:
        dialog_payload = build_dialog_payload(context, "")
    if dialog_payload:
        return "dialog"
    travel_state = (context.kernel_runtime or {}).get("travel_state")
    if isinstance(travel_state, dict):
        status = str(travel_state.get("status", "")).strip().lower()
        if status and status not in {"idle", "arrived", "completed", "resolved", "cancelled"}:
            return "travel"
    payload = campaign_payload or {}
    if isinstance(payload.get("travel_state"), dict):
        status = str(payload["travel_state"].get("status", "")).strip().lower()
        if status and status not in {"idle", "arrived", "completed", "resolved", "cancelled"}:
            return "travel"
    tick_loop = get_tick_loop(context.campaign_id)
    if tick_loop is not None and tick_loop.paused:
        return "tactical_pause"
    return "exploration_realtime"


def sync_tick_loop_mode(
    context: Any,
    *,
    dialog_payload: Optional[dict[str, Any]] = None,
) -> None:
    tick_loop = get_tick_loop(context.campaign_id)
    if tick_loop is None:
        return
    if context.in_combat():
        tick_loop.pause("combat")
    else:
        tick_loop.resume("combat")
    active_dialog = bool(dialog_payload if dialog_payload is not None else build_dialog_payload(context, ""))
    if active_dialog:
        tick_loop.pause("dialog")
    else:
        tick_loop.resume("dialog")


def try_start_tick_loop(runtime: Any, campaign_id: str, *, interval: float = DEFAULT_TICK_INTERVAL) -> None:
    """Start tick loop if an asyncio event loop is running."""
    from engine.api.campaign.tick_loop import start_tick_loop

    coro = start_tick_loop(runtime, campaign_id, interval=interval)
    if not schedule_tick_loop_coroutine(coro):
        coro.close()


def try_stop_tick_loop(campaign_id: str) -> None:
    """Stop tick loop if an asyncio event loop is running."""
    from engine.api.campaign.tick_loop import stop_tick_loop

    coro = stop_tick_loop(campaign_id)
    if not schedule_tick_loop_coroutine(coro):
        coro.close()


__all__ = [
    "build_transport_payload",
    "build_tick_state",
    "build_world_ready",
    "resolve_runtime_mode",
    "sync_tick_loop_mode",
    "try_start_tick_loop",
    "try_stop_tick_loop",
]

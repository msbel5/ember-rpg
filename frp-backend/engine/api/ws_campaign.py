"""WebSocket transport for campaign commands and live state push.

Primary runtime transport after campaign creation. The client sends
commands over WebSocket and receives state snapshots, tick events,
and narrative as push messages.

Protocol (JSON over WebSocket text frames):
  Client -> Server:
    {"type": "command", "input": "attack goblin"}
    {"type": "command", "input": "", "shortcut": "travel", "args": {...}}
    {"type": "runtime_mode", "mode": "tactical_pause"}
    {"type": "ping"}

  Server -> Client:
    {"type": "state", "snapshot": {...}, "narrative": "...", "events": [...]}
    {"type": "tick", "events": [...], "snapshot": {...}}
    {"type": "error", "message": "..."}
    {"type": "pong"}
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from engine.api.campaign.debug_trace import trace_event
from engine.api.campaign.tick_loop import get_tick_loop

logger = logging.getLogger(__name__)
ws_router = APIRouter()

# Runtime reference (set via lifespan in main.py).
_runtime_ref: Any = None

# Active WebSocket connections per campaign.
_connections: dict[str, list[WebSocket]] = {}


def _compact_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    campaign = snapshot.get("campaign")
    if not isinstance(campaign, dict):
        return snapshot
    compact_campaign: dict[str, Any] = {}
    for key in (
        "player",
        "scene",
        "location",
        "combat",
        "conversation_state",
        "knowledge",
        "stores",
        "active_store_id",
        "travel_state",
        "crime_state",
        "game_state",
        "settlement",
        "character_sheet",
        "recent_event_log",
        "active_quests",
        "quest_offers",
        "ground_items",
        "world_entities",
        "map_data",
        "world",
        "travel_options",
        "current_region_summary",
        "path_authority",
        "local_map_state",
    ):
        if key in campaign:
            compact_campaign[key] = campaign[key]
    world_state = campaign.get("world_state")
    if isinstance(world_state, dict):
        compact_campaign["world_state"] = {
            key: world_state[key]
            for key in ("seed", "active_region_id")
            if key in world_state
        }
    compact_snapshot = dict(snapshot)
    compact_snapshot["campaign"] = compact_campaign
    return compact_snapshot


def set_runtime(runtime: Any) -> None:
    """Register the CampaignRuntime instance for WebSocket handlers."""
    global _runtime_ref
    _runtime_ref = runtime
    logger.info("CampaignRuntime registered for WebSocket transport")


def _get_runtime():
    if _runtime_ref is None:
        raise RuntimeError("CampaignRuntime not registered for WebSocket")
    return _runtime_ref


def get_connections(campaign_id: str) -> list[WebSocket]:
    """Return active WebSocket connections for a campaign."""
    return list(_connections.get(campaign_id, []))


async def push_tick_events(campaign_id: str, events: list[dict[str, Any]], snapshot: dict[str, Any]) -> None:
    """Push tick events to all connected WebSocket clients for a campaign."""
    sockets = _connections.get(campaign_id, [])
    dead: list[WebSocket] = []
    compact_snapshot = _compact_snapshot(snapshot)
    for ws in sockets:
        try:
            await ws.send_json({"type": "tick", "events": events, "snapshot": compact_snapshot})
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.remove(ws)


def _register(campaign_id: str, ws: WebSocket) -> None:
    _connections.setdefault(campaign_id, []).append(ws)


def _unregister(campaign_id: str, ws: WebSocket) -> None:
    conns = _connections.get(campaign_id, [])
    if ws in conns:
        conns.remove(ws)
    if not conns:
        _connections.pop(campaign_id, None)


@ws_router.websocket("/ws/campaigns/{campaign_id}")
async def ws_campaign(websocket: WebSocket, campaign_id: str):
    """Handle a WebSocket connection for a single campaign session."""
    await websocket.accept()
    trace_event("ws_connect", campaign_id=campaign_id)
    runtime = _get_runtime()

    try:
        runtime.get_campaign(campaign_id)
    except (KeyError, ValueError):
        await websocket.send_json({"type": "error", "message": f"Campaign not found: {campaign_id}"})
        await websocket.close(code=4004, reason="campaign_not_found")
        return

    _register(campaign_id, websocket)
    # Register push callback on tick loop (lifecycle managed by CampaignRuntime).
    tick_loop = get_tick_loop(campaign_id)
    if tick_loop is not None:
        tick_loop.set_on_tick(push_tick_events)

    try:
        snapshot = runtime.snapshot(campaign_id, narrative="Connected.")
        await websocket.send_json({"type": "state", "snapshot": _compact_snapshot(snapshot)})
    except Exception as exc:
        logger.warning("Failed to send initial snapshot: %s", exc)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = str(msg.get("type", ""))
            trace_event("ws_message", campaign_id=campaign_id, msg_type=msg_type)

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "runtime_mode":
                requested_mode = str(msg.get("mode", "")).strip().lower()
                tick_loop = get_tick_loop(campaign_id)
                if tick_loop is None:
                    await websocket.send_json({"type": "error", "message": "Runtime loop unavailable"})
                    continue
                if requested_mode == "tactical_pause":
                    tick_loop.pause("manual")
                elif requested_mode in {"exploration_realtime", "resume"}:
                    tick_loop.resume("manual")
                else:
                    await websocket.send_json({"type": "error", "message": f"Unknown runtime mode: {requested_mode}"})
                    continue
                snapshot = runtime.snapshot(campaign_id, narrative="")
                await websocket.send_json({"type": "state", "snapshot": _compact_snapshot(snapshot), "events": []})
                continue

            if msg_type == "command":
                input_text = str(msg.get("input", ""))
                shortcut = msg.get("shortcut")
                args = msg.get("args")
                if not input_text and not shortcut:
                    await websocket.send_json({"type": "error", "message": "Empty command"})
                    continue
                try:
                    result = runtime.run_command(campaign_id, input_text, shortcut=shortcut, args=args)
                    narrative = str(result.get("narrative", ""))
                    snap = runtime.snapshot(campaign_id, narrative=narrative)
                    await websocket.send_json({
                        "type": "state", "snapshot": _compact_snapshot(snap),
                        "narrative": narrative,
                        "events": list(result.get("generated_events", [])),
                    })
                except Exception as exc:
                    logger.exception("Command error: %s", exc)
                    await websocket.send_json({"type": "error", "message": str(exc)})
                continue

            await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        trace_event("ws_disconnect", campaign_id=campaign_id)
    except Exception as exc:
        logger.exception("WebSocket error: %s", exc)
        trace_event("ws_error", campaign_id=campaign_id, error=str(exc))
    finally:
        _unregister(campaign_id, websocket)
        if not _connections.get(campaign_id):
            tick_loop = get_tick_loop(campaign_id)
            if tick_loop is not None:
                tick_loop.set_on_tick(None)


__all__ = ["get_connections", "push_tick_events", "set_runtime", "ws_router"]

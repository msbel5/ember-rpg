"""WebSocket transport for campaign commands and state push.

Provides real-time bidirectional communication between the Godot client
and the Python backend. The client sends commands over WebSocket and
receives state snapshots and events as push messages.

Protocol (JSON over WebSocket text frames):
  Client -> Server:
    {"type": "command", "input": "attack goblin"}
    {"type": "ping"}

  Server -> Client:
    {"type": "state", "snapshot": {...}, "narrative": "..."}
    {"type": "error", "message": "..."}
    {"type": "pong"}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from engine.api.campaign.debug_trace import trace_event

logger = logging.getLogger(__name__)
ws_router = APIRouter()

# Registry of active campaign runtimes (set by main.py on startup).
_runtime_ref: Any = None


def set_runtime(runtime: Any) -> None:
    """Register the CampaignRuntime instance for WebSocket handlers."""
    global _runtime_ref
    _runtime_ref = runtime


def _get_runtime():
    """Return the registered CampaignRuntime or raise."""
    if _runtime_ref is None:
        raise RuntimeError("CampaignRuntime not registered for WebSocket")
    return _runtime_ref


@ws_router.websocket("/ws/campaigns/{campaign_id}")
async def ws_campaign(websocket: WebSocket, campaign_id: str):
    """Handle a WebSocket connection for a single campaign session."""
    await websocket.accept()
    trace_event("ws_connect", campaign_id=campaign_id)

    runtime = _get_runtime()

    # Validate campaign exists.
    try:
        context = runtime.get_campaign(campaign_id)
    except (KeyError, ValueError) as exc:
        await websocket.send_json({"type": "error", "message": f"Campaign not found: {campaign_id}"})
        await websocket.close(code=4004, reason="campaign_not_found")
        return

    # Send initial state snapshot.
    try:
        snapshot = runtime.snapshot(campaign_id, narrative="Connected.")
        await websocket.send_json({"type": "state", "snapshot": snapshot})
    except Exception as exc:
        logger.warning("Failed to send initial snapshot: %s", exc)

    # Message loop.
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

            if msg_type == "command":
                input_text = str(msg.get("input", ""))
                shortcut = msg.get("shortcut")
                args = msg.get("args")
                if not input_text and not shortcut:
                    await websocket.send_json({"type": "error", "message": "Empty command"})
                    continue

                try:
                    result = runtime.run_command(
                        campaign_id,
                        input_text,
                        shortcut=shortcut,
                        args=args,
                    )
                    narrative = str(result.get("narrative", ""))
                    snapshot = runtime.snapshot(campaign_id, narrative=narrative)
                    await websocket.send_json({
                        "type": "state",
                        "snapshot": snapshot,
                        "narrative": narrative,
                        "events": list(result.get("events", [])),
                    })
                except Exception as exc:
                    logger.exception("Command error: %s", exc)
                    await websocket.send_json({"type": "error", "message": str(exc)})
                continue

            # Unknown message type.
            await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        trace_event("ws_disconnect", campaign_id=campaign_id)
    except Exception as exc:
        logger.exception("WebSocket error: %s", exc)
        trace_event("ws_error", campaign_id=campaign_id, error=str(exc))


__all__ = ["ws_router", "set_runtime"]

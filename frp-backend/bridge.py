#!/usr/bin/env python3
"""
Ember RPG Python Bridge — raw TCP socket on localhost.

Replaces HTTP/WebSocket with a minimal JSON-over-TCP protocol.
Godot connects via StreamPeerTCP. No HTTP headers, no URL routing,
no FastAPI middleware — just newline-delimited JSON.

Protocol:
  Client sends: {"id": 1, "method": "health", "args": {}}\n
  Server sends: {"id": 1, "result": {...}}\n

Latency: ~0.1-0.5ms per call (vs 5-50ms for HTTP).
"""
from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import traceback
from typing import Any

# Set up path for backend imports
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

# Silence noisy loggers
logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Import backend
from main import app, campaign_runtime
from engine.api.ws_campaign import set_runtime

try:
    from starlette.testclient import TestClient
except ImportError:
    from fastapi.testclient import TestClient

BRIDGE_PORT = int(os.environ.get("EMBER_BRIDGE_PORT", "9741"))


class EmbeddedBridge:
    """Wraps the FastAPI app as an in-process server with JSON-RPC over TCP."""

    def __init__(self):
        set_runtime(campaign_runtime)
        self._client = TestClient(app, raise_server_exceptions=False)
        self._log("bridge initialized, using TestClient for in-process calls")

    def _log(self, msg: str) -> None:
        sys.stderr.write(f"[bridge] {msg}\n")
        sys.stderr.flush()

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method", "")
        args = request.get("args", {})
        req_id = request.get("id", 0)
        try:
            result = self._dispatch(method, args)
            return {"id": req_id, "result": result}
        except Exception as exc:
            self._log(f"ERROR {method}: {exc}")
            return {"id": req_id, "error": str(exc)}

    def _dispatch(self, method: str, args: dict[str, Any]) -> Any:
        # --- Health ---
        if method == "health":
            return self._get("/game/health/campaign-client")

        # --- Creation flow ---
        if method == "creation_catalog":
            return self._get("/game/campaigns/creation/catalog")
        if method == "creation_start":
            return self._post("/game/campaigns/creation/start", args)
        if method == "creation_answer":
            cid = args.pop("creation_id", "")
            return self._post(f"/game/campaigns/creation/{cid}/answer", args)
        if method == "creation_reroll":
            return self._post(f"/game/campaigns/creation/{args.get('creation_id', '')}/reroll", {})
        if method == "creation_save_roll":
            return self._post(f"/game/campaigns/creation/{args.get('creation_id', '')}/save-roll", {})
        if method == "creation_swap_roll":
            return self._post(f"/game/campaigns/creation/{args.get('creation_id', '')}/swap-roll", {})
        if method == "creation_finalize":
            cid = args.pop("creation_id", "")
            return self._post(f"/game/campaigns/creation/{cid}/finalize", args)

        # --- Campaign state ---
        if method == "get_campaign":
            return self._get(f"/game/campaigns/{args.get('campaign_id', '')}")
        if method == "get_region":
            return self._get(f"/game/campaigns/{args.get('campaign_id', '')}/region/current")
        if method == "get_settlement":
            return self._get(f"/game/campaigns/{args.get('campaign_id', '')}/settlement/current")

        # --- Commands ---
        if method == "run_command":
            cid = args.pop("campaign_id", "")
            return self._post(f"/game/campaigns/{cid}/commands", args)

        # --- Save / Load ---
        if method == "save_campaign":
            cid = args.pop("campaign_id", "")
            return self._post(f"/game/campaigns/{cid}/save", args)
        if method == "list_saves":
            return self._get(f"/game/campaigns/{args.get('campaign_id', '')}/saves")
        if method == "list_player_saves":
            return self._get(f"/game/campaigns/saves/player/{args.get('player_id', '')}")
        if method == "load_campaign":
            return self._post(f"/game/campaigns/load/{args.get('save_id', '')}", {})
        if method == "delete_save":
            return self._delete(f"/game/campaigns/saves/{args.get('save_id', '')}")
        if method == "delete_campaign":
            return self._delete(f"/game/campaigns/{args.get('campaign_id', '')}")

        # --- Runtime mode ---
        if method == "set_runtime_mode":
            cid = args.get("campaign_id", "")
            mode = args.get("mode", "")
            ctx = campaign_runtime._campaigns.get(cid)
            if ctx is None:
                return {"error": f"no campaign: {cid}"}
            ctx.runtime_mode = mode
            return {"ok": True, "mode": mode}

        # --- World tick (pull-based, Godot controls timing) ---
        if method == "tick":
            cid = args.get("campaign_id", "")
            ctx = campaign_runtime._campaigns.get(cid)
            if ctx is None:
                return {"error": f"no campaign: {cid}"}
            campaign_runtime.advance_world_tick(cid)
            return campaign_runtime.campaign_payload(cid)

        # --- Visual tick (ambient NPC movement, Godot polls) ---
        if method == "visual_tick":
            cid = args.get("campaign_id", "")
            ctx = campaign_runtime._campaigns.get(cid)
            if ctx is None:
                return {"actors": []}
            # Use the existing visual tick mechanism
            if not hasattr(ctx, "_bridge_vtl"):
                from engine.api.campaign.visual_tick_loop import VisualTickLoop
                ctx._bridge_vtl = VisualTickLoop()
            delta = ctx._bridge_vtl.tick(ctx)
            return {"type": "visual_delta", "actors": delta.get("actors", []) if delta else []}

        # --- URL-based dispatch (Backend.gd sends HTTP paths directly) ---
        if method.startswith("/game/"):
            http_method = args.pop("_http_method", "GET")
            if http_method == "GET":
                return self._get(method)
            elif http_method == "DELETE":
                return self._delete(method)
            else:
                return self._post(method, args)

        return {"error": f"unknown method: {method}"}

    def _get(self, path: str) -> Any:
        resp = self._client.get(path)
        return resp.json()

    def _post(self, path: str, body: dict) -> Any:
        resp = self._client.post(path, json=body)
        return resp.json()

    def _delete(self, path: str) -> Any:
        resp = self._client.delete(path)
        return resp.json()


def handle_client(conn: socket.socket, bridge: EmbeddedBridge) -> None:
    """Handle one Godot client connection."""
    bridge._log("client connected")
    buf = b""
    try:
        while True:
            data = conn.recv(65536)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    conn.sendall(json.dumps({"error": "invalid JSON"}).encode() + b"\n")
                    continue
                response = bridge.handle(request)
                conn.sendall(json.dumps(response, default=str).encode() + b"\n")
    except (ConnectionResetError, BrokenPipeError):
        bridge._log("client disconnected")
    except Exception as exc:
        bridge._log(f"client error: {exc}")
    finally:
        conn.close()
        bridge._log("client connection closed")


def main() -> int:
    bridge = EmbeddedBridge()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", BRIDGE_PORT))
    server.listen(1)
    bridge._log(f"listening on 127.0.0.1:{BRIDGE_PORT}")

    # Signal ready on stdout so Godot knows we're up
    sys.stdout.write(f'{{"type":"ready","port":{BRIDGE_PORT}}}\n')
    sys.stdout.flush()

    try:
        while True:
            conn, addr = server.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # Handle one client at a time (single-player game)
            handle_client(conn, bridge)
    except KeyboardInterrupt:
        bridge._log("shutting down")
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

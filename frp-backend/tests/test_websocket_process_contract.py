from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from websockets.sync.client import connect


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "frp-backend"
DEV_SERVER = BACKEND_DIR / "dev_server.py"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(base_url: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    with httpx.Client(timeout=1.5) as client:
        while time.time() < deadline:
            try:
                response = client.get(f"{base_url}/game/health/campaign-client")
                if response.status_code == 200:
                    payload = response.json()
                    if isinstance(payload, dict):
                        return payload
            except Exception as exc:  # pragma: no cover - transient process boot
                last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for backend health at {base_url}: {last_error}")


def test_dev_server_process_supports_real_websocket_runtime():
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            sys.executable,
            str(DEV_SERVER),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        health = _wait_for_health(base_url)
        assert health["ok"] is True
        assert health["websocket_transport"] is True
        assert health["websocket_library"] in {"websockets", "wsproto"}

        with httpx.Client(base_url=base_url, timeout=5.0) as client:
            response = client.post(
                "/game/campaigns",
                json={
                    "player_name": "ProcessWSTest",
                    "player_class": "warrior",
                    "adapter_id": "fantasy_ember",
                    "profile_id": "standard",
                    "seed": 42,
                },
            )
            response.raise_for_status()
            campaign_id = response.json()["campaign_id"]

        ws_url = f"ws://127.0.0.1:{port}/game/ws/campaigns/{campaign_id}"
        with connect(ws_url, open_timeout=5.0, close_timeout=1.0, max_size=None) as websocket:
            message = websocket.recv()
            assert isinstance(message, str)
            payload = json.loads(message)
            assert payload["type"] == "state"
            assert payload["snapshot"]["campaign_id"] == campaign_id
            assert payload["snapshot"]["transport"]["websocket_ready"] is True
            assert payload["snapshot"]["world_ready"] is True
    finally:
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5.0)

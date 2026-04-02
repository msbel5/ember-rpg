from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


REQUIRED_CAMPAIGN_PATHS = (
    "/game/campaigns",
    "/game/campaigns/creation/catalog",
    "/game/campaigns/load/{save_id}",
)
CAMPAIGN_HEALTH_PATH = "/game/health/campaign-client"


def wait_http(url: str, timeout: float = 25.0) -> int:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1) as response:  # noqa: S310 - local dev endpoint
                return int(response.status)
        except (URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def build_backend_url(host: str, port: int, template_url: str = "http://127.0.0.1:8741") -> str:
    parsed = urlsplit(template_url)
    scheme = parsed.scheme or "http"
    return urlunsplit((scheme, f"{host}:{port}", "", "", ""))


def fetch_backend_health(base_url: str, timeout: float = 2.0) -> dict[str, object] | None:
    try:
        with urlopen(f"{base_url.rstrip('/')}{CAMPAIGN_HEALTH_PATH}", timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, socket.timeout, ConnectionError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    required_keys = {"ok", "campaign_creation", "campaign_runtime", "campaign_save_load"}
    if not required_keys.issubset(payload.keys()):
        return None
    return payload


def backend_supports_paths(
    base_url: str,
    required_paths: tuple[str, ...] = REQUIRED_CAMPAIGN_PATHS,
    timeout: float = 2.0,
) -> bool:
    health = fetch_backend_health(base_url, timeout=timeout)
    if health is not None:
        return bool(
            health.get("ok")
            and health.get("campaign_creation")
            and health.get("campaign_runtime")
            and health.get("campaign_save_load")
        )
    try:
        with urlopen(f"{base_url.rstrip('/')}/openapi.json", timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, socket.timeout, ConnectionError, json.JSONDecodeError):
        return False
    paths = payload.get("paths", {})
    if not isinstance(paths, dict):
        return False
    return all(path in paths for path in required_paths)


def wait_backend_contract(
    base_url: str,
    required_paths: tuple[str, ...] = REQUIRED_CAMPAIGN_PATHS,
    timeout: float = 25.0,
) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if backend_supports_paths(base_url, required_paths=required_paths, timeout=1.0):
            return
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for backend contract at {base_url}.")


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_available_port(host: str, start_port: int, attempts: int = 50) -> int:
    candidate = start_port
    for _ in range(attempts):
        if is_port_available(host, candidate):
            return candidate
        candidate += 1
    raise RuntimeError(f"Could not find an available port on {host} starting at {start_port}.")


def terminate_process(process: subprocess.Popen[object] | None, timeout: float = 5.0) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)


def write_json_atomic(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".tmp")
    serialized = json.dumps(payload, indent=2)
    temp_path.write_text(serialized, encoding="utf-8")
    for _attempt in range(5):
        try:
            temp_path.replace(destination)
            return
        except PermissionError:
            time.sleep(0.05)
    # Windows can briefly lock the target while Godot polls it; fall back to a
    # direct overwrite so bridge traffic keeps moving instead of aborting.
    destination.write_text(serialized, encoding="utf-8")
    if temp_path.exists():
        temp_path.unlink(missing_ok=True)


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def wait_for_json(
    path: str | Path,
    predicate: Callable[[dict[str, Any]], bool],
    timeout: float = 10.0,
) -> dict[str, Any]:
    target = Path(path)
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        if target.exists():
            try:
                payload = read_json(target)
            except Exception as exc:  # pragma: no cover - transient write race
                last_error = exc
            else:
                if predicate(payload):
                    return payload
        time.sleep(0.05)
    raise RuntimeError(f"Timed out waiting for {target}: {last_error}")

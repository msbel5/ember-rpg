from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import urlopen


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
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(destination)


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

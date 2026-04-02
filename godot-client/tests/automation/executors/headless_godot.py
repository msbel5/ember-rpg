from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any
import os

from automation.artifacts import ArtifactManager
from automation.executors.base import AutomationExecutor, CapabilityUnavailableError
from automation.models import ArtifactRecord, AutomationScenario
from automation.process_utils import (
    build_backend_url,
    find_available_port,
    is_port_available,
    read_json,
    terminate_process,
    wait_backend_contract,
    wait_for_json,
    write_json_atomic,
    backend_supports_paths,
)


BACKEND_ENV = "EMBER_RPG_BACKEND_URL"


class HeadlessGodotExecutor(AutomationExecutor):
    name = "headless_godot"

    def __init__(self, scenario: AutomationScenario, artifacts: ArtifactManager):
        super().__init__(scenario, artifacts)
        self._backend_process: subprocess.Popen[str] | None = None
        self._client_process: subprocess.Popen[str] | None = None
        self._backend_started_here = False
        self._sequence = 0
        self._bridge_dir = self.artifacts.run_dir / "bridge"
        self._command_path = self._bridge_dir / "command.json"
        self._result_path = self._bridge_dir / "result.json"
        self._status_path = self._bridge_dir / "status.json"

    @property
    def capabilities(self) -> set[str]:
        return {"keyboard", "mouse", "viewport_capture", "issue_reporting", "headless", "semantic_controls"}

    def launch_backend(self) -> None:
        if backend_supports_paths(self.backend_url):
            return
        port = self.backend_port
        if not is_port_available(self.backend_host, port):
            port = find_available_port(self.backend_host, max(port + 1, 8765))
        self.backend_port = port
        self.backend_url = build_backend_url(self.backend_host, port, self.backend_url)
        self._backend_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                self.backend_host,
                "--port",
                str(self.backend_port),
            ],
            cwd=self.scenario.backend_cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._backend_started_here = True
        wait_backend_contract(self.backend_url, timeout=25.0)

    def stop_backend(self) -> None:
        if self._backend_started_here:
            terminate_process(self._backend_process)
        self._backend_process = None
        self._backend_started_here = False

    def launch_client(self) -> None:
        self._bridge_dir.mkdir(parents=True, exist_ok=True)
        for path in (self._command_path, self._result_path, self._status_path):
            if path.exists():
                path.unlink()
        args = [
            self.scenario.godot_console_executable,
            "--headless",
            "--path",
            self.scenario.godot_project_dir,
            "--script",
            "res://tests/automation/godot/automation_bridge_runner.gd",
            "--",
            "--scene",
            self.scenario.initial_scene,
            "--command-file",
            str(self._command_path),
            "--result-file",
            str(self._result_path),
            "--status-file",
            str(self._status_path),
            "--artifact-root",
            str(self.artifacts.run_dir),
        ]
        self._client_process = subprocess.Popen(
            args,
            cwd=self.scenario.godot_project_dir,
            env={**os.environ, BACKEND_ENV: self.backend_url},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        status = wait_for_json(self._status_path, lambda payload: payload.get("ready") is True, timeout=20.0)
        if status.get("status") == "error":
            raise RuntimeError(str(status.get("message", "Headless bridge failed to launch.")))

    def close_client(self) -> None:
        if self._client_process is not None and self._client_process.poll() is None:
            try:
                self._send_command("close")
            except Exception:
                pass
        terminate_process(self._client_process)
        self._client_process = None

    def activate_window(self) -> None:
        raise CapabilityUnavailableError("Headless Godot has no desktop window to activate.")

    def move_cursor(self, x: int, y: int) -> None:
        self._send_command("mouse_move", x=x, y=y)

    def mouse_down(self, button: str = "left") -> None:
        self._send_command("mouse_down", button=button)

    def mouse_up(self, button: str = "left") -> None:
        self._send_command("mouse_up", button=button)

    def mouse_click(self, x: int, y: int, button: str = "left") -> None:
        self._send_command("mouse_click", x=x, y=y, button=button)

    def key_down(self, key: str) -> None:
        self._send_command("key_down", key=key)

    def key_up(self, key: str) -> None:
        self._send_command("key_up", key=key)

    def key_hold(self, key: str, duration_ms: int) -> None:
        self._send_command("key_hold", key=key, duration_ms=duration_ms)

    def type_text(self, text: str) -> None:
        self._send_command("text", text=text)

    def focus_node(self, node_path: str) -> None:
        self._send_command("focus_node", node_path=node_path)

    def activate_node(self, node_path: str) -> None:
        self._send_command("activate_node", node_path=node_path)

    def set_text_node(self, node_path: str, text: str) -> None:
        self._send_command("set_text_node", node_path=node_path, text=text)

    def select_option_node(self, node_path: str, option_text: str) -> None:
        self._send_command("select_option_node", node_path=node_path, option_text=option_text)

    def click_node(
        self,
        node_path: str,
        *,
        normalized_x: float = 0.5,
        normalized_y: float = 0.5,
        button: str = "left",
    ) -> None:
        self._send_command(
            "click_node",
            node_path=node_path,
            normalized_x=normalized_x,
            normalized_y=normalized_y,
            button=button,
        )

    def current_scene_name(self) -> str:
        response = self.query_node_state()
        return str(response.get("scene_name", "")).strip()

    def node_exists(self, node_path: str) -> bool:
        response = self.query_node_state(node_path)
        return bool(response.get("node_exists", False))

    def query_node_state(self, node_path: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if node_path:
            payload["node_path"] = node_path
        return self._send_command("query_state", **payload)

    def capture_os(self, tag: str) -> ArtifactRecord:
        raise CapabilityUnavailableError("Headless Godot cannot capture an OS/window screenshot.")

    def capture_viewport(self, tag: str) -> ArtifactRecord:
        response = self._send_command("capture_viewport", tag=tag)
        source_path = Path(str(response.get("path", "")))
        if not source_path.exists():
            raise RuntimeError(f"Headless bridge reported a missing viewport artifact: {source_path}")
        scene_name = str(response.get("scene_name", "")).strip()
        if bool(response.get("synthetic", False)):
            note = "synthetic headless fallback"
            if scene_name:
                note = f"{note} [{scene_name}]"
        else:
            note = scene_name
        return self.artifacts.register(tag, "viewport_capture", source_path, note=note)

    def _docs_url(self) -> str:
        return f"{self.backend_url.rstrip('/')}/docs"

    def _send_command(self, action: str, **payload: Any) -> dict[str, Any]:
        if self._client_process is None or self._client_process.poll() is not None:
            raise RuntimeError("Headless Godot bridge is not running.")
        self._sequence += 1
        command = {"seq": self._sequence, "action": action, **payload}
        write_json_atomic(self._command_path, command)
        result = wait_for_json(
            self._result_path,
            lambda entry: int(entry.get("seq", -1)) == self._sequence,
            timeout=15.0,
        )
        status = str(result.get("status", "ok"))
        if status == "gap":
            raise CapabilityUnavailableError(str(result.get("message", "Executor capability gap.")))
        if status == "error":
            raise RuntimeError(str(result.get("message", "Headless bridge command failed.")))
        return result

    def bridge_status(self) -> dict[str, Any]:
        return read_json(self._status_path)

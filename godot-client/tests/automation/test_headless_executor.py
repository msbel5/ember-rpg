from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from automation.artifacts import ArtifactManager
from automation.executors.base import CapabilityUnavailableError
from automation.executors.headless_godot import HeadlessGodotExecutor
from automation.models import AutomationScenario


class DummyProcess:
    def __init__(self) -> None:
        self._poll = None

    def poll(self):
        return self._poll

    def terminate(self) -> None:
        self._poll = 0

    def wait(self, timeout: float | None = None) -> int:
        self._poll = 0
        return 0

    def kill(self) -> None:
        self._poll = 0


def _scenario(tmp_path: Path) -> AutomationScenario:
    return AutomationScenario(
        name="headless",
        description="",
        adapter_id="fantasy_ember",
        player_name="Chaos",
        create_new=True,
        requires_backend=False,
        backend_url="http://127.0.0.1:8000",
        backend_host="127.0.0.1",
        backend_port=8000,
        godot_executable="godot.exe",
        godot_console_executable="godot.console.exe",
        godot_project_dir=str(tmp_path / "godot-client"),
        backend_cwd=str(tmp_path / "frp-backend"),
        window_title="Ember RPG",
        initial_scene="res://scenes/title_screen.tscn",
        run_root=str(tmp_path / "out"),
        start_wait_ms=0,
        tags=(),
        steps=(),
    )


def test_headless_executor_capture_os_is_explicit_gap(tmp_path: Path) -> None:
    executor = HeadlessGodotExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "headless", run_id="one"))

    with pytest.raises(CapabilityUnavailableError, match="cannot capture an OS/window screenshot"):
        executor.capture_os("title")


def test_headless_executor_launch_and_capture_viewport(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    (tmp_path / "godot-client").mkdir()
    artifacts = ArtifactManager(tmp_path, "headless", run_id="two")
    executor = HeadlessGodotExecutor(scenario, artifacts)
    process = DummyProcess()
    source_capture = artifacts.run_dir / "bridge_capture.png"
    source_capture.write_bytes(b"png")

    def fake_popen(*args, **kwargs):
        return process

    def fake_wait_for_json(path, predicate, timeout=10.0):
        if str(path).endswith("status.json"):
            Path(path).write_text(json.dumps({"ready": True, "status": "ok"}), encoding="utf-8")
            return {"ready": True, "status": "ok"}
        payload = {"seq": 1, "status": "ok", "path": str(source_capture), "synthetic": True}
        assert predicate(payload)
        return payload

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr("automation.executors.headless_godot.wait_for_json", fake_wait_for_json)

    executor.launch_client()
    artifact = executor.capture_viewport("title")

    assert artifact.artifact_type == "viewport_capture"
    assert artifact.path == str(source_capture)
    assert artifact.note == "synthetic headless fallback"
    assert executor.bridge_status() == {"ready": True, "status": "ok"}


def test_headless_executor_activate_window_is_gap(tmp_path: Path) -> None:
    executor = HeadlessGodotExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "headless", run_id="three"))

    with pytest.raises(CapabilityUnavailableError, match="no desktop window"):
        executor.activate_window()

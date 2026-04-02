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
        backend_url="http://127.0.0.1:8741",
        backend_host="127.0.0.1",
        backend_port=8741,
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
        payload = {"seq": 1, "status": "ok", "path": str(source_capture), "synthetic": True, "scene_name": "TitleScreen"}
        assert predicate(payload)
        return payload

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr("automation.executors.headless_godot.wait_for_json", fake_wait_for_json)

    executor.launch_client()
    artifact = executor.capture_viewport("title")

    assert artifact.artifact_type == "viewport_capture"
    assert artifact.path == str(source_capture)
    assert artifact.note == "synthetic headless fallback [TitleScreen]"
    assert executor.bridge_status() == {"ready": True, "status": "ok"}


def test_headless_executor_activate_window_is_gap(tmp_path: Path) -> None:
    executor = HeadlessGodotExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "headless", run_id="three"))

    with pytest.raises(CapabilityUnavailableError, match="no desktop window"):
        executor.activate_window()


def test_headless_executor_semantic_actions_proxy_to_bridge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executor = HeadlessGodotExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "headless", run_id="four"))
    recorded: list[tuple[str, dict]] = []

    def fake_send_command(action: str, **payload):
        recorded.append((action, payload))
        if action == "query_state":
            response = {"status": "ok", "scene_name": "TitleScreen", "node_exists": False}
            if payload.get("node_path") == "TitleScreen/VBoxContainer/NewGameButton":
                response["node_exists"] = True
            return response
        return {"status": "ok"}

    monkeypatch.setattr(executor, "_send_command", fake_send_command)

    executor.focus_node("TitleScreen/VBoxContainer/NewGameButton")
    executor.activate_node("TitleScreen/VBoxContainer/NewGameButton")
    executor.set_text_node("TitleScreen/CharacterCreation/VBox/IdentitySection/NameInput", "Nova")
    executor.select_option_node("TitleScreen/CharacterCreation/VBox/IdentitySection/AdapterOption", "Sci-Fi Frontier")
    executor.click_node("MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer", normalized_x=0.25, normalized_y=0.75)
    assert executor.current_scene_name() == "TitleScreen"
    assert executor.node_exists("TitleScreen/VBoxContainer/NewGameButton") is True

    assert recorded == [
        ("focus_node", {"node_path": "TitleScreen/VBoxContainer/NewGameButton"}),
        ("activate_node", {"node_path": "TitleScreen/VBoxContainer/NewGameButton"}),
        ("set_text_node", {"node_path": "TitleScreen/CharacterCreation/VBox/IdentitySection/NameInput", "text": "Nova"}),
        ("select_option_node", {"node_path": "TitleScreen/CharacterCreation/VBox/IdentitySection/AdapterOption", "option_text": "Sci-Fi Frontier"}),
        (
            "click_node",
            {
                "node_path": "MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer",
                "normalized_x": 0.25,
                "normalized_y": 0.75,
                "button": "left",
            },
        ),
        ("query_state", {}),
        ("query_state", {"node_path": "TitleScreen/VBoxContainer/NewGameButton"}),
    ]


def test_headless_executor_launch_backend_uses_fallback_port_when_existing_service_is_incompatible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenario = _scenario(tmp_path)
    executor = HeadlessGodotExecutor(scenario, ArtifactManager(tmp_path, "headless", run_id="five"))
    process = DummyProcess()
    popen_calls: list[list[str]] = []

    monkeypatch.setattr("automation.executors.headless_godot.is_port_available", lambda *_args, **_kwargs: False)
    monkeypatch.setattr("automation.executors.headless_godot.find_available_port", lambda *_args, **_kwargs: 8765)
    monkeypatch.setattr("automation.executors.headless_godot.wait_backend_contract", lambda *_args, **_kwargs: None)

    def fake_popen(args, **kwargs):
        popen_calls.append(list(args))
        return process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    executor.launch_backend()

    assert executor.backend_url == "http://127.0.0.1:8765"
    assert popen_calls[0][-1] == "8765"


def test_headless_executor_launch_client_passes_backend_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenario = _scenario(tmp_path)
    (tmp_path / "godot-client").mkdir()
    artifacts = ArtifactManager(tmp_path, "headless", run_id="six")
    executor = HeadlessGodotExecutor(scenario, artifacts)
    executor.backend_url = "http://127.0.0.1:8765"
    process = DummyProcess()
    popen_envs: list[dict[str, str]] = []

    def fake_popen(*args, **kwargs):
        popen_envs.append(kwargs["env"])
        return process

    def fake_wait_for_json(path, predicate, timeout=10.0):
        if str(path).endswith("status.json"):
            Path(path).write_text(json.dumps({"ready": True, "status": "ok"}), encoding="utf-8")
            return {"ready": True, "status": "ok"}
        raise AssertionError("unexpected wait_for_json call")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr("automation.executors.headless_godot.wait_for_json", fake_wait_for_json)

    executor.launch_client()

    assert popen_envs[0]["EMBER_RPG_BACKEND_URL"] == "http://127.0.0.1:8765"

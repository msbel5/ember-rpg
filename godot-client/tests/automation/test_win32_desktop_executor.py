from __future__ import annotations

from pathlib import Path
import subprocess

from automation.artifacts import ArtifactManager
from automation.executors import win32_desktop
from automation.executors.win32_desktop import Win32DesktopExecutor
from automation.models import AutomationScenario


def _scenario(tmp_path: Path) -> AutomationScenario:
    return AutomationScenario(
        name="desktop",
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


def test_win32_executor_maps_keys_and_buttons(tmp_path: Path) -> None:
    executor = Win32DesktopExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "desktop", run_id="one"))

    assert executor._vk_for_key("backspace") == 0x08
    assert executor._vk_for_key("enter") == 0x0D
    assert executor._vk_for_key("a") == ord("A")
    assert executor._normalize_button("right") == "right"


def test_win32_executor_capture_viewport_registers_copy(monkeypatch, tmp_path: Path) -> None:
    executor = Win32DesktopExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "desktop", run_id="two"))
    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    recorded: list[str] = []
    baselines: list[Path | None] = []

    monkeypatch.setattr(executor, "key_press", lambda key: recorded.append(key))
    monkeypatch.setattr(executor, "_latest_png", lambda: None)
    monkeypatch.setattr(
        executor,
        "_wait_for_viewport_capture",
        lambda baseline, timeout=5.0: baselines.append(baseline) or source,
    )

    artifact = executor.capture_viewport("title")

    assert recorded == ["f12"]
    assert baselines == [None]
    assert artifact.artifact_type == "viewport_capture"
    assert Path(artifact.path).read_bytes() == b"png"


def test_win32_executor_wait_for_viewport_capture_accepts_updated_same_path(
    monkeypatch, tmp_path: Path
) -> None:
    executor = Win32DesktopExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "desktop", run_id="three"))
    source = tmp_path / "source.png"
    source.write_bytes(b"before")
    baseline = source
    poll_count = {"value": 0}

    def latest_png() -> Path:
        poll_count["value"] += 1
        if poll_count["value"] == 1:
            source.write_bytes(b"after")
        return source

    monkeypatch.setattr(executor, "_latest_png", latest_png)

    assert executor._wait_for_viewport_capture(baseline, timeout=0.5) == source


def test_win32_executor_reports_missing_environment_dependencies(monkeypatch, tmp_path: Path) -> None:
    executor = Win32DesktopExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "desktop", run_id="four"))

    def fake_find_spec(module_name: str):
        if module_name in {"win32gui", "PIL"}:
            return None
        class _Spec:
            pass
        return _Spec()

    monkeypatch.setattr(win32_desktop.importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(win32_desktop, "WIN32_AVAILABLE", False)

    health = executor.environment_health()

    assert health["ok"] is False
    assert "pywin32" in health["missing"]
    assert "Pillow" in health["missing"]


def test_win32_executor_launch_backend_uses_fallback_port(monkeypatch, tmp_path: Path) -> None:
    executor = Win32DesktopExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "desktop", run_id="five"))
    popen_calls: list[list[str]] = []

    monkeypatch.setattr(win32_desktop, "is_port_available", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(win32_desktop, "find_available_port", lambda *_args, **_kwargs: 8765)
    monkeypatch.setattr(win32_desktop, "wait_backend_contract", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kwargs: popen_calls.append(list(args)) or object())

    executor.launch_backend()

    assert executor.backend_url == "http://127.0.0.1:8765"
    assert popen_calls[0][-1] == "8765"


def test_win32_executor_launch_client_passes_backend_and_bridge_envs(
    monkeypatch, tmp_path: Path
) -> None:
    scenario = _scenario(tmp_path)
    (tmp_path / "godot-client").mkdir()
    artifacts = ArtifactManager(tmp_path, "desktop", run_id="six")
    executor = Win32DesktopExecutor(scenario, artifacts)
    executor.backend_url = "http://127.0.0.1:8765"
    popen_envs: list[dict[str, str]] = []

    class DummyProcess:
        pid = 1234

        def poll(self):
            return None

    monkeypatch.setattr(win32_desktop, "WIN32_AVAILABLE", True)
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: popen_envs.append(kwargs["env"]) or DummyProcess())
    monkeypatch.setattr(executor, "_find_hwnd", lambda _pid: 100)
    monkeypatch.setattr(executor, "activate_window", lambda: None)
    monkeypatch.setattr(
        win32_desktop,
        "wait_for_json",
        lambda path, predicate, timeout=10.0: {"ready": True, "status": "ok"} if predicate({"ready": True, "status": "ok"}) else {},
    )

    executor.launch_client()

    env = popen_envs[0]
    assert env["EMBER_RPG_BACKEND_URL"] == "http://127.0.0.1:8765"
    assert env["EMBER_AUTOMATION_COMMAND_FILE"].endswith("bridge\\command.json")
    assert env["EMBER_AUTOMATION_RESULT_FILE"].endswith("bridge\\result.json")
    assert env["EMBER_AUTOMATION_STATUS_FILE"].endswith("bridge\\status.json")


def test_win32_executor_semantic_actions_proxy_to_runtime_bridge(monkeypatch, tmp_path: Path) -> None:
    executor = Win32DesktopExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "desktop", run_id="seven"))
    recorded: list[tuple[str, dict]] = []

    def fake_send_command(action: str, **payload):
        recorded.append((action, payload))
        if action == "query_state":
            response = {"status": "ok", "scene_name": "TitleScreen", "node_exists": False}
            if payload.get("node_path") == "TitleMenu/Shell/RootVBox/MenuPanel/MenuMargin/MenuVBox/NewGameButton":
                response["node_exists"] = True
            return response
        return {"status": "ok"}

    monkeypatch.setattr(executor, "_send_command", fake_send_command)

    executor.focus_node("TitleMenu/Shell/RootVBox/MenuPanel/MenuMargin/MenuVBox/NewGameButton")
    executor.activate_node("TitleMenu/Shell/RootVBox/MenuPanel/MenuMargin/MenuVBox/NewGameButton")
    executor.set_text_node("CharacterCreation/VBox/CreationBody/FormPane/FormScroll/FormContent/IdentitySection/NameInput", "Nova")
    executor.click_node("TitleMenu/Shell/RootVBox/MenuPanel/MenuMargin/MenuVBox/NewGameButton", normalized_x=0.5, normalized_y=0.5)
    assert executor.current_scene_name() == "TitleScreen"
    assert executor.node_exists("TitleMenu/Shell/RootVBox/MenuPanel/MenuMargin/MenuVBox/NewGameButton") is True

    assert recorded == [
        ("focus_node", {"node_path": "TitleMenu/Shell/RootVBox/MenuPanel/MenuMargin/MenuVBox/NewGameButton"}),
        ("activate_node", {"node_path": "TitleMenu/Shell/RootVBox/MenuPanel/MenuMargin/MenuVBox/NewGameButton"}),
        (
            "set_text_node",
            {
                "node_path": "CharacterCreation/VBox/CreationBody/FormPane/FormScroll/FormContent/IdentitySection/NameInput",
                "text": "Nova",
            },
        ),
        (
            "click_node",
            {
                "node_path": "TitleMenu/Shell/RootVBox/MenuPanel/MenuMargin/MenuVBox/NewGameButton",
                "normalized_x": 0.5,
                "normalized_y": 0.5,
                "button": "left",
            },
        ),
        ("query_state", {}),
        ("query_state", {"node_path": "TitleMenu/Shell/RootVBox/MenuPanel/MenuMargin/MenuVBox/NewGameButton"}),
    ]

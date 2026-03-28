from __future__ import annotations

from pathlib import Path

from automation.artifacts import ArtifactManager
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


def test_win32_executor_maps_keys_and_buttons(tmp_path: Path) -> None:
    executor = Win32DesktopExecutor(_scenario(tmp_path), ArtifactManager(tmp_path, "desktop", run_id="one"))

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

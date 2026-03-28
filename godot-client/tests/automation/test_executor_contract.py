from __future__ import annotations

from pathlib import Path

from automation.artifacts import ArtifactManager
from automation.executors.base import AutomationExecutor
from automation.models import ArtifactRecord, AutomationScenario


class DummyExecutor(AutomationExecutor):
    name = "dummy"

    def __init__(self, scenario: AutomationScenario, artifacts: ArtifactManager):
        super().__init__(scenario, artifacts)
        self.calls: list[tuple] = []

    @property
    def capabilities(self) -> set[str]:
        return {"keyboard", "mouse", "viewport_capture"}

    def launch_backend(self) -> None:
        self.calls.append(("launch_backend",))

    def stop_backend(self) -> None:
        self.calls.append(("stop_backend",))

    def launch_client(self) -> None:
        self.calls.append(("launch_client",))

    def close_client(self) -> None:
        self.calls.append(("close_client",))

    def activate_window(self) -> None:
        self.calls.append(("activate_window",))

    def move_cursor(self, x: int, y: int) -> None:
        self.calls.append(("move_cursor", x, y))

    def mouse_down(self, button: str = "left") -> None:
        self.calls.append(("mouse_down", button))

    def mouse_up(self, button: str = "left") -> None:
        self.calls.append(("mouse_up", button))

    def mouse_click(self, x: int, y: int, button: str = "left") -> None:
        self.calls.append(("mouse_click", x, y, button))

    def key_down(self, key: str) -> None:
        self.calls.append(("key_down", key))

    def key_up(self, key: str) -> None:
        self.calls.append(("key_up", key))

    def type_text(self, text: str) -> None:
        self.calls.append(("type_text", text))

    def capture_os(self, tag: str) -> ArtifactRecord:
        self.calls.append(("capture_os", tag))
        return ArtifactRecord(step_id=tag, artifact_type="os_screenshot", path=f"{tag}.png")

    def capture_viewport(self, tag: str) -> ArtifactRecord:
        self.calls.append(("capture_viewport", tag))
        return ArtifactRecord(step_id=tag, artifact_type="viewport_capture", path=f"{tag}.png")


def _scenario() -> AutomationScenario:
    return AutomationScenario(
        name="contract",
        description="",
        adapter_id="fantasy_ember",
        player_name="Test",
        create_new=True,
        requires_backend=False,
        backend_url="http://127.0.0.1:8000",
        backend_host="127.0.0.1",
        backend_port=8000,
        godot_executable="godot.exe",
        godot_console_executable="godot.console.exe",
        godot_project_dir="C:/tmp/godot-client",
        backend_cwd="C:/tmp/frp-backend",
        window_title="Ember RPG",
        initial_scene="res://scenes/title_screen.tscn",
        run_root="C:/tmp/out",
        start_wait_ms=0,
        tags=(),
        steps=(),
    )


def test_base_executor_key_press_uses_key_down_and_up(tmp_path: Path) -> None:
    executor = DummyExecutor(_scenario(), ArtifactManager(tmp_path, "contract", run_id="one"))

    executor.key_press("enter")

    assert executor.calls == [("key_down", "enter"), ("key_up", "enter")]


def test_mark_gap_formats_executor_name(tmp_path: Path) -> None:
    executor = DummyExecutor(_scenario(), ArtifactManager(tmp_path, "contract", run_id="two"))

    assert executor.mark_gap("capture_os") == "dummy does not support `capture_os`"

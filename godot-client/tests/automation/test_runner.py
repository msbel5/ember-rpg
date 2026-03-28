from __future__ import annotations

from pathlib import Path

import pytest

from automation.artifacts import ArtifactManager
from automation.executors.base import AutomationExecutor
from automation.models import ArtifactRecord, AutomationScenario
from automation.runner import EXECUTOR_TYPES, run_scenario


class FakeExecutor(AutomationExecutor):
    name = "fake"

    def __init__(self, scenario: AutomationScenario, artifacts: ArtifactManager):
        super().__init__(scenario, artifacts)
        self.calls: list[str] = []

    @property
    def capabilities(self) -> set[str]:
        return {"keyboard", "mouse", "os_capture", "viewport_capture"}

    def launch_backend(self) -> None:
        self.calls.append("launch_backend")

    def stop_backend(self) -> None:
        self.calls.append("stop_backend")

    def launch_client(self) -> None:
        self.calls.append("launch_client")

    def close_client(self) -> None:
        self.calls.append("close_client")

    def activate_window(self) -> None:
        self.calls.append("activate_window")

    def move_cursor(self, x: int, y: int) -> None:
        self.calls.append(f"move_cursor:{x},{y}")

    def mouse_down(self, button: str = "left") -> None:
        self.calls.append(f"mouse_down:{button}")

    def mouse_up(self, button: str = "left") -> None:
        self.calls.append(f"mouse_up:{button}")

    def mouse_click(self, x: int, y: int, button: str = "left") -> None:
        self.calls.append(f"mouse_click:{x},{y},{button}")

    def key_down(self, key: str) -> None:
        self.calls.append(f"key_down:{key}")

    def key_up(self, key: str) -> None:
        self.calls.append(f"key_up:{key}")

    def type_text(self, text: str) -> None:
        self.calls.append(f"text:{text}")

    def capture_os(self, tag: str) -> ArtifactRecord:
        return self.artifacts.write_text(tag, "os_screens", "ok", ".png")

    def capture_viewport(self, tag: str) -> ArtifactRecord:
        return self.artifacts.write_text(tag, "viewport_captures", "ok", ".png")


def test_runner_executes_scenario_and_writes_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "runner_smoke"
description = "Runner smoke"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "focus"
action = "activate_window"
capture_os = true

[[steps]]
id = "viewport"
action = "capture_viewport"
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", FakeExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is True
    assert result.json_report.exists()
    assert result.markdown_report.exists()
    assert len(result.report.artifacts) == 2

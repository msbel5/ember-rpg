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


class ValidatingExecutor(FakeExecutor):
    def capture_os(self, tag: str) -> ArtifactRecord:
        path = self.artifacts.artifact_path("os_screens", tag, ".png")
        path.write_bytes(b"same")
        return self.artifacts.register(tag, "os_screenshot", path)

    def capture_viewport(self, tag: str) -> ArtifactRecord:
        path = self.artifacts.artifact_path("viewport_captures", tag, ".png")
        path.write_bytes(tag.encode("utf-8"))
        note = "C:/tmp/phase2/title/title_screen.png"
        return self.artifacts.register(tag, "viewport_capture", path, note=note)


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


def test_runner_fails_when_viewport_note_expectation_is_not_met(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "viewport_guard"
description = "Viewport note validation"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "load_first_save"
action = "capture_viewport"
expected = "gameplay scene loads"
expect_note_contains = "phase2/game"
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", ValidatingExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is False
    assert any(issue.step_id == "load_first_save" for issue in result.report.issues)


def test_runner_fails_when_artifact_does_not_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "artifact_guard"
description = "Artifact diff validation"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "first"
action = "capture_os"

[[steps]]
id = "second"
action = "capture_os"
expected = "screen changes after the step"
expect_artifact_differs_from = "first:os_screenshot"
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", ValidatingExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is False
    assert any(issue.step_id == "second" for issue in result.report.issues)

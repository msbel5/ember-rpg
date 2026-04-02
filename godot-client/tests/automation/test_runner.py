from __future__ import annotations

from pathlib import Path

import pytest

from automation.artifacts import ArtifactManager
from automation.executors.base import AutomationExecutor
from automation.models import ArtifactRecord, AutomationScenario
from automation.runner import EXECUTOR_TYPES, run_scenario


@pytest.fixture(autouse=True)
def _stub_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("automation.runner.reset_dev_state", lambda: {})


class FakeExecutor(AutomationExecutor):
    name = "fake"

    def __init__(self, scenario: AutomationScenario, artifacts: ArtifactManager):
        super().__init__(scenario, artifacts)
        self.calls: list[str] = []
        self.scene_name = "TitleScreen"
        self.nodes: set[str] = set()
        self.node_states: dict[str, dict[str, object]] = {}

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

    def focus_node(self, node_path: str) -> None:
        self.calls.append(f"focus_node:{node_path}")

    def activate_node(self, node_path: str) -> None:
        self.calls.append(f"activate_node:{node_path}")

    def set_text_node(self, node_path: str, text: str) -> None:
        self.calls.append(f"set_text_node:{node_path}={text}")

    def select_option_node(self, node_path: str, option_text: str) -> None:
        self.calls.append(f"select_option_node:{node_path}={option_text}")

    def click_node(
        self,
        node_path: str,
        *,
        normalized_x: float = 0.5,
        normalized_y: float = 0.5,
        button: str = "left",
    ) -> None:
        self.calls.append(f"click_node:{node_path}:{normalized_x:.2f},{normalized_y:.2f},{button}")

    def current_scene_name(self) -> str:
        self.calls.append("current_scene_name")
        return self.scene_name

    def node_exists(self, node_path: str) -> bool:
        self.calls.append(f"node_exists:{node_path}")
        return node_path in self.nodes

    def query_node_state(self, node_path: str | None = None) -> dict[str, object]:
        self.calls.append(f"query_node_state:{node_path or ''}")
        if not node_path:
            return {"scene_name": self.scene_name}
        state = {"scene_name": self.scene_name, "node_exists": node_path in self.nodes, "node_visible": False, "node_text": ""}
        state.update(self.node_states.get(node_path, {}))
        return state

    def capture_os(self, tag: str) -> ArtifactRecord:
        return self.artifacts.write_text(tag, "os_screens", "ok", ".png")

    def capture_viewport(self, tag: str) -> ArtifactRecord:
        return self.artifacts.write_text(tag, "viewport_captures", "ok", ".png")


class MissingDependencyExecutor(FakeExecutor):
    def environment_health(self) -> dict:
        return {
            "ok": False,
            "summary": "Desktop automation environment is incomplete: pywin32, Pillow.",
            "notes": [
                "Missing `pywin32`.",
                "Missing `Pillow`.",
            ],
        }


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


class RedirectingBackendExecutor(FakeExecutor):
    def launch_backend(self) -> None:
        self.backend_url = "http://127.0.0.1:8765"
        self.calls.append("launch_backend")


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


def test_runner_restart_client_action_relaunches_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "restart_client_smoke"
description = "Runner relaunches the client"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "restart"
action = "restart_client"
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", FakeExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is True
    assert result.report.steps_run == ["restart"]


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


def test_runner_fails_fast_when_executor_environment_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "env_guard"
description = "Desktop environment validation"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "focus"
action = "activate_window"
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", MissingDependencyExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is False
    assert any(issue.step_id == "environment" for issue in result.report.issues)
    assert any("pywin32" in note for note in result.report.notes)


def test_runner_dispatches_semantic_node_actions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "semantic_actions"
description = "semantic node action dispatch"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "focus"
action = "focus_node"
node_path = "TitleScreen/VBoxContainer/NewGameButton"

[[steps]]
id = "activate"
action = "activate_node"
node_path = "TitleScreen/VBoxContainer/NewGameButton"

[[steps]]
id = "set_text"
action = "set_text_node"
node_path = "TitleScreen/CharacterCreation/VBox/IdentitySection/NameInput"
text = "Nova"

[[steps]]
id = "select_adapter"
action = "select_option_node"
node_path = "TitleScreen/CharacterCreation/VBox/IdentitySection/AdapterOption"
option_text = "Sci-Fi Frontier"

[[steps]]
id = "click_world"
action = "click_node"
node_path = "MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer"
normalized_x = 0.25
normalized_y = 0.75
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", FakeExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is True
    assert not result.report.issues


def test_runner_waits_for_scene_and_node_semantically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "semantic_waits"
description = "semantic scene and node waits"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "wait_scene"
action = "wait_for_scene"
scene_name = "GameSession"
duration_ms = 50

[[steps]]
id = "wait_node"
action = "wait_for_node"
node_path = "MainMargin/MainVBox/CommandBar/CommandVBox/InputRow/TextInput"
duration_ms = 50
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    class WaitingExecutor(FakeExecutor):
        def current_scene_name(self) -> str:
            self.scene_name = "GameSession"
            return super().current_scene_name()

        def node_exists(self, node_path: str) -> bool:
            self.nodes.add(node_path)
            return super().node_exists(node_path)

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", WaitingExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is True
    assert not result.report.issues


def test_runner_waits_for_visible_node_and_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "semantic_visibility"
description = "semantic visible node and text waits"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "wait_visible"
action = "wait_for_node_visible"
node_path = "CharacterCreation/VBox/ButtonRow/StartButton"
duration_ms = 50

[[steps]]
id = "wait_text"
action = "wait_for_node_text"
node_path = "CharacterCreation/VBox/CreationBody/PreviewPane/PreviewMargin/PreviewVBox/PreviewHeading"
text = "Dossier"
duration_ms = 50
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    class VisibleExecutor(FakeExecutor):
        def query_node_state(self, node_path: str | None = None) -> dict[str, object]:
            self.node_states["CharacterCreation/VBox/ButtonRow/StartButton"] = {
                "node_exists": True,
                "node_visible": True,
            }
            self.node_states["CharacterCreation/VBox/CreationBody/PreviewPane/PreviewMargin/PreviewVBox/PreviewHeading"] = {
                "node_exists": True,
                "node_visible": True,
                "node_text": "Dossier",
            }
            return super().query_node_state(node_path)

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", VisibleExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is True
    assert not result.report.issues


def test_runner_waits_for_hidden_node(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "semantic_hidden"
description = "semantic hidden node wait"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "wait_hidden"
action = "wait_for_node_hidden"
node_path = "MainMargin/MainVBox/ContentSplit/WorldPane/DialogOverlay"
duration_ms = 50
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    class HiddenExecutor(FakeExecutor):
        def query_node_state(self, node_path: str | None = None) -> dict[str, object]:
            self.node_states["MainMargin/MainVBox/ContentSplit/WorldPane/DialogOverlay"] = {
                "node_exists": True,
                "node_visible": False,
            }
            return super().query_node_state(node_path)

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", HiddenExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is True
    assert not result.report.issues


def test_runner_can_remember_node_text_and_wait_for_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "semantic_text_change"
description = "semantic remembered text wait"
requires_backend = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "remember_dialog"
action = "remember_node_text"
node_path = "DialogOverlay/NpcText"

[[steps]]
id = "wait_dialog_changed"
action = "wait_for_node_text_changed"
node_path = "DialogOverlay/NpcText"
reference_step_id = "remember_dialog"
duration_ms = 50
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    class ChangedTextExecutor(FakeExecutor):
        _queries = 0

        def query_node_state(self, node_path: str | None = None) -> dict[str, object]:
            if node_path == "DialogOverlay/NpcText":
                self._queries += 1
                self.node_states[node_path] = {
                    "node_exists": True,
                    "node_visible": True,
                    "node_text": "First line" if self._queries == 1 else "Second line",
                }
            return super().query_node_state(node_path)

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", ChangedTextExecutor)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is True
    assert not result.report.issues


def test_runner_uses_executor_backend_url_for_resume_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        """
[scenario]
name = "resume_fixture_backend_redirect"
description = "resume fixture uses executor backend url"
requires_backend = true
create_new = false
run_root = "__RUN_ROOT__"

[[steps]]
id = "focus"
action = "activate_window"
""".strip().replace("__RUN_ROOT__", str(tmp_path / "out").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    requests: list[str] = []

    def fake_json_request(url: str, payload: dict[str, object]) -> dict[str, object]:
        requests.append(url)
        if url.endswith("/game/campaigns"):
            return {"campaign_id": "cmp_1"}
        return {"slot_name": "slot_1"}

    monkeypatch.setitem(EXECUTOR_TYPES, "fake", RedirectingBackendExecutor)
    monkeypatch.setattr("automation.runner._json_request", fake_json_request)

    result = run_scenario(scenario_path, "fake")

    assert result.report.success is True
    assert requests[0].startswith("http://127.0.0.1:8765/")
    assert any("did not satisfy the campaign contract" in note for note in result.report.notes)

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


Severity = Literal["info", "minor", "major", "critical"]


@dataclass(frozen=True)
class ArtifactRecord:
    step_id: str
    artifact_type: str
    path: str
    note: str = ""


@dataclass(frozen=True)
class IssueRecord:
    step_id: str
    severity: Severity
    expected: str
    actual: str
    artifact_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionStep:
    id: str
    action: str
    description: str = ""
    key: str | None = None
    text: str | None = None
    x: int | None = None
    y: int | None = None
    button: str = "left"
    duration_ms: int = 0
    repeat: int = 1
    wait_ms: int = 0
    capture_os: bool = False
    capture_viewport: bool = False
    expected: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationScenario:
    name: str
    description: str
    adapter_id: str
    player_name: str
    create_new: bool
    requires_backend: bool
    backend_url: str
    backend_host: str
    backend_port: int
    godot_executable: str
    godot_console_executable: str
    godot_project_dir: str
    backend_cwd: str
    window_title: str
    initial_scene: str
    run_root: str
    start_wait_ms: int
    tags: tuple[str, ...]
    steps: tuple[ActionStep, ...]


@dataclass
class RunReport:
    scenario_name: str
    executor_name: str
    started_at: str
    finished_at: str
    success: bool
    steps_run: list[str] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    issues: list[IssueRecord] = field(default_factory=list)
    capability_gaps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    report_dir: str = ""

    def add_artifact(self, artifact: ArtifactRecord) -> None:
        self.artifacts.append(artifact)

    def add_issue(self, issue: IssueRecord) -> None:
        self.issues.append(issue)
        if issue.severity in {"major", "critical"}:
            self.success = False

    def add_gap(self, gap: str) -> None:
        if gap not in self.capability_gaps:
            self.capability_gaps.append(gap)

    def add_note(self, note: str) -> None:
        self.notes.append(note)

    @property
    def report_path(self) -> Path:
        return Path(self.report_dir) if self.report_dir else Path(".")

    @property
    def status(self) -> str:
        if not self.success:
            return "fail"
        if self.capability_gaps:
            return "partial"
        return "pass"

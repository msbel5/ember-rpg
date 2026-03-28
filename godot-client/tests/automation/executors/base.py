from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path

from automation.artifacts import ArtifactManager
from automation.models import ArtifactRecord, AutomationScenario, IssueRecord, Severity


class CapabilityUnavailableError(RuntimeError):
    """Raised when an executor cannot perform a requested capability."""


class AutomationExecutor(ABC):
    name = "base"

    def __init__(self, scenario: AutomationScenario, artifacts: ArtifactManager):
        self.scenario = scenario
        self.artifacts = artifacts
        self.issues: list[IssueRecord] = []

    @property
    @abstractmethod
    def capabilities(self) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    def launch_backend(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop_backend(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def launch_client(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close_client(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def activate_window(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def move_cursor(self, x: int, y: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def mouse_down(self, button: str = "left") -> None:
        raise NotImplementedError

    @abstractmethod
    def mouse_up(self, button: str = "left") -> None:
        raise NotImplementedError

    @abstractmethod
    def mouse_click(self, x: int, y: int, button: str = "left") -> None:
        raise NotImplementedError

    @abstractmethod
    def key_down(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def key_up(self, key: str) -> None:
        raise NotImplementedError

    def key_press(self, key: str) -> None:
        self.key_down(key)
        self.key_up(key)

    def key_hold(self, key: str, duration_ms: int) -> None:
        self.key_down(key)
        time.sleep(max(duration_ms, 0) / 1000.0)
        self.key_up(key)

    @abstractmethod
    def type_text(self, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def capture_os(self, tag: str) -> ArtifactRecord:
        raise NotImplementedError

    @abstractmethod
    def capture_viewport(self, tag: str) -> ArtifactRecord:
        raise NotImplementedError

    def record_issue(
        self,
        step_id: str,
        severity: Severity,
        expected: str,
        actual: str,
        artifact_paths: tuple[str, ...] = (),
    ) -> IssueRecord:
        issue = IssueRecord(
            step_id=step_id,
            severity=severity,
            expected=expected,
            actual=actual,
            artifact_paths=artifact_paths,
        )
        self.issues.append(issue)
        return issue

    def mark_gap(self, capability: str) -> str:
        return f"{self.name} does not support `{capability}`"

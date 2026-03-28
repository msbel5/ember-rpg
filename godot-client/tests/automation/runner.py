from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from automation.artifacts import ArtifactManager
from automation.executors.base import AutomationExecutor, CapabilityUnavailableError
from automation.executors.headless_godot import HeadlessGodotExecutor
from automation.executors.win32_desktop import Win32DesktopExecutor
from automation.models import ActionStep, ArtifactRecord, RunReport
from automation.report_writer import write_report
from automation.scenario_loader import load_scenario


EXECUTOR_TYPES = {
    "win32_desktop": Win32DesktopExecutor,
    "headless_godot": HeadlessGodotExecutor,
}


@dataclass(frozen=True)
class RunnerResult:
    json_report: Path
    markdown_report: Path
    report: RunReport


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the visual automation backup harness.")
    parser.add_argument("--scenario", required=True, help="Path to a TOML scenario file.")
    parser.add_argument(
        "--executor",
        choices=sorted(EXECUTOR_TYPES),
        default="win32_desktop",
        help="Executor backend to use.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_scenario(args.scenario, args.executor)
    print(result.markdown_report)
    return 0 if result.report.success else 1


def run_scenario(scenario_path: str | Path, executor_name: str) -> RunnerResult:
    scenario = load_scenario(scenario_path)
    artifacts = ArtifactManager(Path(scenario.run_root), scenario.name)
    executor = _build_executor(executor_name, scenario, artifacts)
    started_at = datetime.now(timezone.utc).isoformat()
    report = RunReport(
        scenario_name=scenario.name,
        executor_name=executor.name,
        started_at=started_at,
        finished_at=started_at,
        success=True,
        report_dir=str(artifacts.run_dir),
    )

    try:
        if scenario.requires_backend:
            executor.launch_backend()
        executor.launch_client()
        for step in scenario.steps:
            report.steps_run.append(step.id)
            _run_step(executor, report, step)
    except Exception as exc:  # pragma: no cover - exercised by higher-level scenario runs
        report.success = False
        report.add_note(f"Unhandled runner error: {exc}")
        executor.record_issue("runner", "critical", "scenario completes", str(exc))
    finally:
        report.issues.extend(issue for issue in executor.issues if issue not in report.issues)
        executor.close_client()
        if scenario.requires_backend:
            executor.stop_backend()
        report.finished_at = datetime.now(timezone.utc).isoformat()

    json_report, markdown_report = write_report(report, artifacts)
    return RunnerResult(json_report=json_report, markdown_report=markdown_report, report=report)


def _build_executor(executor_name: str, scenario, artifacts) -> AutomationExecutor:
    executor_type = EXECUTOR_TYPES[executor_name]
    return executor_type(scenario, artifacts)


def _run_step(executor: AutomationExecutor, report: RunReport, step: ActionStep) -> None:
    for _ in range(step.repeat):
        try:
            artifact = _dispatch_action(executor, step)
        except CapabilityUnavailableError as exc:
            gap = executor.mark_gap(f"{step.id}:{step.action}")
            report.add_gap(gap)
            report.add_note(str(exc))
            report.add_issue(executor.record_issue(step.id, "major", step.expected or step.action, str(exc)))
            return
        if artifact is not None:
            report.add_artifact(artifact)
        if step.wait_ms:
            time.sleep(step.wait_ms / 1000.0)

    if step.capture_os:
        _capture(report, executor, step, "os")
    if step.capture_viewport:
        _capture(report, executor, step, "viewport")


def _dispatch_action(executor: AutomationExecutor, step: ActionStep) -> ArtifactRecord | None:
    action = step.action
    if action == "activate_window":
        executor.activate_window()
    elif action == "capture_os":
        return executor.capture_os(step.id)
    elif action == "capture_viewport":
        return executor.capture_viewport(step.id)
    elif action == "wait":
        time.sleep(max(step.duration_ms, step.wait_ms) / 1000.0)
    elif action == "mouse_move":
        _require_xy(step)
        executor.move_cursor(step.x, step.y)  # type: ignore[arg-type]
    elif action == "mouse_down":
        executor.mouse_down(step.button)
    elif action == "mouse_up":
        executor.mouse_up(step.button)
    elif action == "mouse_click":
        _require_xy(step)
        executor.mouse_click(step.x, step.y, step.button)  # type: ignore[arg-type]
    elif action == "key_down":
        _require_key(step)
        executor.key_down(step.key or "")
    elif action == "key_up":
        _require_key(step)
        executor.key_up(step.key or "")
    elif action == "key_press":
        _require_key(step)
        executor.key_press(step.key or "")
    elif action == "key_hold":
        _require_key(step)
        executor.key_hold(step.key or "", step.duration_ms)
    elif action == "text":
        if step.text is None:
            raise ValueError(f"Step {step.id} requires text")
        executor.type_text(step.text)
    else:
        raise ValueError(f"Unsupported action `{action}` in step {step.id}")
    return None


def _capture(report: RunReport, executor: AutomationExecutor, step: ActionStep, artifact_kind: str) -> None:
    try:
        artifact = (
            executor.capture_os(step.id)
            if artifact_kind == "os"
            else executor.capture_viewport(step.id)
        )
        report.add_artifact(artifact)
    except CapabilityUnavailableError as exc:
        report.add_gap(executor.mark_gap(f"{step.id}:{artifact_kind}_capture"))
        report.add_note(str(exc))


def _require_xy(step: ActionStep) -> None:
    if step.x is None or step.y is None:
        raise ValueError(f"Step {step.id} requires x and y coordinates")


def _require_key(step: ActionStep) -> None:
    if not step.key:
        raise ValueError(f"Step {step.id} requires a key")


if __name__ == "__main__":
    raise SystemExit(main())

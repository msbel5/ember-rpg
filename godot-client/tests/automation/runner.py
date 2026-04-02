from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib import request

from automation.artifacts import ArtifactManager
from automation.executors.base import AutomationExecutor, CapabilityUnavailableError
from automation.executors.headless_godot import HeadlessGodotExecutor
from automation.executors.win32_desktop import Win32DesktopExecutor
from automation.models import ActionStep, ArtifactRecord, RunReport
from automation.report_writer import write_report
from automation.scenario_loader import load_scenario
from tools.reset_dev_state import reset_dev_state


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
    reset_dev_state()
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
    step_memory: dict[str, str] = {}

    try:
        if not _check_environment(executor, report):
            json_report, markdown_report = write_report(report, artifacts)
            return RunnerResult(json_report=json_report, markdown_report=markdown_report, report=report)
        prepared_slot = ""
        if scenario.requires_backend:
            executor.launch_backend()
            if executor.backend_url != scenario.backend_url:
                report.add_note(
                    f"Automation selected backend `{executor.backend_url}` because `{scenario.backend_url}` did not satisfy the campaign contract."
                )
            prepared_slot = _ensure_resume_fixture(scenario, report, executor.backend_url)
        _seed_godot_profile(scenario, prepared_slot)
        executor.launch_client()
        for step in scenario.steps:
            report.steps_run.append(step.id)
            _run_step(executor, report, step, step_memory)
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


def _ensure_resume_fixture(scenario, report: RunReport, backend_url: str) -> str:
    if scenario.create_new:
        return ""
    seed = sum(ord(character) for character in f"{scenario.player_name}:{scenario.adapter_id}:{scenario.name}") % 100000
    payload = {
        "player_name": scenario.player_name,
        "player_class": "warrior",
        "adapter_id": scenario.adapter_id,
        "profile_id": "standard",
        "seed": seed,
    }
    created = _json_request(f"{backend_url.rstrip('/')}/game/campaigns", payload)
    campaign_id = str(created.get("campaign_id", "")).strip()
    if not campaign_id:
        raise RuntimeError("Fixture campaign creation did not return campaign_id.")
    slot_name = f"auto_{scenario.name}_{scenario.player_name}".replace(" ", "_").lower()
    _json_request(
        f"{backend_url.rstrip('/')}/game/campaigns/{campaign_id}/save",
        {"player_id": scenario.player_name, "slot_name": slot_name},
    )
    report.add_note(f"Prepared canonical campaign save fixture `{slot_name}` for player `{scenario.player_name}`.")
    return slot_name


def _seed_godot_profile(scenario, prepared_slot: str = "") -> None:
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        return
    profile_path = Path(appdata) / "Godot" / "app_userdata" / "Ember RPG" / "client_profile.cfg"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_text = "\n".join(
        [
            "[profile]",
            f'last_player_id="{scenario.player_name}"',
            f'last_resume_player_id="{scenario.player_name}"',
            f'last_adapter_id="{scenario.adapter_id}"',
            f'last_campaign_save_id="{prepared_slot}"' if prepared_slot else "",
            "",
        ]
    )
    profile_path.write_text(profile_text, encoding="utf-8")


def _json_request(url: str, payload: dict[str, object]) -> dict[str, object]:
    raw = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _check_environment(executor: AutomationExecutor, report: RunReport) -> bool:
    health = executor.environment_health()
    if bool(health.get("ok", True)):
        return True
    summary = str(health.get("summary", "")).strip() or "Automation environment preflight failed."
    report.success = False
    report.add_note(summary)
    for note in health.get("notes", []):
        report.add_note(str(note))
    report.add_issue(
        executor.record_issue(
            "environment",
            "critical",
            "automation environment is ready before scenario launch",
            summary,
        )
    )
    return False


def _run_step(
    executor: AutomationExecutor,
    report: RunReport,
    step: ActionStep,
    step_memory: dict[str, str],
) -> None:
    for _ in range(step.repeat):
        try:
            artifact = _dispatch_action(executor, step, step_memory)
        except CapabilityUnavailableError as exc:
            gap = executor.mark_gap(f"{step.id}:{step.action}")
            report.add_gap(gap)
            report.add_note(str(exc))
            report.add_issue(executor.record_issue(step.id, "major", step.expected or step.action, str(exc)))
            return
        if artifact is not None:
            _record_artifact(report, executor, step, artifact)
        if step.wait_ms:
            time.sleep(step.wait_ms / 1000.0)

    if step.capture_os:
        _capture(report, executor, step, "os")
    if step.capture_viewport:
        _capture(report, executor, step, "viewport")


def _dispatch_action(
    executor: AutomationExecutor,
    step: ActionStep,
    step_memory: dict[str, str],
) -> ArtifactRecord | None:
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
    elif action == "focus_node":
        _require_node_path(step)
        executor.focus_node(step.node_path or "")
    elif action == "activate_node":
        _require_node_path(step)
        executor.activate_node(step.node_path or "")
    elif action == "set_text_node":
        _require_node_path(step)
        if step.text is None:
            raise ValueError(f"Step {step.id} requires text")
        executor.set_text_node(step.node_path or "", step.text)
    elif action == "select_option_node":
        _require_node_path(step)
        if not step.option_text:
            raise ValueError(f"Step {step.id} requires option_text")
        executor.select_option_node(step.node_path or "", step.option_text)
    elif action == "click_node":
        _require_node_path(step)
        executor.click_node(
            step.node_path or "",
            normalized_x=step.normalized_x if step.normalized_x is not None else 0.5,
            normalized_y=step.normalized_y if step.normalized_y is not None else 0.5,
            button=step.button,
        )
    elif action == "wait_for_scene":
        _require_scene_name(step)
        _wait_for_scene(executor, step.scene_name or "", _step_timeout_seconds(step))
    elif action == "wait_for_node":
        _require_node_path(step)
        _wait_for_node(executor, step.node_path or "", _step_timeout_seconds(step))
    elif action == "wait_for_node_visible":
        _require_node_path(step)
        _wait_for_node_visible(executor, step.node_path or "", _step_timeout_seconds(step))
    elif action == "wait_for_node_hidden":
        _require_node_path(step)
        _wait_for_node_hidden(executor, step.node_path or "", _step_timeout_seconds(step))
    elif action == "wait_for_node_text":
        _require_node_path(step)
        if step.text is None:
            raise ValueError(f"Step {step.id} requires text")
        _wait_for_node_text(executor, step.node_path or "", step.text, _step_timeout_seconds(step))
    elif action == "remember_node_text":
        _require_node_path(step)
        state = executor.query_node_state(step.node_path or "")
        if not bool(state.get("node_exists", False)):
            raise RuntimeError(f"Cannot remember text for missing node `{step.node_path}`.")
        step_memory[_memory_key(step)] = str(state.get("node_text", ""))
    elif action == "wait_for_node_text_changed":
        _require_node_path(step)
        baseline_key = _reference_key(step)
        baseline_text = step_memory.get(baseline_key)
        if baseline_text is None:
            raise RuntimeError(
                f"Step {step.id} requires remembered text for reference `{baseline_key}`."
            )
        _wait_for_node_text_changed(
            executor,
            step.node_path or "",
            baseline_text,
            _step_timeout_seconds(step),
        )
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
    elif action == "restart_client":
        executor.close_client()
        executor.launch_client()
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
        _record_artifact(report, executor, step, artifact)
    except CapabilityUnavailableError as exc:
        report.add_gap(executor.mark_gap(f"{step.id}:{artifact_kind}_capture"))
        report.add_note(str(exc))


def _record_artifact(report: RunReport, executor: AutomationExecutor, step: ActionStep, artifact: ArtifactRecord) -> None:
    report.add_artifact(artifact)
    _validate_artifact(report, executor, step, artifact)


def _validate_artifact(report: RunReport, executor: AutomationExecutor, step: ActionStep, artifact: ArtifactRecord) -> None:
    expected_note = str(step.metadata.get("expect_note_contains", "")).strip()
    if expected_note and artifact.artifact_type == "viewport_capture" and expected_note not in artifact.note:
        report.add_issue(
            executor.record_issue(
                step.id,
                "major",
                step.expected or f"artifact note contains `{expected_note}`",
                "Artifact note did not contain the required marker.",
                (artifact.path,),
            )
        )

    diff_reference = str(step.metadata.get("expect_artifact_differs_from", "")).strip()
    if diff_reference:
        reference = _find_artifact_reference(report, artifact, diff_reference)
        if reference is None:
            report.add_issue(
                executor.record_issue(
                    step.id,
                    "major",
                    step.expected or f"artifact differs from `{diff_reference}`",
                    f"Reference artifact `{diff_reference}` was not found.",
                    (artifact.path,),
                )
            )
            return
        if _artifact_bytes(artifact.path) == _artifact_bytes(reference.path):
            report.add_issue(
                executor.record_issue(
                    step.id,
                    "major",
                    step.expected or f"artifact differs from `{diff_reference}`",
                    "Captured artifact is identical to the referenced artifact.",
                    (artifact.path, reference.path),
                )
            )


def _find_artifact_reference(
    report: RunReport,
    artifact: ArtifactRecord,
    reference: str,
) -> ArtifactRecord | None:
    step_id, _, artifact_type = reference.partition(":")
    normalized_step_id = step_id.strip()
    normalized_type = artifact_type.strip() or artifact.artifact_type
    for candidate in reversed(report.artifacts):
        if candidate.step_id == normalized_step_id and candidate.artifact_type == normalized_type:
            return candidate
    return None


def _artifact_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def _require_xy(step: ActionStep) -> None:
    if step.x is None or step.y is None:
        raise ValueError(f"Step {step.id} requires x and y coordinates")


def _require_key(step: ActionStep) -> None:
    if not step.key:
        raise ValueError(f"Step {step.id} requires a key")


def _require_node_path(step: ActionStep) -> None:
    if not step.node_path:
        raise ValueError(f"Step {step.id} requires node_path")


def _require_scene_name(step: ActionStep) -> None:
    if not step.scene_name:
        raise ValueError(f"Step {step.id} requires scene_name")


def _step_timeout_seconds(step: ActionStep) -> float:
    timeout_ms = max(step.duration_ms, step.wait_ms, 1000)
    return timeout_ms / 1000.0


def _wait_for_scene(executor: AutomationExecutor, scene_name: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_scene = ""
    while time.monotonic() <= deadline:
        last_scene = executor.current_scene_name()
        if last_scene == scene_name:
            return
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for scene `{scene_name}`. Last scene was `{last_scene or 'unknown'}`.")


def _wait_for_node(executor: AutomationExecutor, node_path: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if executor.node_exists(node_path):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for node `{node_path}`.")


def _wait_for_node_visible(executor: AutomationExecutor, node_path: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        state = executor.query_node_state(node_path)
        if bool(state.get("node_exists", False)) and bool(state.get("node_visible", False)):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for visible node `{node_path}`.")


def _wait_for_node_hidden(executor: AutomationExecutor, node_path: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        state = executor.query_node_state(node_path)
        if not bool(state.get("node_exists", False)) or not bool(state.get("node_visible", False)):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for hidden node `{node_path}`.")


def _wait_for_node_text(
    executor: AutomationExecutor,
    node_path: str,
    expected_text: str,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_text = ""
    while time.monotonic() <= deadline:
        state = executor.query_node_state(node_path)
        last_text = str(state.get("node_text", ""))
        if bool(state.get("node_exists", False)) and expected_text in last_text:
            return
        time.sleep(0.1)
    raise RuntimeError(
        f"Timed out waiting for text `{expected_text}` in node `{node_path}`. Last text was `{last_text}`."
    )


def _wait_for_node_text_changed(
    executor: AutomationExecutor,
    node_path: str,
    baseline_text: str,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_text = baseline_text
    while time.monotonic() <= deadline:
        state = executor.query_node_state(node_path)
        last_text = str(state.get("node_text", ""))
        if bool(state.get("node_exists", False)) and last_text.strip() and last_text != baseline_text:
            return
        time.sleep(0.1)
    raise RuntimeError(
        f"Timed out waiting for text in node `{node_path}` to change from `{baseline_text}`. "
        f"Last text was `{last_text}`."
    )


def _memory_key(step: ActionStep) -> str:
    custom_key = str(step.metadata.get("store_as", "")).strip()
    return custom_key or step.id


def _reference_key(step: ActionStep) -> str:
    reference_key = str(step.metadata.get("reference_step_id", "")).strip()
    return reference_key or step.id


if __name__ == "__main__":
    raise SystemExit(main())

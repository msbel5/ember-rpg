# PRD: Visual Automation Backup Harness
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Define a test-only visual automation subsystem that can drive Ember RPG like a real player, capture OS-level and in-engine viewport proof, and produce structured QA reports even when external `computer-use` transport is unavailable. The subsystem exists to support long-form visual QA, regression testing, and reproducible bug reports without adding production gameplay instrumentation.

## 2. Scope
- In scope: reusable automation scenarios, an executor abstraction, a Windows-first desktop executor, a headless Godot executor, screenshot and log artifact handling, and QA report generation.
- In scope: replaying keyboard, mouse, and text input against the real title flow and gameplay scenes.
- In scope: explicit capability-gap reporting when an executor cannot provide OS or viewport proof.
- Out of scope: gameplay logic changes, UI redesign, network contract changes, new production instrumentation, and replacement of final desktop visual signoff with headless proof.

## 3. Functional Requirements (FR)
FR-01: The subsystem SHALL live under `godot-client/tests/automation/` and SHALL not require production code changes outside the existing viewport capture path.
FR-02: The subsystem SHALL load repeatable visual scenarios from TOML fixtures.
FR-03: The subsystem SHALL define a common executor interface for launch, focus, input, screenshot capture, and issue logging.
FR-04: The Windows desktop executor SHALL drive a real Godot window and capture OS-level screenshots.
FR-05: The headless Godot executor SHALL replay synthetic input inside Godot and capture viewport proof through the existing screenshot subsystem, producing a synthetic diagnostic artifact when the headless renderer cannot expose a real render target.
FR-06: The runner SHALL write deterministic artifact paths for screenshots, logs, and JSON/Markdown reports.
FR-07: The runner SHALL record any missing executor capability as an explicit report entry instead of skipping the step silently.
FR-08: The subsystem SHALL support a logical cursor state for scenario playback and artifact debugging.
FR-09: The subsystem SHALL support reusable scenarios for title flow, save browser, new game, gameplay click, and save panel smoke checks.
FR-10: The subsystem SHALL keep headless proof as CI and backup evidence only; final release visual signoff SHALL still require a real desktop run.

## 4. Data Structures
```python
from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class ActionStep:
    step_id: str
    kind: Literal[
        "key_down",
        "key_up",
        "key_press",
        "key_hold",
        "mouse_move",
        "mouse_down",
        "mouse_up",
        "mouse_click",
        "text",
        "wait",
        "capture_os",
        "capture_viewport",
    ]
    target: dict[str, Any]
    expect: str | None = None


@dataclass
class AutomationScenario:
    scenario_id: str
    name: str
    adapter_id: str | None
    steps: list[ActionStep]


@dataclass
class ArtifactRecord:
    artifact_id: str
    kind: Literal["os_screenshot", "viewport_capture", "log", "report_json", "report_md"]
    path: str


@dataclass
class IssueRecord:
    step_id: str
    severity: Literal["P0", "P1", "P2", "info"]
    expected: str
    actual: str
    artifact_paths: list[str]


@dataclass
class RunReport:
    run_id: str
    scenario_id: str
    executor_id: str
    status: Literal["pass", "partial", "fail"]
    artifacts: list[ArtifactRecord]
    issues: list[IssueRecord]
```

## 5. Public API
`godot-client/tests/automation/runner.py` SHALL expose:
- `load_scenario(path: str) -> AutomationScenario`
- `run_scenario(scenario: AutomationScenario, executor: VisualExecutor) -> RunReport`
- `write_report(report: RunReport, output_dir: str) -> dict[str, str]`

`godot-client/tests/automation/executors/base.py` SHALL define:
- `launch_backend() -> None`
- `stop_backend() -> None`
- `launch_client() -> None`
- `close_client() -> None`
- `activate_window() -> None`
- `move_cursor(x: int, y: int) -> None`
- `mouse_down(button: str = "left") -> None`
- `mouse_up(button: str = "left") -> None`
- `mouse_click(x: int, y: int, button: str = "left") -> None`
- `key_down(key: str) -> None`
- `key_up(key: str) -> None`
- `key_press(key: str) -> None`
- `key_hold(key: str, duration_ms: int) -> None`
- `type_text(text: str) -> None`
- `capture_os(tag: str) -> str | None`
- `capture_viewport(tag: str) -> str | None`
- `record_issue(step_id: str, severity: str, expected: str, actual: str, artifact_paths: list[str]) -> None`

Preconditions: the executor must know whether it is desktop or headless. Postconditions: capture methods return artifact paths when supported. Exceptions: the executor SHALL raise a structured error on missing launch target, missing scene, invalid step type, or failed capture.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: All harness code lives under `godot-client/tests/automation/` and no production gameplay file is modified to add automation hooks.
AC-02 [FR-02]: A TOML scenario can be loaded into a typed scenario object and replayed deterministically.
AC-03 [FR-03]: The runner can execute scenarios through a shared executor interface without knowing the executor implementation.
AC-04 [FR-04]: The Windows desktop executor can drive a real Godot window and produce OS screenshots.
AC-05 [FR-05]: The headless executor can replay input inside Godot and produce a deterministic viewport artifact, with synthetic fallback explicitly labeled when the renderer cannot expose a real render target.
AC-06 [FR-06]: Each run emits stable artifact paths and both JSON and Markdown reports.
AC-07 [FR-07]: Unsupported executor capabilities appear in the report as explicit gaps.
AC-08 [FR-08]: Scenario playback preserves logical cursor state for debugging and report narration.
AC-09 [FR-09]: The default fixture set covers title flow, save browser, new game, gameplay click, and save panel smoke.
AC-10 [FR-10]: Headless proof is accepted as backup evidence and CI coverage only, not as final desktop visual signoff.

## 7. Performance Requirements
- Scenario parsing SHALL complete in under 50 ms for a single fixture on typical developer hardware.
- Artifact path generation SHALL be deterministic and complete in under 10 ms per step.
- A short smoke scenario of fewer than 20 steps SHOULD complete in under 10 seconds excluding backend startup time.

## 8. Error Handling
- Invalid scenario syntax SHALL fail fast with a clear file path and line-oriented parse error.
- Missing screenshots SHALL be recorded as explicit capture failures in the report.
- Synthetic headless fallback captures SHALL be labeled explicitly so they are never mistaken for desktop signoff evidence.
- Unsupported executor methods SHALL raise a structured error and mark the run partial rather than silently passing.
- If a step fails, the runner SHALL continue only when the scenario definition explicitly allows recovery.

## 9. Integration Points
- `godot-client/tests/automation/scenario_loader.py`
- `godot-client/tests/automation/runner.py`
- `godot-client/tests/automation/artifacts.py`
- `godot-client/tests/automation/report_writer.py`
- `godot-client/tests/automation/executors/base.py`
- `godot-client/tests/automation/executors/win32_desktop.py`
- `godot-client/tests/automation/executors/headless_godot.py`
- `godot-client/tests/automation/godot/automation_bridge.gd`
- `godot-client/tests/automation/godot/automation_bridge_runner.gd`
- `godot-client/scripts/ui/screenshot_capture.gd`
- `docs/qa/campaign_cutover_visual_log.md`
- `docs/qa/demo_signoff_matrix.md`

## 10. Test Coverage Target
- Parser and model coverage SHALL be at least 90% for the automation package.
- Each supported action kind SHALL have at least one unit test and one scenario test.
- Report generation SHALL be covered for pass, partial, and fail outputs.
- Executor gap handling SHALL be covered for both desktop and headless capabilities.
- The headless bridge and desktop executor SHALL each have smoke coverage for title flow and gameplay interaction.

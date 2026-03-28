# PRD: Visual Automation Headless Executor
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Define the headless Godot executor used by the visual automation backup harness. This executor is responsible for replaying synthetic input inside Godot, collecting viewport proof with the existing capture path, and providing CI-friendly evidence when an external desktop window is unavailable. It is a backup and regression path, not a replacement for final desktop visual signoff.

## 2. Scope
- In scope: headless launch, scenario replay, synthetic input dispatch, viewport capture, and bridge-side state tracking.
- In scope: exercising the real title, gameplay, save/load, and click flows without changing production gameplay code.
- Out of scope: OS screenshots, desktop-only focus recovery, and final release visual acceptance.

## 3. Functional Requirements (FR)
FR-01: The executor SHALL launch Godot in headless mode with a tests-only bridge entrypoint.
FR-02: The executor SHALL replay keyboard, mouse, and text actions as synthetic `InputEvent` data inside Godot.
FR-03: The executor SHALL support key down, key up, key press, key hold, mouse move, mouse down, mouse up, mouse click, and text steps.
FR-04: The executor SHALL capture viewport proof through the existing screenshot capture subsystem already available to the project, and SHALL emit a synthetic diagnostic image when the headless renderer cannot expose a real render target.
FR-05: The executor SHALL write proof artifacts to deterministic paths.
FR-06: The executor SHALL surface unsupported actions, missing scenes, and capture failures as explicit errors.
FR-07: The executor SHALL support the title wizard, a gameplay smoke path, and a save panel smoke path.
FR-08: The executor SHALL be usable in CI and local fallback runs.
FR-09: The executor SHALL not require any production code instrumentation beyond the existing capture path.
FR-10: The executor SHALL be treated as backup evidence and regression coverage, not as final desktop visual signoff.

## 4. Data Structures
```python
from dataclasses import dataclass
from typing import Literal


@dataclass
class HeadlessStep:
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
        "capture_viewport",
    ]
    payload: dict[str, object]


@dataclass
class BridgeState:
    scenario_id: str
    scene_name: str
    cursor_x: int
    cursor_y: int
    focus_target: str | None
    last_capture_path: str | None


@dataclass
class HeadlessArtifact:
    kind: Literal["viewport_capture", "log"]
    path: str
```

## 5. Public API
`godot-client/tests/automation/godot/automation_bridge_runner.gd` SHALL expose a CLI entrypoint that:
- loads a scenario
- loads the target Godot scene
- replays the scenario steps
- triggers viewport capture when requested
- emits a machine-readable summary for the Python runner

The headless executor SHALL provide the same shared harness interface as the desktop executor, except for OS screenshot capture, which MAY return `None` or a structured unsupported-capability result.

Preconditions: the Godot executable is available and the bridge scene path exists. Postconditions: a valid viewport proof path is produced when the scenario requests capture. If the headless renderer cannot expose a real texture, the returned artifact SHALL be marked synthetic instead of being presented as desktop-equivalent proof. Exceptions: missing scene, invalid action kind, or screenshot capture failure SHALL stop the run with a structured error.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: The executor can launch Godot headless through the bridge entrypoint.
AC-02 [FR-02]: The executor can replay synthetic keyboard, mouse, and text actions inside the game scenes.
AC-03 [FR-03]: The executor supports all declared input step kinds used by the harness scenarios.
AC-04 [FR-04]: A viewport capture step produces a deterministic proof file through the screenshot subsystem, with synthetic fallback explicitly labeled if the renderer cannot expose a real render target.
AC-05 [FR-05]: Proof artifact paths are deterministic and recorded in the run report.
AC-06 [FR-06]: Unsupported actions or missing scenes fail explicitly rather than being ignored.
AC-07 [FR-07]: The headless executor can replay title and save-panel smoke scenarios.
AC-08 [FR-08]: The executor works in CI-style runs without a live desktop window.
AC-09 [FR-09]: No production gameplay code is modified to add automation hooks.
AC-10 [FR-10]: The report marks headless evidence as backup and CI coverage, not final desktop signoff.

## 7. Performance Requirements
- A short headless scenario SHOULD launch and reach the first actionable step in under 10 seconds on a normal developer machine, excluding any backend startup.
- A viewport capture step SHOULD complete in under 1 second once the scene is ready.

## 8. Error Handling
- If the bridge scene cannot be loaded, the executor SHALL fail fast with the missing path.
- If a synthetic event cannot be translated to Godot input, the executor SHALL stop the scenario and report the invalid step.
- If viewport capture fails, the executor SHALL mark the artifact as failed rather than producing a blank file silently.
- If only a synthetic fallback is possible, the executor SHALL label the artifact accordingly instead of claiming desktop-equivalent proof.

## 9. Integration Points
- `godot-client/tests/automation/godot/automation_bridge.gd`
- `godot-client/tests/automation/godot/automation_bridge_runner.gd`
- `godot-client/tests/automation/godot/automation_state.gd`
- `godot-client/tests/run_headless_tests.gd`
- `godot-client/scripts/ui/screenshot_capture.gd`
- `godot-client/scenes/title_screen.tscn`
- `godot-client/scenes/game_session.tscn`
- `godot-client/tests/automation/runner.py`

## 10. Test Coverage Target
- The bridge SHALL have tests for keyboard, mouse, and text forwarding.
- The bridge SHALL have tests for viewport capture path creation.
- Scenario replay SHALL be covered by title-wizard and gameplay smoke tests.
- Failure paths SHALL be covered for missing scene and capture failure.

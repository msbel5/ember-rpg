# PRD: Automation Authority V1
**Project:** Ember RPG  
**Phase:** 0  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-31  
**Status:** Approved  

---

## 1. Purpose
Automation Authority V1 defines the authoritative QA stack for Ember RPG on desktop platforms. Its purpose is to remove ambiguity about which automation surface is trusted, prevent false confidence from broken OS-level tools, and ensure scene-level automation, screenshot capture, and recording are deterministic and reproducible.

## 2. Scope
- In scope: headless Godot automation bridge, Win32 desktop fallback, dependency health checks, screenshot and recording authority, scenario expectations, viewport capture behavior.
- Out of scope: fixing external Claude computer-use support on Windows, cloud device labs, generalized browser automation, full gameplay AI playtesting.

## 3. Functional Requirements (FR)
FR-01: The authoritative automation path for gameplay and title-screen QA on Windows must be the Godot automation bridge, not external computer-use tooling.

FR-02: The fallback desktop executor must fail with explicit remediation when required Windows dependencies are unavailable.

FR-03: Headless automation must support:
- keyboard input
- mouse input in logical client coordinates
- text input
- viewport capture
- recording controls

FR-04: Desktop automation must support:
- window activation
- OS/window screenshot capture
- forwarding keyboard and mouse input

FR-05: Automation scenarios used for creation and title-screen validation must not depend on absolute monitor-space coordinates.

FR-06: Viewport capture must remain available even when OS screenshot support is missing.

FR-07: Automation reports must distinguish capability gaps from assertion failures.

## 4. Data Structures
```python
@dataclass
class AutomationHealthReport:
    ok: bool
    summary: str
    notes: list[str]


@dataclass
class AutomationCapabilities:
    keyboard: bool
    mouse: bool
    viewport_capture: bool
    os_capture: bool
    recording: bool


@dataclass
class ArtifactRecord:
    step_id: str
    artifact_type: Literal["viewport_capture", "os_screenshot"]
    path: str
    note: str = ""
```

## 5. Public API
```python
class AutomationExecutor:
    def environment_health(self) -> dict[str, Any]: ...
    def capture_viewport(self, tag: str) -> ArtifactRecord: ...
```
- Preconditions: executor is initialized.
- Postconditions: reports health or emits an artifact.
- Exceptions raised: `CapabilityUnavailableError` only for genuine capability gaps.

```python
class HeadlessGodotExecutor(AutomationExecutor):
    def mouse_click(self, x: int, y: int, button: str = "left") -> None: ...
```
- Coordinates are logical client/viewport coordinates, not OS desktop coordinates.

```python
class Win32DesktopExecutor(AutomationExecutor):
    def environment_health(self) -> dict[str, Any]: ...
```
- Must validate `pywin32`, `Pillow`, and `requests` before scenario execution.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Given the project runs on Windows, when the automation stack is documented and tested, then `headless_godot` is identified as the primary authority for deterministic QA.

AC-02 [FR-02]: Given a missing Win32 dependency, when the desktop executor health check runs, then it returns `ok = false` and reports remediation notes before scenario launch.

AC-03 [FR-03]: Given a running headless bridge, when a scenario sends keyboard, mouse, text, record, and viewport capture commands, then the bridge returns successful responses for supported operations.

AC-04 [FR-04]: Given a healthy Win32 executor, when a desktop smoke scenario runs, then it can activate the game window and capture an OS screenshot.

AC-05 [FR-05]: Given a title-screen automation scenario, when it is executed, then the scenario uses logical client coordinates or keyboard focus paths rather than desktop-space assumptions.

AC-06 [FR-06]: Given OS screenshot capture is unavailable, when viewport capture is requested through the headless bridge, then a viewport artifact is still produced.

AC-07 [FR-07]: Given an unsupported capability is requested, when the runner records the result, then the report marks a capability gap rather than a false test failure.

## 7. Performance Requirements
- Automation health checks must complete in under 250 ms excluding import cold start.
- Headless bridge command round-trips must complete within 15 seconds or fail with a structured error.

## 8. Error Handling
- Missing Win32 dependencies must never degrade silently.
- Missing viewport artifact files must raise structured runner errors.
- Unsupported OS capture in headless mode must raise `CapabilityUnavailableError`.

## 9. Integration Points
- `godot-client/tests/automation/runner.py`
- `godot-client/tests/automation/executors/base.py`
- `godot-client/tests/automation/executors/headless_godot.py`
- `godot-client/tests/automation/executors/win32_desktop.py`
- `godot-client/tests/automation/godot/automation_bridge.gd`
- `godot-client/scripts/ui/screenshot_capture.gd`

## 10. Test Coverage Target
- 100% coverage of environment-health branches for automation executors.
- Scenario/runner tests must cover capability gaps, viewport capture, and missing dependency handling.

## Changelog
- 2026-04-01: Promoted to approved after the headless and Win32 automation pytest suite passed and the `title_creation_bridge` headless scenario produced deterministic viewport artifacts with explicit synthetic labeling.

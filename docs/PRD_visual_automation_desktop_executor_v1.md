# PRD: Visual Automation Desktop Executor
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Define the Windows-first external desktop executor used by the visual automation backup harness. This executor is responsible for interacting with a real Godot window, forwarding input, and capturing OS-level screenshots for QA evidence. It exists so the project can keep doing real graphical validation even when a dedicated `computer-use` transport is unavailable.

## 2. Scope
- In scope: window discovery, activation, focus recovery, mouse and keyboard dispatch, text entry, logical cursor tracking, OS screenshot capture, and launcher control for the Godot client and optional backend process.
- In scope: Windows-first implementation seeded from the existing manual visual driver approach.
- Out of scope: production gameplay logic, viewport instrumentation inside the shipped client, and cross-platform native desktop implementations in v1.

## 3. Functional Requirements (FR)
FR-01: The executor SHALL discover a target Godot window by title, process id, or configured executable path.
FR-02: The executor SHALL activate and focus the target window before sending input.
FR-03: The executor SHALL support key down, key up, key press, key hold, mouse move, mouse down, mouse up, mouse click, and text input.
FR-04: The executor SHALL maintain a logical cursor position in scenario state.
FR-05: The executor SHALL capture OS-level screenshots of the active Godot window on demand.
FR-06: The executor SHALL expose a backend launch/stop helper only as an optional test convenience, not as a gameplay dependency.
FR-07: The executor SHALL report focus loss, window not found, or screenshot failure as explicit errors.
FR-08: The executor SHALL not require changes to production Godot scenes beyond the existing viewport capture path.
FR-09: The executor SHALL keep the desktop contract behind the shared harness interface.
FR-10: The executor SHALL be the primary release-quality visual path for Windows desktop QA.

## 4. Data Structures
```python
from dataclasses import dataclass
from typing import Literal


@dataclass
class DesktopWindowHandle:
    title: str
    process_id: int
    hwnd: int | None


@dataclass
class MouseAction:
    button: Literal["left", "right", "middle"]
    x: int
    y: int
    click_count: int = 1


@dataclass
class KeyAction:
    key: str
    duration_ms: int | None = None


@dataclass
class DesktopArtifact:
    kind: Literal["os_screenshot", "log"]
    path: str
```

## 5. Public API
The executor implementation SHALL provide the shared harness methods defined by the base executor interface:
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

Preconditions: a supported Windows desktop session must be available. Postconditions: input is delivered to the focused Godot window and screenshots reflect the current UI. Exceptions: missing window, permission denial, and screenshot failure SHALL surface as explicit errors.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: The executor can locate the target Godot process or window without manual one-off edits.
AC-02 [FR-02]: The executor can recover focus and continue sending input after the window loses activation.
AC-03 [FR-03]: The executor can send keyboard and mouse actions that change the live Godot UI.
AC-04 [FR-04]: The logical cursor position is preserved across move and click steps.
AC-05 [FR-05]: The executor can capture an OS screenshot of the live Godot window.
AC-06 [FR-06]: Backend launch/stop is available as an optional harness convenience and does not affect gameplay code.
AC-07 [FR-07]: Missing focus or screenshot failure produces an explicit test failure.
AC-08 [FR-08]: The executor works without adding production-only instrumentation.
AC-09 [FR-09]: The desktop executor is callable only through the shared harness interface.
AC-10 [FR-10]: Windows desktop visual QA can use this executor as the release-quality desktop path.

## 7. Performance Requirements
- Window activation SHALL complete in under 2 seconds on a healthy local desktop session.
- A single OS screenshot capture SHOULD complete in under 1 second for a normal-sized Godot window.
- A short click-and-type smoke scenario SHOULD avoid input lag visible to the operator.

## 8. Error Handling
- If the target window is not present, the executor SHALL fail fast with the requested window metadata.
- If input cannot be delivered to the target window, the executor SHALL raise a structured error and stop the current scenario.
- If OS screenshot capture fails, the executor SHALL return a failed artifact record rather than fabricating proof.

## 9. Integration Points
- `godot-client/tests/manual/campaign_visual_driver.py`
- `godot-client/tests/automation/runner.py`
- `godot-client/tests/automation/executors/base.py`
- `godot-client/tests/automation/executors/win32_desktop.py`
- `godot-client/tests/automation/scenarios/*.toml`
- `godot-client/tests/automation/report_writer.py`
- `docs/qa/campaign_cutover_visual_log.md`

## 10. Test Coverage Target
- Window discovery and focus recovery SHALL have explicit tests.
- Keyboard and mouse dispatch SHALL have unit coverage and a real-window smoke test.
- OS screenshot capture SHALL have at least one success-path test and one failure-path test.
- Logical cursor tracking SHALL be verified by scenario playback tests.


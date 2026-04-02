# PRD: Automation Authority V1
**Project:** Ember RPG
**Phase:** 0
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Approved

---

## 1. Purpose
Automation Authority V1 defines the authoritative QA stack for Ember RPG on desktop platforms. Its purpose is to keep gameplay proof deterministic, Godot-first, and semantically driven. Headless Godot is the truth path for repeatable QA; Win32 desktop remains the fallback proof lane, but it may use the runtime automation bridge to assert scene and node state instead of relying on blind coordinate clicks alone.

## 2. Scope
- In scope: headless Godot automation bridge, runtime automation bridge, semantic scene actions, logical-coordinate input, Win32 fallback, dependency health checks, viewport and OS screenshot capture, capability-gap reporting, and bounded scenario evidence.
- Out of scope: `computer_use`, browser automation, cloud device labs, full autonomous play, and long chaos proof as the default release gate.

## 3. Functional Requirements
FR-01: The authoritative automation path for title, creation, gameplay shell, and save/load QA on Windows SHALL be the Godot automation bridge.

FR-02: The fallback desktop executor SHALL fail with explicit remediation when required dependencies are unavailable.

FR-03: Headless automation SHALL support keyboard input, logical mouse input, text input, viewport capture, recording controls, and semantic scene actions.

FR-04: Semantic scene actions SHALL support at minimum:
- focus a control by scene path
- activate a control by scene path
- set text on a control by scene path
- select an option on an option control by scene path
- click a control-relative position by scene path
- wait for a node to become visible or hidden
- wait for node text to match or change

FR-05: Automation scenarios used for title, creation, continue, and save/load validation SHALL avoid absolute monitor-space coordinates.

FR-06: Viewport capture SHALL remain available even when OS screenshot support is unavailable.

FR-07: Automation reports SHALL distinguish capability gaps from assertion failures.

FR-08: Win32 desktop execution SHALL remain a fallback proof lane and, when the runtime automation bridge is available, SHALL support scene/node visibility and text assertions in addition to window activation, keyboard/mouse forwarding, and desktop proof screenshots.

FR-09: The default release gate SHALL use bounded headless and targeted desktop proofs rather than `100`/`500` turn chaos runs.

FR-10: The required semantic desktop proof pack SHALL include fresh creation/resume proof plus dedicated dialog, travel, combat, sidebar, and save/load scenarios.

## 4. Data Structures
```python
@dataclass
class AutomationCapabilities:
    keyboard: bool
    mouse: bool
    viewport_capture: bool
    os_capture: bool
    recording: bool
    semantic_controls: bool


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

```python
class HeadlessGodotExecutor(AutomationExecutor):
    def focus_node(self, node_path: str) -> None: ...
    def activate_node(self, node_path: str) -> None: ...
    def set_text_node(self, node_path: str, text: str) -> None: ...
    def select_option_node(self, node_path: str, option_text: str) -> None: ...
    def click_node(self, node_path: str, normalized_x: float = 0.5, normalized_y: float = 0.5) -> None: ...
```

## 6. Acceptance Criteria
AC-01 [FR-01]: `headless_godot` is documented and tested as the primary deterministic QA authority.

AC-02 [FR-02]: Missing Win32 dependencies fail health checks before scenario execution with explicit remediation notes.

AC-03 [FR-03]: The headless bridge accepts keyboard, logical mouse, text, record, viewport capture, and semantic node commands.

AC-04 [FR-04]: Semantic actions can focus, activate, set text, select options, click control-relative positions, and assert visibility/text state by scene path.

AC-05 [FR-05]: Title, creation, continue, and save/load scenarios no longer rely on desktop-space `x/y` coordinates in the default headless path.

AC-06 [FR-06]: Viewport capture still succeeds when OS screenshot capture is unavailable.

AC-07 [FR-07]: Capability gaps are reported separately from behavior/assertion failures.

AC-08 [FR-08]: The desktop executor remains non-authoritative for gameplay rules, but it can verify real scene/node state through the runtime bridge while capturing desktop proof.

AC-09 [FR-09]: The default QA gate is bounded deterministic scenario proof, while long chaos remains a soak lane.

AC-10 [FR-10]: Versioned semantic desktop proofs exist for creation/resume, save/load, sidebar hydration, dialog, travel, and combat.

## 7. Performance Requirements
- Automation health checks should complete in under 250 ms excluding import cold start.
- Headless bridge command round-trips should complete within 15 seconds or fail with structured errors.

## 8. Error Handling
- Missing Win32 dependencies must never degrade silently.
- Missing viewport artifact files must raise structured runner errors.
- Unsupported headless actions or missing node targets must produce explicit command failures.

## 9. Integration Points
- `godot-client/tests/automation/runner.py`
- `godot-client/tests/automation/models.py`
- `godot-client/tests/automation/scenario_loader.py`
- `godot-client/tests/automation/executors/base.py`
- `godot-client/tests/automation/executors/headless_godot.py`
- `godot-client/tests/automation/executors/win32_desktop.py`
- `godot-client/tests/automation/godot/automation_bridge.gd`
- `godot-client/autoloads/runtime_automation_bridge.gd`
- `godot-client/scripts/ui/screenshot_capture.gd`

## 10. Test Coverage Target
- Environment-health branches for all executors.
- Scenario/runner coverage for capability gaps, semantic headless actions, and viewport capture.
- Required scenario fixtures must prove semantic title/creation/continue/save-load/dialog/travel/combat flows.

## Changelog
- 2026-04-01: Updated to semantic headless automation, bounded proof gating, and explicit deprecation of long-chaos as a default release requirement.
- 2026-04-02: Added semantic text-change assertions and made dialog, travel, combat, sidebar, and save/load part of the required desktop proof pack.

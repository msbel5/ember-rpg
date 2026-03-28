# PRD: Visual Automation Reporting
**Project:** Ember RPG  
**Phase:** 4  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Define the evidence and reporting layer for the visual automation backup harness. The report layer converts scenario execution into a reviewable bug ledger with screenshots, viewport captures, pass/fail status, and explicit capability gaps. It exists so future chats and human reviewers can trust what was actually observed.

## 2. Scope
- In scope: artifact indexing, issue logging, JSON output, Markdown summaries, and deterministic file naming.
- In scope: pass/partial/fail status computation and explicit support-gap reporting.
- Out of scope: gameplay logic, executor implementation, and visual styling of the game itself.

## 3. Functional Requirements (FR)
FR-01: The reporting layer SHALL record every executed step with its resulting status.
FR-02: The reporting layer SHALL record each artifact path with a stable kind and identifier, including whether the artifact is synthetic fallback evidence.
FR-03: The reporting layer SHALL record each issue with step id, severity, expected result, actual result, and artifact references.
FR-04: The reporting layer SHALL serialize run results to JSON.
FR-05: The reporting layer SHALL serialize a human-readable Markdown summary.
FR-06: The reporting layer SHALL explicitly mark unsupported executor capabilities as report entries.
FR-07: The reporting layer SHALL preserve the order of steps and issues exactly as executed.
FR-08: The reporting layer SHALL support final statuses of pass, partial, and fail.
FR-09: The reporting layer SHALL keep report generation deterministic for the same input data.
FR-10: The reporting layer SHALL be usable by both desktop and headless executors.

## 4. Data Structures
```python
from dataclasses import dataclass
from typing import Literal


@dataclass
class StepRecord:
    step_id: str
    label: str
    status: Literal["pass", "fail", "skip", "partial"]
    notes: str | None = None


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
    steps: list[StepRecord]
    artifacts: list[ArtifactRecord]
    issues: list[IssueRecord]
    capability_gaps: list[str]
```

## 5. Public API
`godot-client/tests/automation/report_writer.py` SHALL expose:
- `write_json(report: RunReport, path: str) -> str`
- `write_markdown(report: RunReport, path: str) -> str`
- `summarize_capabilities(executor_name: str, gaps: list[str]) -> list[str]`

Preconditions: the run report object must be internally consistent. Postconditions: JSON and Markdown outputs exist at deterministic paths. Exceptions: invalid output path or unserializable content SHALL raise a structured error.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Every executed step appears in the report with its recorded status.
AC-02 [FR-02]: Every artifact is listed with a stable kind and absolute or repo-resolvable path, and any synthetic fallback evidence is labeled explicitly.
AC-03 [FR-03]: Issues include step id, severity, expected, actual, and artifact references.
AC-04 [FR-04]: JSON output can be consumed by automated tooling without parsing Markdown.
AC-05 [FR-05]: Markdown output is human-readable and reflects the same run data as the JSON file.
AC-06 [FR-06]: Missing executor capabilities are visible in the report instead of being omitted.
AC-07 [FR-07]: The report preserves the real execution order of steps and issues.
AC-08 [FR-08]: Pass, partial, and fail statuses are all representable.
AC-09 [FR-09]: Re-running the same input data produces the same report content order and naming.
AC-10 [FR-10]: Both desktop and headless executors can emit reports through the same writer contract.

## 7. Performance Requirements
- Report serialization SHOULD complete in under 100 ms for a short smoke run and under 500 ms for a typical visual QA run on developer hardware.
- Artifact indexing SHOULD remain linear in the number of steps and capture files.

## 8. Error Handling
- Missing artifact paths SHALL be reported as explicit broken evidence entries.
- Synthetic fallback artifacts SHALL be labeled explicitly in both JSON and Markdown output.
- Invalid report data SHALL fail fast with the field that could not be serialized.
- Partial runs SHALL still produce JSON and Markdown outputs if the report object is structurally valid.

## 9. Integration Points
- `godot-client/tests/automation/runner.py`
- `godot-client/tests/automation/artifacts.py`
- `godot-client/tests/automation/executors/base.py`
- `godot-client/tests/automation/executors/win32_desktop.py`
- `godot-client/tests/automation/executors/headless_godot.py`
- `docs/qa/campaign_cutover_visual_log.md`
- `docs/qa/demo_signoff_matrix.md`
- `docs/qa/rimworld_benchmark_report.md`

## 10. Test Coverage Target
- JSON serialization SHALL be tested for pass, partial, and fail runs.
- Markdown formatting SHALL be tested for the same three run states.
- Capability-gap reporting SHALL be covered by unit tests.
- Artifact and issue ordering SHALL be tested with deterministic fixtures.

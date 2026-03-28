from __future__ import annotations

import json
from pathlib import Path

from automation.artifacts import ArtifactManager
from automation.models import ArtifactRecord, IssueRecord, RunReport


def write_report(report: RunReport, artifacts: ArtifactManager) -> tuple[Path, Path]:
    json_path = artifacts.artifact_path("reports", "run_report", ".json")
    md_path = artifacts.artifact_path("reports", "run_report", ".md")
    json_path.write_text(_report_to_json(report), encoding="utf-8")
    md_path.write_text(_report_to_markdown(report), encoding="utf-8")
    return json_path, md_path


def _report_to_json(report: RunReport) -> str:
    payload = {
        "scenario_name": report.scenario_name,
        "executor_name": report.executor_name,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "status": report.status,
        "success": report.success,
        "steps_run": report.steps_run,
        "capability_gaps": report.capability_gaps,
        "notes": report.notes,
        "artifacts": [_artifact_to_dict(entry) for entry in report.artifacts],
        "issues": [_issue_to_dict(entry) for entry in report.issues],
    }
    return json.dumps(payload, indent=2)


def _report_to_markdown(report: RunReport) -> str:
    lines = [
        f"# Visual Automation Report: {report.scenario_name}",
        "",
        f"- Executor: `{report.executor_name}`",
        f"- Started: `{report.started_at}`",
        f"- Finished: `{report.finished_at}`",
        f"- Status: `{report.status}`",
        f"- Success: `{'yes' if report.success else 'no'}`",
        "",
        "## Steps",
    ]
    for step_id in report.steps_run:
        lines.append(f"- `{step_id}`")

    lines.extend(["", "## Capability Gaps"])
    if report.capability_gaps:
        lines.extend(f"- {gap}" for gap in report.capability_gaps)
    else:
        lines.append("- none")

    lines.extend(["", "## Issues"])
    if report.issues:
        for issue in report.issues:
            lines.append(
                f"- `{issue.severity}` `{issue.step_id}`: expected `{issue.expected}` but observed `{issue.actual}`"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Artifacts"])
    if report.artifacts:
        for artifact in report.artifacts:
            suffix = f" ({artifact.note})" if artifact.note else ""
            lines.append(f"- `{artifact.artifact_type}` `{artifact.step_id}`: `{artifact.path}`{suffix}")
    else:
        lines.append("- none")

    if report.notes:
        lines.extend(["", "## Notes"])
        lines.extend(f"- {note}" for note in report.notes)

    lines.append("")
    return "\n".join(lines)


def _artifact_to_dict(entry: ArtifactRecord) -> dict:
    return {
        "step_id": entry.step_id,
        "artifact_type": entry.artifact_type,
        "path": entry.path,
        "note": entry.note,
    }


def _issue_to_dict(entry: IssueRecord) -> dict:
    return {
        "step_id": entry.step_id,
        "severity": entry.severity,
        "expected": entry.expected,
        "actual": entry.actual,
        "artifact_paths": list(entry.artifact_paths),
    }

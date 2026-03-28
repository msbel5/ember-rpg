from __future__ import annotations

import json
from pathlib import Path

from automation.artifacts import ArtifactManager
from automation.models import ArtifactRecord, IssueRecord, RunReport
from automation.report_writer import write_report


def test_write_report_emits_json_and_markdown(tmp_path: Path) -> None:
    artifacts = ArtifactManager(tmp_path, "resume flow", run_id="r1")
    report = RunReport(
        scenario_name="resume flow",
        executor_name="headless_godot",
        started_at="2026-03-28T00:00:00Z",
        finished_at="2026-03-28T00:00:05Z",
        success=False,
        steps_run=["title", "continue"],
    )
    report.add_gap("headless_godot does not support `os_capture`")
    report.add_artifact(
        ArtifactRecord(
            step_id="continue",
            artifact_type="viewport_capture",
            path="proof.png",
            note="synthetic headless fallback",
        )
    )
    report.add_issue(
        IssueRecord(
            step_id="continue",
            severity="major",
            expected="save browser visible",
            actual="blank panel",
            artifact_paths=("proof.png",),
        )
    )

    json_path, md_path = write_report(report, artifacts)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")

    assert payload["scenario_name"] == "resume flow"
    assert payload["status"] == "fail"
    assert payload["issues"][0]["severity"] == "major"
    assert "headless_godot does not support `os_capture`" in markdown
    assert "proof.png" in markdown
    assert "synthetic headless fallback" in markdown

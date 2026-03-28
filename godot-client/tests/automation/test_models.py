from __future__ import annotations

from automation.models import ActionStep, ArtifactRecord, IssueRecord, RunReport


def test_action_step_defaults_are_safe() -> None:
    step = ActionStep(id="intro", action="key_press")

    assert step.description == ""
    assert step.button == "left"
    assert step.repeat == 1
    assert step.wait_ms == 0
    assert step.capture_os is False
    assert step.capture_viewport is False
    assert step.metadata == {}


def test_run_report_major_issue_marks_run_failed() -> None:
    report = RunReport(
        scenario_name="smoke",
        executor_name="dummy",
        started_at="2026-03-28T00:00:00Z",
        finished_at="2026-03-28T00:00:01Z",
        success=True,
    )

    report.add_artifact(ArtifactRecord(step_id="title", artifact_type="os_screenshot", path="shot.png"))
    report.add_issue(IssueRecord(step_id="title", severity="major", expected="visible", actual="blank"))

    assert report.success is False
    assert len(report.artifacts) == 1
    assert len(report.issues) == 1


def test_run_report_tracks_gaps_without_duplicates() -> None:
    report = RunReport(
        scenario_name="smoke",
        executor_name="dummy",
        started_at="2026-03-28T00:00:00Z",
        finished_at="2026-03-28T00:00:01Z",
        success=True,
    )

    report.add_gap("no os capture")
    report.add_gap("no os capture")
    report.add_note("first pass")

    assert report.capability_gaps == ["no os capture"]
    assert report.notes == ["first pass"]

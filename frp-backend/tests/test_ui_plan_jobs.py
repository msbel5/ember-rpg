from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import asset_pipeline as ap


def test_build_ui_plan_jobs_non_empty() -> None:
    jobs = ap.build_ui_plan_jobs()
    assert len(jobs) >= 5


def test_ui_plan_jobs_have_required_fields() -> None:
    jobs = ap.build_ui_plan_jobs()
    assert jobs, "ui_plan jobs should not be empty"
    for job in jobs:
        assert job.key
        assert job.kind == "ui_plan"
        assert len(job.prompt.split()) > 20
        assert job.output_relative_path.startswith("ui_plan/")
        assert isinstance(job.seed, int)

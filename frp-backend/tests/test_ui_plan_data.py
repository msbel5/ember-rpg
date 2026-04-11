from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "tools" / "asset_jobs" / "ui_plan.json"
REQUIRED_FIELDS = {"id", "category", "size", "prompt_hint", "variants"}
EXPECTED_COUNT = 24


def _load_jobs() -> list[dict]:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return payload.get("jobs", [])


def test_ui_plan_file_exists_and_count_matches() -> None:
    assert DATA_PATH.exists(), f"Missing UI plan file: {DATA_PATH}"
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", [])
    assert payload.get("count") == EXPECTED_COUNT
    assert isinstance(jobs, list)
    assert len(jobs) == EXPECTED_COUNT


def test_ui_plan_entries_expose_required_fields() -> None:
    for entry in _load_jobs():
        missing = REQUIRED_FIELDS.difference(entry.keys())
        assert not missing, f"UI plan entry {entry.get('id', '<missing>')} is missing: {sorted(missing)}"
        assert isinstance(entry["size"], list) and len(entry["size"]) == 2
        assert all(isinstance(value, int) and value > 0 for value in entry["size"])
        assert str(entry["prompt_hint"]).strip(), f"UI plan entry {entry['id']} needs a prompt_hint"
        assert isinstance(entry["variants"], int) and entry["variants"] >= 1


def test_ui_plan_has_no_duplicate_ids() -> None:
    ids = [str(entry.get("id", "")).strip() for entry in _load_jobs()]
    assert all(ids), "Every UI plan entry must have a non-empty id"
    assert len(ids) == len(set(ids)), "UI plan entry ids must be unique"

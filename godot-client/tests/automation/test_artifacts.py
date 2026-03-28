from __future__ import annotations

import json
from pathlib import Path

from automation.artifacts import ArtifactManager, sanitize_name


def test_sanitize_name_normalizes_unsafe_characters() -> None:
    assert sanitize_name(" Title Screen / Smoke ") == "Title_Screen_Smoke"
    assert sanitize_name("...") == "artifact"


def test_artifact_manager_creates_deterministic_paths(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path, "title flow", run_id="run:1")

    shot_path = manager.artifact_path("os_screens", "Title Step", ".png")
    assert shot_path == tmp_path / "title_flow" / "run_1" / "os_screens" / "Title_Step.png"


def test_artifact_manager_writes_json_and_text(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path, "title flow", run_id="run-2")

    json_record = manager.write_json("status", "bridge", {"ready": True})
    text_record = manager.write_text("notes", "logs", "ok", ".log")

    assert json.loads(Path(json_record.path).read_text(encoding="utf-8")) == {"ready": True}
    assert Path(text_record.path).read_text(encoding="utf-8") == "ok"
    assert text_record.path.endswith(".log")

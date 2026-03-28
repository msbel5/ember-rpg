from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from automation.models import ArtifactRecord


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_name(value: str) -> str:
    cleaned = SAFE_NAME.sub("_", value.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "artifact"


@dataclass
class ArtifactManager:
    root_dir: Path
    scenario_name: str
    run_id: str | None = None

    def __post_init__(self) -> None:
        run_id = self.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = sanitize_name(run_id)
        self.root_dir = Path(self.root_dir)
        self.run_dir = self.root_dir / sanitize_name(self.scenario_name) / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def artifact_path(self, artifact_type: str, step_id: str, extension: str) -> Path:
        ext = extension if extension.startswith(".") else f".{extension}"
        path = self.run_dir / artifact_type / f"{sanitize_name(step_id)}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def register(self, step_id: str, artifact_type: str, path: str | Path, note: str = "") -> ArtifactRecord:
        return ArtifactRecord(step_id=step_id, artifact_type=artifact_type, path=str(path), note=note)

    def write_json(self, step_id: str, artifact_type: str, payload: dict) -> ArtifactRecord:
        path = self.artifact_path(artifact_type, step_id, ".json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return self.register(step_id, artifact_type, path)

    def write_text(self, step_id: str, artifact_type: str, payload: str, extension: str = ".txt") -> ArtifactRecord:
        path = self.artifact_path(artifact_type, step_id, extension)
        path.write_text(payload, encoding="utf-8")
        return self.register(step_id, artifact_type, path)

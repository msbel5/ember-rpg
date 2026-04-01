from __future__ import annotations

import json
from pathlib import Path

from automation.process_utils import write_json_atomic


def test_write_json_atomic_falls_back_to_direct_overwrite_on_windows_lock(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "command.json"
    target.write_text("{}", encoding="utf-8")

    def always_locked(self: Path, destination: Path) -> Path:
        raise PermissionError("locked")

    monkeypatch.setattr(Path, "replace", always_locked)
    monkeypatch.setattr("automation.process_utils.time.sleep", lambda _seconds: None)

    payload = {"seq": 7, "action": "mouse_click", "x": 42, "y": 18}
    write_json_atomic(target, payload)

    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert not target.with_suffix(".json.tmp").exists()

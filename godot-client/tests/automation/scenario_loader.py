from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from automation.models import ActionStep, AutomationScenario

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility path
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GODOT_EXE = r"C:\Tools\Scoop\apps\godot\current\godot.exe"
DEFAULT_GODOT_CONSOLE = r"C:\Tools\Scoop\apps\godot\current\godot.console.exe"


def load_scenario(path: str | Path) -> AutomationScenario:
    scenario_path = Path(path)
    with scenario_path.open("rb") as handle:
        payload = tomllib.load(handle)

    scenario_data = dict(payload.get("scenario", {}))
    raw_steps = payload.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError(f"Scenario {scenario_path} does not define any [[steps]]")

    steps = tuple(_load_step(entry) for entry in raw_steps)
    name = str(scenario_data.get("name", scenario_path.stem)).strip()
    if not name:
        raise ValueError(f"Scenario {scenario_path} must define a non-empty name")

    return AutomationScenario(
        name=name,
        description=str(scenario_data.get("description", "")).strip(),
        adapter_id=str(scenario_data.get("adapter_id", "fantasy_ember")).strip(),
        player_name=str(scenario_data.get("player_name", "VisualSmoke")).strip(),
        create_new=bool(scenario_data.get("create_new", True)),
        requires_backend=bool(scenario_data.get("requires_backend", True)),
        backend_url=str(scenario_data.get("backend_url", "http://127.0.0.1:8000")).strip(),
        backend_host=str(scenario_data.get("backend_host", "127.0.0.1")).strip(),
        backend_port=int(scenario_data.get("backend_port", 8000)),
        godot_executable=_expand_path(str(scenario_data.get("godot_executable", DEFAULT_GODOT_EXE))),
        godot_console_executable=_expand_path(
            str(scenario_data.get("godot_console_executable", DEFAULT_GODOT_CONSOLE))
        ),
        godot_project_dir=_expand_path(str(scenario_data.get("godot_project_dir", ROOT / "godot-client"))),
        backend_cwd=_expand_path(str(scenario_data.get("backend_cwd", ROOT / "frp-backend"))),
        window_title=str(scenario_data.get("window_title", "Ember RPG (DEBUG)")).strip(),
        initial_scene=str(scenario_data.get("initial_scene", "res://scenes/title_screen.tscn")).strip(),
        run_root=_expand_path(str(scenario_data.get("run_root", ROOT / "tmp" / "visual_automation"))),
        start_wait_ms=int(scenario_data.get("start_wait_ms", 6000)),
        tags=tuple(str(tag) for tag in scenario_data.get("tags", [])),
        steps=steps,
    )


def _load_step(entry: dict[str, Any]) -> ActionStep:
    if not isinstance(entry, dict):
        raise ValueError("Each [[steps]] entry must be a table")

    known_keys = {
        "id",
        "action",
        "description",
        "key",
        "text",
        "x",
        "y",
        "button",
        "duration_ms",
        "repeat",
        "wait_ms",
        "capture_os",
        "capture_viewport",
        "expected",
    }
    step_id = str(entry.get("id", "")).strip()
    action = str(entry.get("action", "")).strip()
    if not step_id or not action:
        raise ValueError("Each step must define non-empty id and action")

    metadata = {key: value for key, value in entry.items() if key not in known_keys}
    return ActionStep(
        id=step_id,
        action=action,
        description=str(entry.get("description", "")).strip(),
        key=_optional_string(entry.get("key")),
        text=_optional_string(entry.get("text")),
        x=_optional_int(entry.get("x")),
        y=_optional_int(entry.get("y")),
        button=str(entry.get("button", "left")).strip() or "left",
        duration_ms=int(entry.get("duration_ms", 0)),
        repeat=max(1, int(entry.get("repeat", 1))),
        wait_ms=max(0, int(entry.get("wait_ms", 0))),
        capture_os=bool(entry.get("capture_os", False)),
        capture_viewport=bool(entry.get("capture_viewport", False)),
        expected=str(entry.get("expected", "")).strip(),
        metadata=metadata,
    )


def _expand_path(value: str) -> str:
    return str(Path(os.path.expandvars(value)).expanduser())


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)

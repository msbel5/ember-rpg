from __future__ import annotations

from pathlib import Path

import pytest

from automation.scenario_loader import load_scenario


def test_load_scenario_parses_defaults_and_metadata(tmp_path: Path) -> None:
    scenario_path = tmp_path / "new_game.toml"
    scenario_path.write_text(
        """
[scenario]
name = "new_game_keyboard_flow"
description = "Keyboard-only onboarding smoke."
adapter_id = "scifi_frontier"
player_name = "Nova"
create_new = true
tags = ["title", "keyboard"]

[[steps]]
id = "focus_title"
action = "activate_window"
capture_os = true
expected = "title screen focused"

[[steps]]
id = "name_text"
action = "text"
text = "Nova"
wait_ms = 50
custom_tag = "kept"
""".strip(),
        encoding="utf-8",
    )

    scenario = load_scenario(scenario_path)

    assert scenario.name == "new_game_keyboard_flow"
    assert scenario.description == "Keyboard-only onboarding smoke."
    assert scenario.adapter_id == "scifi_frontier"
    assert scenario.player_name == "Nova"
    assert scenario.create_new is True
    assert scenario.tags == ("title", "keyboard")
    assert len(scenario.steps) == 2
    assert scenario.steps[0].capture_os is True
    assert scenario.steps[1].text == "Nova"
    assert scenario.steps[1].metadata["custom_tag"] == "kept"
    assert scenario.godot_project_dir.endswith("godot-client")
    assert scenario.backend_cwd.endswith("frp-backend")


def test_load_scenario_requires_steps(tmp_path: Path) -> None:
    scenario_path = tmp_path / "empty.toml"
    scenario_path.write_text("[scenario]\nname='empty'\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not define any"):
        load_scenario(scenario_path)


def test_load_scenario_rejects_missing_step_fields(tmp_path: Path) -> None:
    scenario_path = tmp_path / "bad.toml"
    scenario_path.write_text(
        """
[scenario]
name = "bad"

[[steps]]
id = ""
action = ""
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-empty id and action"):
        load_scenario(scenario_path)

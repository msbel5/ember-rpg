from __future__ import annotations

from pathlib import Path

from automation.scenario_loader import load_scenario


def test_required_scenario_fixtures_exist_and_parse() -> None:
    scenario_dir = Path(__file__).with_name("scenarios")
    required = [
        "title_continue_browser.toml",
        "new_game_keyboard_flow.toml",
        "resume_and_command.toml",
        "world_click_smoke.toml",
        "save_panel_smoke.toml",
    ]

    for filename in required:
        path = scenario_dir / filename
        assert path.exists(), f"missing scenario fixture {filename}"
        scenario = load_scenario(path)
        assert scenario.steps, f"scenario {filename} should define steps"

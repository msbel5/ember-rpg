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


def test_resume_flows_clear_long_player_lookup_values() -> None:
    scenario_dir = Path(__file__).with_name("scenarios")
    for filename in ["resume_and_command.toml", "save_panel_smoke.toml", "world_click_smoke.toml"]:
        scenario = load_scenario(scenario_dir / filename)
        clear_step = next(step for step in scenario.steps if step.id == "clear_player_lookup")
        assert clear_step.repeat >= 32, f"{filename} must clear long remembered player names reliably"


def test_new_game_keyboard_flow_requires_post_identity_change_proof() -> None:
    scenario_dir = Path(__file__).with_name("scenarios")
    scenario = load_scenario(scenario_dir / "new_game_keyboard_flow.toml")

    identity_ready = next(step for step in scenario.steps if step.id == "capture_identity_ready")
    advance_identity = next(step for step in scenario.steps if step.id == "advance_identity")

    assert identity_ready.action == "capture_os"
    assert advance_identity.action == "mouse_click"
    assert advance_identity.metadata.get("expect_artifact_differs_from") == "capture_identity_ready:os_screenshot"

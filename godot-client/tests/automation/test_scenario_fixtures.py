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
        "dialog_interaction_desktop.toml",
        "travel_route_desktop.toml",
        "combat_action_desktop.toml",
    ]

    for filename in required:
        path = scenario_dir / filename
        assert path.exists(), f"missing scenario fixture {filename}"
        scenario = load_scenario(path)
        assert scenario.steps, f"scenario {filename} should define steps"


def test_resume_flows_use_semantic_player_lookup_updates() -> None:
    scenario_dir = Path(__file__).with_name("scenarios")
    for filename in [
        "resume_and_command.toml",
        "save_panel_smoke.toml",
        "world_click_smoke.toml",
        "dialog_interaction_desktop.toml",
        "travel_route_desktop.toml",
        "combat_action_desktop.toml",
    ]:
        scenario = load_scenario(scenario_dir / filename)
        set_step = next(step for step in scenario.steps if step.id == "set_player_lookup")
        wait_button = next(step for step in scenario.steps if step.id == "wait_for_load_button")
        wait_scene = next(step for step in scenario.steps if step.id == "wait_for_game_session")
        assert set_step.action == "set_text_node", f"{filename} should update player lookup semantically"
        assert set_step.node_path == "LoadBrowser/VBox/PlayerRow/PlayerInput"
        assert wait_button.action == "wait_for_node_visible", f"{filename} should wait for the load button semantically"
        assert wait_button.node_path == "LoadBrowser/VBox/SaveScroll/SaveList/SaveRow0/LoadButton0"
        assert wait_scene.action == "wait_for_scene", f"{filename} should wait for the gameplay scene semantically"
        assert wait_scene.scene_name == "GameSession"


def test_new_game_keyboard_flow_requires_post_identity_change_proof() -> None:
    scenario_dir = Path(__file__).with_name("scenarios")
    scenario = load_scenario(scenario_dir / "new_game_keyboard_flow.toml")

    identity_ready = next(step for step in scenario.steps if step.id == "capture_identity_ready")
    advance_identity = next(step for step in scenario.steps if step.id == "advance_identity")

    assert identity_ready.action == "capture_viewport"
    assert advance_identity.action == "activate_node"
    assert advance_identity.metadata.get("expect_artifact_differs_from") == "capture_identity_ready:viewport_capture"


def test_vertical_desktop_scenarios_target_semantic_dialog_travel_and_combat() -> None:
    scenario_dir = Path(__file__).with_name("scenarios")

    dialog = load_scenario(scenario_dir / "dialog_interaction_desktop.toml")
    assert next(step for step in dialog.steps if step.id == "wait_for_dialog").action == "wait_for_node_visible"
    assert next(step for step in dialog.steps if step.id == "choose_first_dialog_option").node_path.endswith("OptionButton0")
    assert next(step for step in dialog.steps if step.id == "close_dialog").action == "activate_node"

    travel = load_scenario(scenario_dir / "travel_route_desktop.toml")
    assert next(step for step in travel.steps if step.id == "open_map_tab").action == "activate_node"
    assert next(step for step in travel.steps if step.id == "wait_for_route_button").node_path.endswith("RouteButton0")
    assert next(step for step in travel.steps if step.id == "wait_for_active_travel_summary").action == "wait_for_node_text"
    assert next(step for step in travel.steps if step.id == "wait_for_continue_travel").node_path.endswith("ContinueTravelButton")
    assert next(step for step in travel.steps if step.id == "continue_travel_once").action == "activate_node"
    assert next(step for step in travel.steps if step.id == "wait_for_continue_history").text == "continue travel"

    combat = load_scenario(scenario_dir / "combat_action_desktop.toml")
    assert next(step for step in combat.steps if step.id == "enter_combat").action == "activate_node"
    assert next(step for step in combat.steps if step.id == "prepare_attack").node_path.endswith("TextInput")
    assert next(step for step in combat.steps if step.id == "wait_for_attack_history").text == "attack wolf"
    assert next(step for step in combat.steps if step.id == "wait_for_combat_panel").node_path == "OverlayCanvas/CombatPanel"
    assert next(step for step in combat.steps if step.id == "use_end_turn").node_path.endswith("EndTurnButton")

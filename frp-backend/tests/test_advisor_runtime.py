from __future__ import annotations

import copy

from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel.combat_engine import CombatState, CombatantEntry
from engine.kernel.hybrid_types import TravelState


def _make_campaign(seed: int = 42) -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="AdvisorTester", seed=seed)
    return runtime, context


def test_raw_ask_dm_returns_spoiler_safe_advisor_view() -> None:
    runtime, context = _make_campaign()

    result = runtime.run_command(context.campaign_id, "ask dm where should I go")

    assert result["command_type"] == "advisor"
    assert result["hours_advanced"] == 0
    assert isinstance(result["advisor_view"], dict)
    assert result["advisor_view"]["spoiler_safe"] is True
    assert result["advisor_view"]["intent"] in {
        "objective",
        "navigation",
        "combat",
        "resources",
        "social",
        "unknown",
    }
    assert "advisor" not in result["campaign"]
    assert "advisor_view" not in result["campaign"]


def test_structured_ask_dm_returns_advisor_view() -> None:
    runtime, context = _make_campaign(seed=43)

    result = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="advisor",
        args={"action_id": "ask_dm", "query": "what should I do next"},
    )

    assert result["command_type"] == "advisor"
    assert result["hours_advanced"] == 0
    assert isinstance(result["advisor_view"]["answer_lines"], list)
    assert isinstance(result["advisor_view"]["suggested_commands"], list)
    assert isinstance(result["advisor_view"]["blockers"], list)


def test_ask_dm_during_combat_does_not_mutate_combat_state() -> None:
    runtime, context = _make_campaign(seed=44)
    combat_state = CombatState(
        combatants=[CombatantEntry(actor_id="player", initiative=20, is_player=True)],
        current_turn_index=0,
        phase="active",
    )
    context.kernel_runtime["game_state"].raw_payload["combat"] = combat_state.to_dict()
    before = copy.deepcopy(context.kernel_runtime["game_state"].raw_payload["combat"])

    result = runtime.run_command(context.campaign_id, "ask dm what should I prioritize")

    assert result["command_type"] == "advisor"
    assert result["advisor_view"]["intent"] == "combat"
    after = context.kernel_runtime["game_state"].raw_payload["combat"]
    assert after["phase"] == before["phase"]
    assert after["current_turn_index"] == before["current_turn_index"]
    assert after["combatants"][0]["actor_id"] == before["combatants"][0]["actor_id"]
    assert after["combatants"][0]["turn_resources"] == before["combatants"][0]["turn_resources"]


def test_ask_dm_during_travel_does_not_mutate_travel_state() -> None:
    runtime, context = _make_campaign(seed=45)
    travel_state = TravelState(
        status="traveling",
        origin_region_id=str(context.region_snapshot.region_id),
        destination_region_id="test_destination",
        travel_hours_remaining=2,
        travel_hours_total=5,
        danger_level=2,
        paused_for_encounter=True,
        encounter_triggered=True,
    )
    context.kernel_runtime["travel_state"] = travel_state
    context.kernel_runtime["game_state"].raw_payload["travel_state"] = travel_state.to_dict()
    before = copy.deepcopy(context.kernel_runtime["game_state"].raw_payload["travel_state"])

    result = runtime.run_command(context.campaign_id, "ask dm how dangerous is this road")

    assert result["command_type"] == "advisor"
    assert result["advisor_view"]["intent"] == "navigation"
    assert "travel_paused_for_encounter" in result["advisor_view"]["blockers"]
    assert context.kernel_runtime["game_state"].raw_payload["travel_state"] == before


def test_unknown_advisor_query_fails_softly_with_advisor_view() -> None:
    runtime, context = _make_campaign(seed=46)

    result = runtime.run_command(context.campaign_id, "ask dm zzqx narrative entropy")

    assert result["command_type"] == "advisor"
    assert isinstance(result["advisor_view"], dict)
    assert result["command_type"] != "unknown"

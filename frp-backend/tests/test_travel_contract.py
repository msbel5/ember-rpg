from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime


def _runtime_campaign(seed: int = 42):
    runtime = CampaignRuntime()
    context = runtime.create_campaign(
        player_name="TravelProbe",
        player_class="warrior",
        adapter_id="fantasy_ember",
        profile_id="standard",
        seed=seed,
    )
    return runtime, context


def _first_travel_destination(snapshot: dict) -> dict:
    travel_options = list(snapshot["campaign"]["travel_options"])
    destination = next(option for option in travel_options if not option.get("is_current"))
    assert destination["route_id"]
    assert destination["destination_region_id"]
    return destination


def _travel_snapshot(runtime: CampaignRuntime, campaign_id: str) -> dict:
    return runtime.snapshot(campaign_id, narrative="travel")


def test_travel_start_blocks_immediate_region_switch_and_exposes_state():
    runtime, context = _runtime_campaign(seed=77)
    start_snapshot = _travel_snapshot(runtime, context.campaign_id)
    origin_region_id = start_snapshot["campaign"]["world"]["active_region_id"]
    destination = _first_travel_destination(start_snapshot)

    result = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="travel",
        args={
            "action_id": "start",
            "route_id": destination["route_id"],
            "destination_region_id": destination["destination_region_id"],
            "destination_settlement_id": destination["destination_settlement_id"],
        },
    )

    campaign = result["campaign"]
    assert result["command_type"] == "travel"
    assert campaign["scene"] == "travel"
    assert campaign["world"]["active_region_id"] == origin_region_id
    assert campaign["path_authority"]["active_region_id"] == origin_region_id
    assert isinstance(campaign["travel_state"], dict)
    assert campaign["travel_state"]["route_id"] == destination["route_id"]
    assert campaign["travel_state"]["origin_region_id"] == origin_region_id
    assert campaign["travel_state"]["destination_region_id"] == destination["destination_region_id"]
    assert campaign["travel_state"]["destination_settlement_id"] == destination["destination_settlement_id"]
    assert campaign["travel_state"]["destination_name"] == destination["destination_name"]
    assert campaign["travel_state"]["travel_hours_total"] >= campaign["travel_state"]["travel_hours_remaining"] >= 0


def test_travel_advances_then_completes_and_clears_travel_state():
    runtime, context = _runtime_campaign(seed=88)
    start_snapshot = _travel_snapshot(runtime, context.campaign_id)
    origin_region_id = start_snapshot["campaign"]["world"]["active_region_id"]
    destination = _first_travel_destination(start_snapshot)

    current = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="travel",
        args={
            "action_id": "start",
            "route_id": destination["route_id"],
            "destination_region_id": destination["destination_region_id"],
            "destination_settlement_id": destination["destination_settlement_id"],
        },
    )

    for _ in range(12):
        travel_state = current["campaign"].get("travel_state")
        if travel_state is None:
            break
        if travel_state.get("paused_for_encounter"):
            resolved = runtime.run_command(
                context.campaign_id,
                "",
                shortcut="travel",
                args={"action_id": "resolve_encounter"},
            )
            assert resolved["campaign"]["travel_state"]["encounter_resolved"] is True
            assert resolved["campaign"]["travel_state"]["paused_for_encounter"] is False
            current = resolved
            continue

        before_remaining = int(travel_state["travel_hours_remaining"])
        advanced = runtime.run_command(
            context.campaign_id,
            "",
            shortcut="travel",
            args={"action_id": "advance"},
        )
        after_state = advanced["campaign"].get("travel_state")
        if after_state is None:
            current = advanced
            break
        assert int(after_state["travel_hours_remaining"]) in {max(0, before_remaining - 1), before_remaining}
        current = advanced
    else:
        pytest.fail("travel did not complete within the expected number of steps")

    campaign = current["campaign"]
    assert campaign["travel_state"] is None
    assert campaign["world"]["active_region_id"] == destination["destination_region_id"]
    assert campaign["world"]["active_region_id"] != origin_region_id
    assert campaign["path_authority"]["active_region_id"] == destination["destination_region_id"]


def test_raw_travel_command_uses_same_travel_contract():
    runtime, context = _runtime_campaign(seed=89)
    start_snapshot = _travel_snapshot(runtime, context.campaign_id)
    destination = _first_travel_destination(start_snapshot)

    result = runtime.run_command(
        context.campaign_id,
        f"travel {destination['destination_region_id']}",
    )

    campaign = result["campaign"]
    assert result["command_type"] == "travel"
    assert campaign["scene"] == "travel"
    assert isinstance(campaign["travel_state"], dict)
    assert campaign["travel_state"]["route_id"] == destination["route_id"]

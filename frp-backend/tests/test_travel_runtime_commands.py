from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel.hybrid_types import TravelState


def _runtime_campaign(seed: int = 42) -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(
        player_name="TravelCommander",
        player_class="warrior",
        adapter_id="fantasy_ember",
        profile_id="standard",
        seed=seed,
    )
    return runtime, context


def _travel_snapshot(runtime: CampaignRuntime, campaign_id: str) -> dict:
    return runtime.snapshot(campaign_id, narrative="travel-runtime")


def _first_travel_destination(snapshot: dict) -> dict:
    options = list(snapshot["campaign"]["travel_options"])
    destination = next(option for option in options if not option.get("is_current"))
    assert destination["route_id"]
    assert destination["destination_region_id"]
    return destination


def _runtime_travel_state(context) -> TravelState:
    travel_state = context.kernel_runtime["travel_state"]
    if isinstance(travel_state, TravelState):
        return travel_state
    return TravelState.from_dict(dict(travel_state))


def _set_runtime_travel_state(context, **overrides: object) -> TravelState:
    state = TravelState.from_dict(_runtime_travel_state(context).to_dict())
    for key, value in overrides.items():
        setattr(state, key, value)
    context.kernel_runtime["travel_state"] = state
    return state


def test_structured_start_prefers_route_id_without_region_switch() -> None:
    runtime, context = _runtime_campaign(seed=71)
    start = _travel_snapshot(runtime, context.campaign_id)
    origin_region_id = start["campaign"]["world"]["active_region_id"]
    destination = _first_travel_destination(start)

    result = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="travel",
        args={
            "action_id": "start",
            "route_id": destination["route_id"],
            "destination_region_id": "bogus_region_id",
            "destination_settlement_id": "bogus_settlement_id",
        },
    )

    campaign = result["campaign"]
    assert result["command_type"] == "travel"
    assert result["hours_advanced"] == 0
    assert campaign["scene"] == "travel"
    assert campaign["world"]["active_region_id"] == origin_region_id
    assert campaign["path_authority"]["active_region_id"] == origin_region_id
    assert campaign["travel_state"]["route_id"] == destination["route_id"]
    assert campaign["travel_state"]["destination_region_id"] == destination["destination_region_id"]


def test_raw_travel_command_starts_without_immediate_region_switch() -> None:
    runtime, context = _runtime_campaign(seed=72)
    start = _travel_snapshot(runtime, context.campaign_id)
    origin_region_id = start["campaign"]["world"]["active_region_id"]
    destination = _first_travel_destination(start)

    result = runtime.run_command(context.campaign_id, f"travel {destination['destination_region_id']}")

    assert result["command_type"] == "travel"
    assert result["campaign"]["scene"] == "travel"
    assert result["campaign"]["world"]["active_region_id"] == origin_region_id
    assert result["campaign"]["travel_state"]["destination_region_id"] == destination["destination_region_id"]


def test_continue_and_resume_advance_exactly_one_hour_each() -> None:
    runtime, context = _runtime_campaign(seed=73)
    destination = _first_travel_destination(_travel_snapshot(runtime, context.campaign_id))

    started = runtime.run_command(
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
    started_remaining = int(started["campaign"]["travel_state"]["travel_hours_remaining"])
    _set_runtime_travel_state(context, danger_level=0, encounter_checked=False, paused_for_encounter=False, encounter_resolved=False)

    continued = runtime.run_command(context.campaign_id, "continue travel")
    resumed = runtime.run_command(context.campaign_id, "resume travel")

    assert continued["command_type"] == "travel"
    assert continued["hours_advanced"] == 1
    assert int(continued["campaign"]["travel_state"]["travel_hours_remaining"]) == started_remaining - 1
    assert resumed["command_type"] == "travel"
    assert resumed["hours_advanced"] == 1
    assert int(resumed["campaign"]["travel_state"]["travel_hours_remaining"]) == started_remaining - 2


def test_paused_encounter_blocks_advance_until_resolved() -> None:
    runtime, context = _runtime_campaign(seed=74)
    destination = _first_travel_destination(_travel_snapshot(runtime, context.campaign_id))

    runtime.run_command(
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
    _set_runtime_travel_state(
        context,
        status="traveling",
        travel_hours_remaining=3,
        danger_level=0,
        encounter_triggered=True,
        paused_for_encounter=True,
        encounter_resolved=False,
    )

    blocked = runtime.run_command(context.campaign_id, "continue travel")

    assert blocked["command_type"] == "travel"
    assert blocked["hours_advanced"] == 0
    assert blocked["narrative"] == "Travel is paused by an encounter. Resolve the travel encounter before moving on."
    assert blocked["campaign"]["travel_state"]["paused_for_encounter"] is True
    assert blocked["campaign"]["travel_state"]["encounter_resolved"] is False
    assert int(blocked["campaign"]["travel_state"]["travel_hours_remaining"]) == 3


def test_resolve_travel_encounter_unblocks_progress() -> None:
    runtime, context = _runtime_campaign(seed=75)
    destination = _first_travel_destination(_travel_snapshot(runtime, context.campaign_id))

    runtime.run_command(
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
    _set_runtime_travel_state(
        context,
        status="traveling",
        travel_hours_remaining=3,
        danger_level=0,
        encounter_triggered=True,
        paused_for_encounter=True,
        encounter_resolved=False,
    )

    resolved = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="travel",
        args={"action_id": "resolve_encounter"},
    )
    advanced = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="travel",
        args={"action_id": "advance"},
    )

    assert resolved["command_type"] == "travel"
    assert resolved["hours_advanced"] == 0
    assert resolved["campaign"]["travel_state"]["paused_for_encounter"] is False
    assert resolved["campaign"]["travel_state"]["encounter_resolved"] is True
    assert advanced["command_type"] == "travel"
    assert advanced["hours_advanced"] == 1
    assert int(advanced["campaign"]["travel_state"]["travel_hours_remaining"]) == 2


def test_arrival_switches_region_and_clears_active_travel_state() -> None:
    runtime, context = _runtime_campaign(seed=76)
    start = _travel_snapshot(runtime, context.campaign_id)
    origin_region_id = start["campaign"]["world"]["active_region_id"]
    destination = _first_travel_destination(start)

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
    _set_runtime_travel_state(context, danger_level=0, encounter_checked=False, paused_for_encounter=False, encounter_resolved=False)

    for _ in range(8):
        if current["campaign"].get("travel_state") is None:
            break
        current = runtime.run_command(context.campaign_id, "continue travel")
    else:
        raise AssertionError("Travel did not complete within expected command budget")

    assert current["command_type"] == "travel"
    assert current["campaign"]["travel_state"] is None
    assert current["campaign"]["world"]["active_region_id"] == destination["destination_region_id"]
    assert current["campaign"]["world"]["active_region_id"] != origin_region_id
    assert current["campaign"]["path_authority"]["active_region_id"] == destination["destination_region_id"]
    assert current["campaign"]["local_map_state"]["region_id"] == destination["destination_region_id"]


def test_unrelated_commands_reject_during_active_travel() -> None:
    runtime, context = _runtime_campaign(seed=77)
    destination = _first_travel_destination(_travel_snapshot(runtime, context.campaign_id))

    runtime.run_command(
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

    rejected = runtime.run_command(context.campaign_id, "look around")

    assert rejected["command_type"] == "travel"
    assert rejected["hours_advanced"] == 0
    assert rejected["narrative"] == "You are already traveling. Use continue travel, resolve travel encounter, or wait for arrival."
    assert rejected["campaign"]["scene"] == "travel"


def test_rest_rejects_explicitly_during_active_travel() -> None:
    runtime, context = _runtime_campaign(seed=78)
    destination = _first_travel_destination(_travel_snapshot(runtime, context.campaign_id))

    runtime.run_command(
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

    rejected = runtime.run_command(context.campaign_id, "rest")

    assert rejected["command_type"] == "travel"
    assert rejected["hours_advanced"] == 0
    assert rejected["narrative"] == "You cannot rest while actively traveling."
    assert rejected["campaign"]["scene"] == "travel"
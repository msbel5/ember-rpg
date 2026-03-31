"""Targeted tests for campaign commander directives."""

from engine.api.campaign_runtime import CampaignRuntime


def _runtime() -> CampaignRuntime:
    return CampaignRuntime(llm=lambda _prompt: "stub")


def test_assign_build_and_travel_commands_update_campaign_state():
    runtime = _runtime()
    context = runtime.create_campaign("Commander", adapter_id="fantasy_ember", seed=42)
    previous_region_id = context.region_snapshot.region_id
    resident_name = context.settlement_state["residents"][1]["name"]

    assigned = runtime.run_command(context.campaign_id, f"assign {resident_name} to hauling")
    assert assigned["command_type"] == "commander"
    assert any(job["kind"] == "hauling" for job in assigned["campaign"]["settlement"]["jobs"])
    assert any(job["kind"] == "hauling" for job in assigned["campaign"]["jobs"])
    assert assigned["campaign"]["worksites"]

    built = runtime.run_command(context.campaign_id, "build warehouse")
    assert built["campaign"]["settlement"]["construction_queue"]
    assert built["campaign"]["colony_pressure"]["supply"] >= 0
    assert built["campaign"]["path_authority"]["active_region_id"] == built["campaign"]["world"]["active_region_id"]
    assert "power_network" in built["campaign"]["systems"]

    travel_target = built["campaign"]["travel_options"][0]
    traveled = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="travel",
        args={
            "destination_region_id": travel_target["destination_region_id"],
            "destination_settlement_id": travel_target["destination_settlement_id"],
        },
    )
    assert traveled["command_type"] == "travel"
    assert traveled["campaign"]["world"]["active_region_id"] != previous_region_id
    assert traveled["campaign"]["local_map_state"]["region_id"] == traveled["campaign"]["world"]["active_region_id"]


def test_defend_and_stockpile_commands_change_settlement_controls():
    runtime = _runtime()
    context = runtime.create_campaign("Commander", adapter_id="scifi_frontier", seed=99)

    defend = runtime.run_command(context.campaign_id, "defend")
    assert defend["campaign"]["settlement"]["defense_posture"] == "fortified"
    assert "unrest" in defend["campaign"]["colony_pressure"]
    assert defend["campaign"]["military"]["defense_posture"] == "fortified"
    assert defend["campaign"]["systems"]["traps"]

    stockpile = runtime.run_command(context.campaign_id, "set stockpile medkits")
    stockpiles = stockpile["campaign"]["settlement"]["stockpiles"]
    assert any(entry["label"] == "Medkits Stockpile" for entry in stockpiles)

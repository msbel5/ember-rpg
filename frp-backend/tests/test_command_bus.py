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

    built = runtime.run_command(context.campaign_id, "build warehouse")
    assert built["campaign"]["settlement"]["construction_queue"]

    traveled = runtime.run_command(context.campaign_id, "travel next outpost")
    assert traveled["command_type"] == "travel"
    assert traveled["campaign"]["world"]["active_region_id"] != previous_region_id


def test_defend_and_stockpile_commands_change_settlement_controls():
    runtime = _runtime()
    context = runtime.create_campaign("Commander", adapter_id="scifi_frontier", seed=99)

    defend = runtime.run_command(context.campaign_id, "defend")
    assert defend["campaign"]["settlement"]["defense_posture"] == "fortified"

    stockpile = runtime.run_command(context.campaign_id, "set stockpile medkits")
    stockpiles = stockpile["campaign"]["settlement"]["stockpiles"]
    assert any(entry["label"] == "Medkits Stockpile" for entry in stockpiles)

from __future__ import annotations

import pathlib
import sys

TESTS_DIR = pathlib.Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.append(str(TESTS_DIR))

import pytest

import engine.api.campaign.runtime_commands as runtime_commands
from _release_gate_helpers import (  # noqa: E402
    advance_active_travel,
    canonical_release_state,
    choose_attack_tick,
    first_live_store_item,
    first_live_travel_route,
    inject_hostile_npc_for_attack,
    inject_ready_to_report_quest,
    inject_recruitable_companion,
    inventory_quantity,
    make_runtime_campaign,
    seed_live_store_item,
    seed_player_gold,
    set_target_tick,
)


SLICE_SEED = 212


@pytest.fixture(autouse=True)
def _no_world_advance(monkeypatch: pytest.MonkeyPatch) -> None:
    real_advance_world = runtime_commands._advance_world

    def _wrapped_advance_world(context, command_type, hours_advanced, command_text):
        if command_type == "commerce":
            return []
        return real_advance_world(context, command_type, hours_advanced, command_text)

    monkeypatch.setattr(runtime_commands, "_advance_world", _wrapped_advance_world)


def test_backend_first_playable_slice_acceptance() -> None:
    runtime, context = make_runtime_campaign(player_name="SliceTester", seed=SLICE_SEED)
    seed_player_gold(context, 500)
    seed_live_store_item(context, item_def_id="bread", quantity=3)
    create_snapshot = runtime.snapshot(context.campaign_id, narrative="slice-create")
    _store_id, item_id = first_live_store_item(create_snapshot)
    route = first_live_travel_route(create_snapshot)

    companion = inject_recruitable_companion(
        context,
        actor_id="slice_scout_mira",
        name="Scout Mira",
        role="scout",
    )
    recruit = runtime.run_command(context.campaign_id, "recruit Scout Mira")

    player_before_buy = context.kernel_runtime["actors"]["player"]
    gold_before_buy = int(player_before_buy.raw_payload.get("gold", 0) or 0)
    quantity_before_buy = inventory_quantity(context, item_id)
    buy = runtime.run_command(context.campaign_id, f"buy {item_id}")
    quantity_after_buy = inventory_quantity(context, item_id)
    gold_after_buy = int(context.kernel_runtime["actors"]["player"].raw_payload.get("gold", 0) or 0)

    travel_result, travel_history = advance_active_travel(runtime, context, route)

    fang = inject_hostile_npc_for_attack(
        context,
        actor_id="slice_replay_fang",
        name="Slice Fang",
        role="wolf",
        near_future_player_step=False,
    )
    set_target_tick(context, choose_attack_tick(context))
    combat = runtime.run_command(context.campaign_id, "attack Slice Fang")

    inject_ready_to_report_quest(
        context,
        quest_id="supply_run",
        title="Supply Run",
        reward_gold=25,
        reward_xp=50,
    )
    player_before_report = context.kernel_runtime["actors"]["player"]
    gold_before_report = int(player_before_report.raw_payload.get("gold", 0) or 0)
    xp_before_report = int(player_before_report.raw_payload.get("xp", 0) or 0)
    report = runtime.run_command(context.campaign_id, "report supply_run")
    gold_after_report = int(context.kernel_runtime["actors"]["player"].raw_payload.get("gold", 0) or 0)
    xp_after_report = int(context.kernel_runtime["actors"]["player"].raw_payload.get("xp", 0) or 0)

    before_load = canonical_release_state(runtime, context)
    runtime.save_campaign(context.campaign_id, "backend_first_playable_slice_slot", "SliceTester")
    loaded = runtime.load_campaign("backend_first_playable_slice_slot")
    after_load = canonical_release_state(runtime, loaded)

    assert create_snapshot["campaign"]["world"]["active_region_id"]
    assert recruit["command_type"] == "party"
    assert companion.identity.actor_id in context.kernel_runtime["game_state"].party
    assert companion.identity.actor_id in recruit["campaign"]["party"]

    assert buy["command_type"] == "commerce"
    assert quantity_after_buy == quantity_before_buy + 1
    assert gold_after_buy <= gold_before_buy

    assert travel_history[0]["command_type"] == "travel"
    assert travel_result["command_type"] == "travel"
    assert isinstance(travel_history[0]["campaign"]["travel_state"], dict)
    assert travel_history[0]["campaign"]["travel_state"]["route_id"] == route["route_id"]
    assert travel_result["campaign"]["travel_state"] is None
    assert travel_result["campaign"]["world"]["active_region_id"] == route["destination_region_id"]

    assert combat["command_type"] == "combat"
    assert context.kernel_runtime["actors"][fang.identity.actor_id].alive is False
    assert combat["campaign"]["combat"] is None or isinstance(combat["campaign"]["combat"], dict)
    if isinstance(combat["campaign"]["combat"], dict):
        combatant_ids = {entry["actor_id"] for entry in combat["campaign"]["combat"]["combatants"]}
        assert fang.identity.actor_id in combatant_ids
        assert any(target["actor_id"] == fang.identity.actor_id for target in combat["campaign"]["combat"]["targets"])

    assert report["command_type"] == "quest"
    assert "Completed quest: Supply Run." in report["narrative"]
    assert "supply_run" in context.campaign_state["completed_quest_ids"]
    assert "supply_run" not in {entry.get("quest_id") for entry in context.campaign_state.get("active_quests", [])}
    assert gold_after_report == gold_before_report + 25
    assert xp_after_report == xp_before_report + 50

    assert before_load == after_load
    assert loaded.kernel_runtime["game_state"].party == context.kernel_runtime["game_state"].party
    assert "supply_run" in loaded.campaign_state.get("completed_quest_ids", [])
    assert loaded.campaign_state.get("reserve_party_members", []) == context.campaign_state.get("reserve_party_members", [])

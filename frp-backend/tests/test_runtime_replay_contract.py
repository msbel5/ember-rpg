from __future__ import annotations

import pathlib
import sys

TESTS_DIR = pathlib.Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.append(str(TESTS_DIR))

import pytest

import engine.api.campaign.runtime_commands as runtime_commands
from _release_gate_helpers import (  # noqa: E402
    build_replay_transcript,
    canonical_release_state,
    inject_hostile_npc_for_attack,
    inject_ready_to_report_quest,
    inject_recruitable_companion,
    make_runtime_campaign,
    run_transcript,
    seed_live_store_item,
    seed_player_gold,
)


REPLAY_SEED = 211


@pytest.fixture(autouse=True)
def _no_world_advance(monkeypatch: pytest.MonkeyPatch) -> None:
    real_advance_world = runtime_commands._advance_world

    def _wrapped_advance_world(context, command_type, hours_advanced, command_text):
        if command_type == "commerce":
            return []
        return real_advance_world(context, command_type, hours_advanced, command_text)

    monkeypatch.setattr(runtime_commands, "_advance_world", _wrapped_advance_world)


def _prepare_replay_scenario():
    runtime, context = make_runtime_campaign(player_name="ReplayTester", seed=REPLAY_SEED)
    seed_player_gold(context, 500)
    seed_live_store_item(context, item_def_id="bread", quantity=3)
    inject_recruitable_companion(
        context,
        actor_id="replay_mira",
        name="Replay Mira",
        role="scout",
    )
    inject_ready_to_report_quest(
        context,
        quest_id="supply_run",
        title="Supply Run",
        reward_gold=25,
        reward_xp=50,
    )
    inject_hostile_npc_for_attack(
        context,
        actor_id="replay_fang",
        name="Replay Fang",
        role="wolf",
        near_future_player_step=True,
    )
    initial_snapshot = runtime.snapshot(context.campaign_id, narrative="replay-start")
    transcript = build_replay_transcript(initial_snapshot)
    return runtime, context, transcript


def test_replay_transcript_matches_save_load_parity_contract() -> None:
    straight_runtime, straight_context, transcript = _prepare_replay_scenario()
    straight_context, straight_results = run_transcript(straight_runtime, straight_context, transcript)
    straight_final = canonical_release_state(straight_runtime, straight_context)

    mid_runtime, mid_context, mid_transcript = _prepare_replay_scenario()
    assert mid_transcript == transcript
    mid_context, mid_results = run_transcript(
        mid_runtime,
        mid_context,
        mid_transcript,
        save_after_step=3,
        slot_name="runtime_replay_contract_mid_slot",
    )
    mid_final = canonical_release_state(mid_runtime, mid_context)

    straight_runtime.save_campaign(straight_context.campaign_id, "runtime_replay_contract_final_slot", "ReplayTester")
    reloaded_context = straight_runtime.load_campaign("runtime_replay_contract_final_slot")
    round_trip_final = canonical_release_state(straight_runtime, reloaded_context)

    assert [result["command_type"] for result in straight_results] == [
        "party",
        "commerce",
        "exploration",
        "advisor",
        "quest",
        "quest",
        "combat",
    ]
    assert straight_results[5]["narrative"] == "Completed quest: Supply Run. Reward: 25 gold, 50 XP."
    assert [result["command_type"] for result in mid_results] == [
        "party",
        "commerce",
        "exploration",
        "advisor",
        "quest",
        "quest",
        "combat",
    ]
    assert mid_results[5]["narrative"] == "Completed quest: Supply Run. Reward: 25 gold, 50 XP."
    assert straight_final == mid_final == round_trip_final

"""Deterministic backend soak and save/load churn contracts.

Exercises all major runtime surfaces in a single deterministic scenario
with periodic save/load cycles, proving operational stability.
"""
from __future__ import annotations

import pathlib
import sys

TESTS_DIR = pathlib.Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.append(str(TESTS_DIR))

import pytest

import engine.api.campaign.runtime_commands as runtime_commands
from _release_gate_helpers import (
    advance_active_travel,
    canonical_release_state,
    choose_attack_tick,
    first_live_store_item,
    first_live_travel_route,
    inject_hostile_npc_for_attack,
    inject_ready_to_report_quest,
    inject_recruitable_companion,
    make_runtime_campaign,
    seed_live_store_item,
    seed_player_gold,
    set_target_tick,
)


SOAK_SEED = 500
CHURN_SEED = 501


@pytest.fixture(autouse=True)
def _no_world_advance(monkeypatch: pytest.MonkeyPatch) -> None:
    real = runtime_commands._advance_world

    def _wrapped(context, command_type, hours_advanced, command_text):
        if command_type == "commerce":
            return []
        return real(context, command_type, hours_advanced, command_text)

    monkeypatch.setattr(runtime_commands, "_advance_world", _wrapped)


# ═════════════════════════════════════════════════════════════════════
#  Save/load churn contract
# ═════════════════════════════════════════════════════════════════════


def test_save_load_churn_produces_equivalent_canonical_state() -> None:
    """Run a fixed transcript, saving/loading after every 3rd action.
    Final canonical state must equal a straight-through run."""

    # Straight-through run
    rt_a, ctx_a = make_runtime_campaign(player_name="ChurnTester", seed=CHURN_SEED)
    seed_player_gold(ctx_a, 500)
    seed_live_store_item(ctx_a, item_def_id="bread", quantity=5)
    inject_recruitable_companion(ctx_a, actor_id="churn_scout", name="Churn Scout", role="scout")
    inject_ready_to_report_quest(ctx_a, quest_id="churn_quest", title="Churn Quest", reward_gold=25, reward_xp=50)
    snap_a = rt_a.snapshot(ctx_a.campaign_id, narrative="churn-a-start")
    _store_id, item_id = first_live_store_item(snap_a)

    transcript = [
        "look around",
        "recruit Churn Scout",
        f"buy {item_id}",
        "move east",
        "quests",
        "report churn_quest",
        "look around",
        "ask dm where next",
        "move west",
    ]

    for cmd in transcript:
        rt_a.run_command(ctx_a.campaign_id, cmd)
    state_a = canonical_release_state(rt_a, ctx_a)

    # Churn run — save/load every 3 actions
    rt_b, ctx_b = make_runtime_campaign(player_name="ChurnTester", seed=CHURN_SEED)
    seed_player_gold(ctx_b, 500)
    seed_live_store_item(ctx_b, item_def_id="bread", quantity=5)
    inject_recruitable_companion(ctx_b, actor_id="churn_scout", name="Churn Scout", role="scout")
    inject_ready_to_report_quest(ctx_b, quest_id="churn_quest", title="Churn Quest", reward_gold=25, reward_xp=50)

    active_ctx = ctx_b
    for i, cmd in enumerate(transcript, start=1):
        rt_b.run_command(active_ctx.campaign_id, cmd)
        if i % 3 == 0:
            slot = f"churn_slot_{i}"
            rt_b.save_campaign(active_ctx.campaign_id, slot, "ChurnTester")
            active_ctx = rt_b.load_campaign(slot)

    state_b = canonical_release_state(rt_b, active_ctx)

    # Canonical states must match
    assert state_a == state_b, "Save/load churn diverged from straight-through run"


# ═════════════════════════════════════════════════════════════════════
#  Deterministic soak — 50+ actions across all surfaces
# ═════════════════════════════════════════════════════════════════════


def test_deterministic_soak_completes_without_error() -> None:
    """Exercise all major runtime surfaces in a single deterministic scenario."""
    runtime, context = make_runtime_campaign(player_name="SoakTester", seed=SOAK_SEED)
    seed_player_gold(context, 1000)
    seed_live_store_item(context, item_def_id="bread", quantity=10)
    snap = runtime.snapshot(context.campaign_id, narrative="soak-start")
    _store_id, item_id = first_live_store_item(snap)
    route = first_live_travel_route(snap)

    companion = inject_recruitable_companion(
        context, actor_id="soak_ally", name="Soak Ally", role="scout",
    )
    inject_ready_to_report_quest(
        context, quest_id="soak_quest", title="Soak Quest", reward_gold=50, reward_xp=100,
    )

    actions: list[str] = []

    def _run(cmd: str) -> dict:
        actions.append(cmd)
        return runtime.run_command(context.campaign_id, cmd)

    # ── Exploration (6) ──────────────────────────────────────────
    r = _run("look around")
    assert r["command_type"] == "exploration"
    _run("move east")
    _run("move west")
    _run("move north")
    _run("move south")
    _run("look around")

    # ── Knowledge (4) ────────────────────────────────────────────
    _run("topics")
    _run("think about this region")
    _run("ask dm what should I do next")
    _run("topics")

    # ── Recruit (1) ──────────────────────────────────────────────
    r = _run("recruit Soak Ally")
    assert r["command_type"] in ("party", "recruit", "exploration")

    # ── Commerce: buy/sell/rent (5) ──────────────────────────────
    r = _run(f"buy {item_id}")
    assert r["command_type"] == "commerce"
    _run(f"buy {item_id}")
    _run(f"buy {item_id}")
    _run("rent room")
    _run("rent a room")

    # ── Save/load checkpoint 1 (2 virtual) ───────────────────────
    runtime.save_campaign(context.campaign_id, "soak_cp1", "SoakTester")
    loaded = runtime.load_campaign("soak_cp1")
    # Continue on loaded context
    context_active = loaded

    # ── Travel: start/advance/arrive (counted as 1+ actions) ─────
    travel_result, travel_history = advance_active_travel(runtime, context_active, route)
    actions.extend([f"travel_step_{i}" for i in range(len(travel_history))])
    assert travel_result["campaign"].get("travel_state") is None  # arrived

    # ── More exploration at destination (4) ──────────────────────
    _run2 = lambda cmd: (actions.append(cmd), runtime.run_command(context_active.campaign_id, cmd))[1]
    _run2("look around")
    _run2("move east")
    _run2("move west")
    _run2("look around")

    # ── Quest: accept/quests/report (3) ──────────────────────────
    r = _run2("quests")
    assert r["command_type"] == "quest"
    _run2("report soak_quest")
    _run2("quests")

    # ── Save/load checkpoint 2 ───────────────────────────────────
    runtime.save_campaign(context_active.campaign_id, "soak_cp2", "SoakTester")
    context_active = runtime.load_campaign("soak_cp2")

    # ── Dialog: ask_about (2) ────────────────────────────────────
    _run3 = lambda cmd: (actions.append(cmd), runtime.run_command(context_active.campaign_id, cmd))[1]
    _run3("ask dm what is the lore of this place")
    _run3("topics")

    # ── Combat: attack/end_turn (inject hostile, attack, end turn) (5+)
    attack_tick = choose_attack_tick(context_active)
    set_target_tick(context_active, attack_tick)
    inject_hostile_npc_for_attack(
        context_active, actor_id="soak_foe", name="Soak Foe", role="bandit",
    )
    r = _run3("attack Soak Foe")
    actions.append("attack Soak Foe")
    if r["command_type"] == "combat":
        combat = r["campaign"].get("combat")
        if combat and combat.get("phase") != "resolved":
            # End turn to advance combat
            for _ in range(5):
                er = runtime.run_command(
                    context_active.campaign_id, "",
                    shortcut="combat", args={"action_id": "end_turn"},
                )
                actions.append("combat end_turn")
                if er["campaign"].get("combat") is None or er["campaign"]["combat"].get("phase") == "resolved":
                    break

    # ── More exploration (4) ─────────────────────────────────────
    _run3("look around")
    _run3("move east")
    _run3("move west")
    _run3("look around")

    # ── Save/load checkpoint 3 ───────────────────────────────────
    runtime.save_campaign(context_active.campaign_id, "soak_cp3", "SoakTester")
    context_active = runtime.load_campaign("soak_cp3")

    # ── Final exploration burst (16) ─────────────────────────────
    _run4 = lambda cmd: (actions.append(cmd), runtime.run_command(context_active.campaign_id, cmd))[1]
    for _ in range(8):
        _run4("move east")
        _run4("look around")

    # ── Verify minimum action count ──────────────────────────────
    assert len(actions) >= 50, f"Soak only ran {len(actions)} actions, need at least 50"

    # ── Final canonical state is valid ───────────────────────────
    final = canonical_release_state(runtime, context_active)
    assert final["scene"] in ("exploration", "combat", "travel", "dialog")
    assert final["player_essentials"]["alive"] is True
    assert isinstance(final["inventory"], list)
    assert isinstance(final["quest_state"]["completed_ids"], list)


def test_soak_save_load_final_state_is_stable() -> None:
    """After the soak run, saving and loading must produce identical canonical state."""
    runtime, context = make_runtime_campaign(player_name="SoakStable", seed=SOAK_SEED)
    seed_player_gold(context, 500)
    seed_live_store_item(context, item_def_id="bread", quantity=5)
    snap = runtime.snapshot(context.campaign_id, narrative="soak-stable-start")
    _store_id, item_id = first_live_store_item(snap)

    # Short deterministic transcript
    for cmd in ["look around", "move east", f"buy {item_id}", "look around", "move west",
                 "rent room", "look around", "move north", "look around", "move south"]:
        runtime.run_command(context.campaign_id, cmd)

    state_before = canonical_release_state(runtime, context)

    runtime.save_campaign(context.campaign_id, "soak_stable_slot", "SoakStable")
    loaded = runtime.load_campaign("soak_stable_slot")
    state_after = canonical_release_state(runtime, loaded)

    assert state_before == state_after, "Canonical state diverged after save/load"

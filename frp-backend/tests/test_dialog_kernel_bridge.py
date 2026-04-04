"""Tests for the kernel dialog bridge in campaign/dialog.py."""
from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.dialog import build_dialog_payload
from engine.api.campaign_commands import maybe_handle_dialog_command, maybe_handle_talk_command
from engine.kernel.dialog import (
    DialogAction,
    DialogDef, DialogStateNode, DialogTransition, DialogCondition,
    start_dialog,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign():
    rt = CampaignRuntime()
    ctx = rt.create_campaign(player_name="DialogTest", seed=42)
    return rt, ctx


def _inject_npc(ctx, actor_id: str, display_name: str):
    """Inject a minimal NPC ActorRecord into kernel runtime for dialog tests."""
    player = ctx.kernel_runtime["actors"]["player"]
    from engine.kernel.actor_records import ActorRecord
    from engine.kernel.actor import ActorIdentity, ActorPosition
    npc = ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=display_name, actor_type="npc"),
        position=ActorPosition(x=0, y=0),
        action_points=3, max_action_points=3, alive=True,
        stats=dict(player.stats), skills={}, raw_payload={"role": "guard"},
    )
    ctx.kernel_runtime["actors"][actor_id] = npc
    return npc


def _inject_dialog(ctx, dialog_def: DialogDef):
    runtime = ctx.kernel_runtime
    runtime.setdefault("dialog_defs", {})[dialog_def.dialog_id] = dialog_def
    from engine.data._shared import dialog_defs_registry

    registry = dialog_defs_registry()
    registry[dialog_def.dialog_id] = dialog_def.to_dict()


def _mock_actor(name="TestNPC", stats=None):
    from engine.kernel.actor_records import ActorRecord
    from engine.kernel.actor_foundation import ActorIdentity, ActorPosition
    default_stats = {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10}
    merged = {**default_stats, **(stats or {})}
    return ActorRecord(
        identity=ActorIdentity(actor_id=name.lower().replace(" ", "_"), display_name=name, actor_type="npc"),
        position=ActorPosition(x=0, y=0),
        action_points=3, max_action_points=3, alive=True,
        stats=merged, skills={}, raw_payload={},
    )


# ---------------------------------------------------------------------------
# Authored dialog resolution
# ---------------------------------------------------------------------------

class TestAuthoredDialogResolution:
    def test_returns_empty_when_no_authored_dialog_exists(self):
        _, ctx = _make_campaign()
        _inject_npc(ctx, "test_unknown", "Unknowner")
        ctx.kernel_runtime["actors"]["test_unknown"].raw_payload["role"] = "unwritten_role"
        ctx.conversation_state = {
            "target_type": "npc",
            "npc_id": "test_unknown",
            "npc_name": "Unknowner",
        }

        result = build_dialog_payload(ctx, "The stranger stares silently.")

        assert result == {}


# ---------------------------------------------------------------------------
# Kernel dialog start_dialog
# ---------------------------------------------------------------------------

class TestKernelDialogIntegration:
    def test_start_dialog_returns_state(self):
        player = _mock_actor("Player", {"MIG": 14, "AGI": 12, "INS": 14, "PRE": 14})
        npc = _mock_actor("Guard", {"MIG": 10})
        dialog_def = DialogDef(
            dialog_id="test_dialog", npc_id="guard_1",
            states=[DialogStateNode(
                state_id="start", text="Guard speaks.",
                transitions=[
                    DialogTransition(transition_id="greet", text="Hello", terminates=True),
                    DialogTransition(
                        transition_id="bribe", text="Offer gold",
                        condition=DialogCondition("stat_check", {"stat": "PRE", "operator": ">=", "value": 12}),
                        terminates=True,
                    ),
                ],
            )],
        )
        state, node, transitions = start_dialog(dialog_def, npc, player, {})
        assert state.active
        assert node.state_id == "start"
        assert len(transitions) == 2  # both available (PRE >= 12)

    def test_stat_check_blocks_transition(self):
        player = _mock_actor("Player", {"PRE": 8})
        npc = _mock_actor("Guard")
        dialog_def = DialogDef(
            dialog_id="test", npc_id="guard",
            states=[DialogStateNode(
                state_id="start", text="Guard.",
                transitions=[
                    DialogTransition(transition_id="greet", text="Hello", terminates=True),
                    DialogTransition(
                        transition_id="charm", text="Charm",
                        condition=DialogCondition("stat_check", {"stat": "PRE", "operator": ">=", "value": 12}),
                        terminates=True,
                    ),
                ],
            )],
        )
        state, node, transitions = start_dialog(dialog_def, npc, player, {})
        assert len(transitions) == 1  # charm blocked


# ---------------------------------------------------------------------------
# build_dialog_payload integration
# ---------------------------------------------------------------------------

class TestBuildDialogPayload:
    def test_returns_empty_when_not_talking(self):
        _, ctx = _make_campaign()
        result = build_dialog_payload(ctx, "You look around.")
        assert result == {}

    def test_returns_dialog_when_talking_to_npc(self):
        _, ctx = _make_campaign()
        _inject_npc(ctx, "test_guard", "Guard")
        ctx.conversation_state = {
            "target_type": "npc",
            "npc_id": "test_guard",
            "npc_name": "Guard",
        }
        result = build_dialog_payload(ctx, "The guard looks at you.")
        assert "dialog_npc" in result
        assert "dialog_options" in result
        assert len(result["dialog_options"]) >= 2

    def test_options_have_required_fields(self):
        _, ctx = _make_campaign()
        _inject_npc(ctx, "test_merchant", "Merchant")
        ctx.conversation_state = {
            "target_type": "npc", "npc_id": "test_merchant", "npc_name": "Merchant",
        }
        result = build_dialog_payload(ctx, "Hello.")
        assert result["dialog_options"]
        for opt in result.get("dialog_options", []):
            assert "text" in opt
            assert "command" in opt
            assert "available" in opt
            assert "enabled" in opt
            assert opt["command"].startswith("dialog ")


def test_talk_dialog_transition_starts_quest_and_adds_journal_entry():
    _, ctx = _make_campaign()
    _inject_npc(ctx, "quest_guard", "Quest Guard")
    ctx.quest_offers = [{
        "id": "guard_patrol",
        "quest_id": "guard_patrol",
        "title": "Guard Patrol",
        "description": "Speak to the captain.",
        "objectives": [{"type": "talk", "target_id": "quest_guard", "required": 1}],
    }]
    ctx.campaign_state["quest_offers"] = list(ctx.quest_offers)
    dialog_def = DialogDef(
        dialog_id="quest_guard",
        npc_id="quest_guard",
        states=[
            DialogStateNode(
                state_id="start",
                text="Will you help us?",
                transitions=[
                    DialogTransition(
                        transition_id="accept",
                        text="I will help.",
                        terminates=True,
                        actions=[
                            DialogAction("start_quest", {"quest_id": "guard_patrol"}),
                            DialogAction("add_journal", {"text": "Captain Rhea asked for help.", "quest_id": "guard_patrol"}),
                        ],
                    )
                ],
            )
        ],
    )
    _inject_dialog(ctx, dialog_def)

    talk_result = maybe_handle_talk_command(ctx, "talk quest_guard")
    assert talk_result is not None
    ctx.kernel_runtime["dialog_state"], _, _ = start_dialog(
        dialog_def,
        ctx.kernel_runtime["actors"]["quest_guard"],
        ctx.kernel_runtime["actors"]["player"],
        {},
    )
    ctx.kernel_runtime["dialog_npc_id"] = "quest_guard"
    ctx.kernel_runtime.setdefault("dialog_defs", {})[dialog_def.dialog_id] = dialog_def

    result = maybe_handle_dialog_command(ctx, "dialog accept")

    assert result is not None
    assert "conversation ends" in result[0].lower()
    quest = ctx.campaign_state["active_quests"][0]
    assert quest["quest_id"] == "guard_patrol"
    assert quest["stage"] == "started"
    assert any(entry.quest_id == "guard_patrol" and "Accepted quest" in entry.text for entry in ctx.kernel_runtime["game_state"].journal)
    assert any(entry.quest_id == "guard_patrol" and "Captain Rhea asked for help." in entry.text for entry in ctx.kernel_runtime["game_state"].journal)


def test_dialog_advance_quest_updates_active_stage_and_objective_state():
    _, ctx = _make_campaign()
    _inject_npc(ctx, "captain_rhea", "Captain Rhea")
    ctx.quest_offers = [{
        "id": "wolves_at_gate",
        "quest_id": "wolves_at_gate",
        "title": "Wolves at the Gate",
        "objectives": [{"type": "talk", "target_id": "captain_rhea", "required": 1}],
    }]
    ctx.campaign_state["quest_offers"] = list(ctx.quest_offers)
    ctx.campaign_state["active_quests"] = []
    from engine.api.campaign.quest_bridge import start_quest, sync_runtime_objectives

    start_quest(ctx, "wolves_at_gate")
    ctx.conversation_state = {"target_type": "npc", "npc_id": "captain_rhea", "npc_name": "Captain Rhea"}
    sync_runtime_objectives(ctx)

    dialog_def = DialogDef(
        dialog_id="captain_rhea",
        npc_id="captain_rhea",
        states=[
            DialogStateNode(
                state_id="start",
                text="Have you dealt with the wolves?",
                transitions=[
                    DialogTransition(
                        transition_id="advance",
                        text="The road is clear.",
                        terminates=True,
                        actions=[DialogAction("advance_quest", {"quest_id": "wolves_at_gate", "stage": "return_to_captain"})],
                    )
                ],
            )
        ],
    )
    _inject_dialog(ctx, dialog_def)
    ctx.kernel_runtime["dialog_state"], _, _ = start_dialog(dialog_def, ctx.kernel_runtime["actors"]["captain_rhea"], ctx.kernel_runtime["actors"]["player"], {})
    ctx.kernel_runtime["dialog_npc_id"] = "captain_rhea"

    result = maybe_handle_dialog_command(ctx, "dialog advance")

    assert result is not None
    active_quest = ctx.campaign_state["active_quests"][0]
    assert active_quest["stage"] == "return_to_captain"
    assert active_quest["objectives"][0]["progress"] == 1
    assert active_quest["objectives"][0]["completed"] is True


def test_sync_runtime_objectives_marks_kill_objective_complete_for_dead_target():
    _, ctx = _make_campaign()
    target = _inject_npc(ctx, "fallen_raider", "Fallen Raider")
    ctx.quest_offers = [{
        "id": "clear_raiders",
        "quest_id": "clear_raiders",
        "title": "Clear Raiders",
        "objectives": [{"type": "kill", "target_id": "fallen_raider", "required": 1}],
    }]
    ctx.campaign_state["quest_offers"] = list(ctx.quest_offers)

    from engine.api.campaign.quest_bridge import start_quest, sync_runtime_objectives

    start_quest(ctx, "clear_raiders")
    target.alive = False
    sync_runtime_objectives(ctx)

    active_quest = ctx.campaign_state["active_quests"][0]
    assert active_quest["objectives"][0]["type"] == "kill"
    assert active_quest["objectives"][0]["progress"] == 1
    assert active_quest["objectives"][0]["completed"] is True
    assert active_quest["report_ready"] is True

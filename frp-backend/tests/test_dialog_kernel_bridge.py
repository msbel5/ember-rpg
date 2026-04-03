"""Tests for the kernel dialog bridge in campaign/dialog.py."""
from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.dialog import build_dialog_payload
from engine.kernel.dialog import (
    DialogDef, DialogStateNode, DialogTransition, DialogCondition,
    start_dialog,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign():
    rt = CampaignRuntime(llm=None)
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
        ctx.session.conversation_state = {
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
        ctx.session.conversation_state = {
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
        ctx.session.conversation_state = {
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

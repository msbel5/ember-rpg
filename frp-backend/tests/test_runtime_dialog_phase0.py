from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
def _make_campaign():
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="DialogRuntime", seed=42)
    return runtime, context


def _inject_npc(context, actor_id: str, display_name: str):
    from engine.kernel.actor import ActorIdentity, ActorPosition
    from engine.kernel.actor_records import ActorRecord

    player = context.kernel_runtime["actors"]["player"]
    npc = ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=display_name, actor_type="npc"),
        position=ActorPosition(x=int(context.position[0]), y=int(context.position[1])),
        action_points=3,
        max_action_points=3,
        alive=True,
        stats=dict(player.stats),
        skills={},
        raw_payload={"role": "guard"},
    )
    context.kernel_runtime["actors"][actor_id] = npc
    return npc
def test_active_dialog_blocks_non_dialog_commands_until_terminate() -> None:
    runtime, context = _make_campaign()
    _inject_npc(context, "phase_zero_sentinel", "Phase Zero Sentinel")

    talk = runtime.run_command(context.campaign_id, "talk Phase Zero Sentinel")
    blocked_rest = runtime.run_command(context.campaign_id, "rest")
    blocked_move = runtime.run_command(context.campaign_id, "move north")
    continued = runtime.run_command(context.campaign_id, "dialog ask_work_guard")
    terminated = runtime.run_command(context.campaign_id, "dialog guard_info_done")
    resumed = runtime.run_command(context.campaign_id, "rest")

    assert talk["command_type"] == "dialog"
    assert talk["dialog_options"]
    assert blocked_rest["command_type"] == "dialog"
    assert "choose a dialog option" in blocked_rest["narrative"].lower()
    assert blocked_rest["hours_advanced"] == 0
    assert blocked_rest["dialog_options"]
    assert blocked_move["command_type"] == "dialog"
    assert "choose a dialog option" in blocked_move["narrative"].lower()
    assert blocked_move["hours_advanced"] == 0
    assert continued["command_type"] == "dialog"
    assert "wolves" in continued["narrative"].lower()
    assert terminated["command_type"] == "dialog"
    assert "conversation ends" in terminated["narrative"].lower()
    assert resumed["command_type"] == "rest"
    assert resumed["hours_advanced"] > 0

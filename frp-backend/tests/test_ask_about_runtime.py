from __future__ import annotations

import pytest

from engine.api.campaign.knowledge import discover_topics
from engine.api.campaign.runtime import CampaignRuntime
from engine.data._shared import dialog_defs_registry
from engine.kernel.actor import ActorIdentity, ActorPosition
from engine.kernel.actor_records import ActorRecord
from engine.kernel.dialog import DialogDef, DialogStateNode, DialogTransition, start_dialog
from engine.world.rumors import RumorNetwork


def _make_campaign(seed: int = 42) -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="AskAboutTester", seed=seed)
    return runtime, context


def _inject_npc(context, actor_id: str, display_name: str, *, role: str = "guard", faction_id: str = ""):
    player = context.kernel_runtime["actors"]["player"]
    actor = ActorRecord(
        identity=ActorIdentity(
            actor_id=actor_id,
            display_name=display_name,
            actor_type="npc",
            faction_id=faction_id or None,
        ),
        position=ActorPosition(x=0, y=0),
        action_points=3,
        max_action_points=3,
        alive=True,
        stats=dict(player.stats),
        skills={},
        raw_payload={
            "role": role,
            "template": role,
            "memory_id": actor_id,
            "faction_id": faction_id,
            "relationship_score": 0,
        },
    )
    context.kernel_runtime["actors"][actor_id] = actor
    return actor


def _activate_dialog(context, actor_id: str, display_name: str):
    actor = _inject_npc(context, actor_id, display_name)
    dialog_def = DialogDef(
        dialog_id=actor_id,
        npc_id=actor_id,
        states=[
            DialogStateNode(
                state_id="start",
                text=f"{display_name} waits.",
                transitions=[DialogTransition(transition_id="leave", text="Leave", terminates=True)],
            )
        ],
    )
    dialog_defs_registry()[actor_id] = dialog_def.to_dict()
    context.conversation_state = {
        "target_type": "npc",
        "npc_id": actor_id,
        "npc_name": display_name,
        "ask_about": {},
    }
    dialog_state, _, _ = start_dialog(
        dialog_def,
        actor,
        context.kernel_runtime["actors"]["player"],
        {},
    )
    context.kernel_runtime["dialog_state"] = dialog_state
    context.kernel_runtime["dialog_npc_id"] = actor_id
    context.kernel_runtime.setdefault("dialog_defs", {})[dialog_def.dialog_id] = dialog_def
    return actor


def test_raw_ask_about_returns_fact_from_npc_memory() -> None:
    runtime, context = _make_campaign()
    _activate_dialog(context, "fact_keeper", "Fact Keeper")
    memory = context.npc_memory.get_memory("fact_keeper", "Fact Keeper")
    memory.add_known_fact("Bandits watch the old road")
    discover_topics(context, ["fact.bandits_watch_the_old_road"])

    result = runtime.run_command(context.campaign_id, "ask about fact.bandits_watch_the_old_road")

    assert result["command_type"] == "dialog"
    assert result["knowledge_view"]["ask_about"]["response_type"] == "fact"
    assert result["knowledge_view"]["ask_about"]["topic"]["topic_id"] == "fact.bandits_watch_the_old_road"
    assert "Bandits watch the old road" in result["knowledge_view"]["ask_about"]["facts"]
    assert result["campaign"]["conversation_state"]["ask_about"]["response_type"] == "fact"


def test_raw_ask_about_resolves_alias_and_returns_rumor() -> None:
    runtime, context = _make_campaign()
    _activate_dialog(context, "rumor_keeper", "Rumor Keeper")
    rumor_network = context.rumor_network or RumorNetwork()
    context.rumor_network = rumor_network
    rumor = rumor_network.add_rumor("Ferry lights go dark before raids", "dockhand", "river_gate")
    rumor.heard_by.add("rumor_keeper")
    discover_topics(context, [f"rumor.{rumor.rumor_id}"])

    result = runtime.run_command(context.campaign_id, "ask about Ferry lights go dark before raids")

    assert result["command_type"] == "dialog"
    assert result["knowledge_view"]["ask_about"]["response_type"] == "rumor"
    assert result["knowledge_view"]["ask_about"]["topic"]["topic_id"] == f"rumor.{rumor.rumor_id}"
    assert "Ferry lights go dark before raids" in result["knowledge_view"]["ask_about"]["rumors"]


def test_structured_ask_about_redirects_when_npc_lacks_direct_topic_knowledge() -> None:
    runtime, context = _make_campaign()
    _activate_dialog(context, "guide_keeper", "Guide Keeper")
    discover_topics(context, ["quest.secret_mission"])

    result = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="dialog",
        args={"action_id": "ask_about", "topic_id": "quest.secret_mission"},
    )

    assert result["command_type"] == "dialog"
    assert result["knowledge_view"]["ask_about"]["response_type"] == "redirect"
    assert result["knowledge_view"]["ask_about"]["topic"]["topic_id"] == "quest.secret_mission"
    assert result["knowledge_view"]["ask_about"]["redirect_topic_ids"]
    assert "quest.secret_mission" not in result["knowledge_view"]["ask_about"]["redirect_topic_ids"]


def test_ask_about_rejects_undiscovered_topics_without_leaking_facts() -> None:
    runtime, context = _make_campaign()
    _activate_dialog(context, "quiet_keeper", "Quiet Keeper")
    memory = context.npc_memory.get_memory("quiet_keeper", "Quiet Keeper")
    memory.add_known_fact("A hidden cache sits below the east wall")

    result = runtime.run_command(context.campaign_id, "ask about fact.a_hidden_cache_sits_below_the_east_wall")

    assert result["command_type"] == "dialog"
    assert "have not discovered" in result["narrative"].lower()
    assert result["knowledge_view"]["blockers"] == ["undiscovered_topic"]
    assert result["knowledge_view"]["ask_about"]["response_type"] == "refusal"
    assert result["knowledge_view"]["ask_about"]["refusal_reason"] == "undiscovered_topic"
    assert result["knowledge_view"]["ask_about"]["facts"] == []
    assert result["knowledge_view"]["ask_about"]["rumors"] == []

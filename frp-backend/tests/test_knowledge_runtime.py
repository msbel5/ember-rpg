from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.world.rumors import RumorNetwork


def _make_campaign(seed: int = 42) -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="KnowledgeRunner", seed=seed)
    return runtime, context


def _knowledge_topic(payload: dict, topic_id: str) -> dict:
    return next(topic for topic in payload["campaign"]["knowledge"]["topics"] if topic["topic_id"] == topic_id)


def _current_region_topic(payload: dict) -> dict:
    region_id = payload["campaign"]["world"]["active_region_id"]
    return _knowledge_topic(payload, f"region.{region_id}")


def _first_travel_destination(payload: dict) -> dict:
    return next(option for option in payload["campaign"]["travel_options"] if not option.get("is_current"))


def test_topics_raw_and_structured_commands_return_knowledge_payload() -> None:
    runtime, context = _make_campaign()

    raw = runtime.run_command(context.campaign_id, "topics")
    structured = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="knowledge",
        args={"action_id": "topics"},
    )

    assert raw["command_type"] == "knowledge"
    assert structured["command_type"] == "knowledge"
    assert isinstance(raw["knowledge_view"]["topics"], list)
    assert isinstance(structured["knowledge_view"]["topics"], list)
    assert raw["campaign"]["knowledge"]["discovered_topic_ids"]


def test_think_resolves_exact_label_and_returns_grounded_region_rumors() -> None:
    runtime, context = _make_campaign(seed=77)
    rumor_network = context.rumor_network or RumorNetwork()
    context.rumor_network = rumor_network

    payload = runtime.snapshot(context.campaign_id, narrative="knowledge-seed")
    region_topic = _current_region_topic(payload)
    settlement_id = str(
        context.settlement_state.get("settlement_id")
        or context.region_snapshot.metadata.get("settlement_id")
        or context.region_snapshot.region_id
    ).strip()
    rumor_network.add_rumor("Bandits watch the old road", "town_crier", settlement_id)

    result = runtime.run_command(context.campaign_id, f"think {region_topic['label']}")

    assert result["command_type"] == "knowledge"
    assert result["knowledge_view"]["topic"]["topic_id"] == region_topic["topic_id"]
    assert "Bandits watch the old road" in result["knowledge_view"]["rumors"]
    assert isinstance(result["knowledge_view"]["facts"], list)


def test_pin_is_idempotent_for_discovered_topics() -> None:
    runtime, context = _make_campaign(seed=91)
    payload = runtime.snapshot(context.campaign_id, narrative="pin-seed")
    region_topic = _current_region_topic(payload)

    first = runtime.run_command(context.campaign_id, f"pin {region_topic['label']}")
    second = runtime.run_command(context.campaign_id, f"pin {region_topic['topic_id']}")

    assert first["command_type"] == "knowledge"
    assert second["command_type"] == "knowledge"
    assert first["knowledge_view"]["pinned"] is True
    assert second["knowledge_view"]["pinned"] is True
    assert "already pinned" in second["narrative"].lower()
    assert region_topic["topic_id"] in context.kernel_runtime["game_state"].raw_payload["knowledge"]["pinned_topic_ids"]


def test_travel_start_discovers_destination_topics() -> None:
    runtime, context = _make_campaign(seed=123)
    payload = runtime.snapshot(context.campaign_id, narrative="travel-knowledge")
    destination = _first_travel_destination(payload)

    result = runtime.run_command(
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

    discovered = set(result["campaign"]["knowledge"]["discovered_topic_ids"])
    assert f"region.{destination['destination_region_id']}" in discovered
    if destination.get("destination_settlement_id"):
        assert f"settlement.{destination['destination_settlement_id']}" in discovered


def test_talk_discovers_npc_topic_when_dialog_opens() -> None:
    runtime, context = _make_campaign(seed=42)
    payload = runtime.snapshot(context.campaign_id, narrative="talk-knowledge-seed")
    talkables = [
        entity
        for entity in payload["campaign"]["world_entities"]
        if entity.get("entity_type") == "npc" and "talk" in entity.get("context_actions", [])
    ]
    for talkable in talkables:
        target_name = str(talkable["name"])
        target_position = talkable["position"]
        move_x = max(0, int(target_position[0]) - 3)
        move_y = int(target_position[1])
        runtime.run_command(context.campaign_id, f"move to {move_x},{move_y}")
        result = runtime.run_command(context.campaign_id, f"talk {target_name}")
        if result["command_type"] != "dialog" or result.get("dialog_npc") != target_name:
            continue
        actor_id = str(result["campaign"]["conversation_state"]["npc_id"])
        assert f"npc.{actor_id}" in result["campaign"]["knowledge"]["discovered_topic_ids"]
        break
    else:
        pytest.skip("No authored dialog opening available for talkable NPCs in this seed")

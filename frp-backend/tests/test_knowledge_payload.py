from __future__ import annotations

import copy

from engine.api.campaign.runtime import CampaignRuntime


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="KnowledgeTester", seed=77)
    return runtime, context


def test_campaign_knowledge_payload_is_deterministic_and_survives_save_load() -> None:
    runtime, context = _make_campaign()
    world = context.world
    region_id = str(context.region_snapshot.region_id)
    settlement_id = str(
        context.settlement_state.get("settlement_id")
        or context.region_snapshot.metadata.get("settlement_id")
        or ""
    ).strip()
    faction_id = str(world.factions[0].id).strip() if world.factions else "alliance"

    discovered_topic_ids = [f"region.{region_id}", f"faction.{faction_id}"]
    pinned_topic_ids = [f"region.{region_id}"]
    if settlement_id and settlement_id != region_id:
        discovered_topic_ids.append(f"settlement.{settlement_id}")

    context.kernel_runtime["game_state"].raw_payload["knowledge"] = {
        "discovered_topic_ids": list(discovered_topic_ids),
        "pinned_topic_ids": list(pinned_topic_ids),
        "topics": [{"topic_id": "stale"}],
        "facts": ["stale"],
    }

    first = runtime.snapshot(context.campaign_id, narrative="knowledge-a")["campaign"]["knowledge"]
    second = runtime.snapshot(context.campaign_id, narrative="knowledge-b")["campaign"]["knowledge"]

    runtime.save_campaign(context.campaign_id, "knowledge_payload_slot", "KnowledgeTester")
    loaded = runtime.load_campaign("knowledge_payload_slot")
    loaded_raw = loaded.kernel_runtime["game_state"].raw_payload["knowledge"]
    after = runtime.snapshot(loaded.campaign_id, narrative="knowledge-loaded")["campaign"]["knowledge"]

    assert first == second == after
    assert list(loaded_raw.keys()) == ["discovered_topic_ids", "pinned_topic_ids"]
    assert loaded_raw == {
        "discovered_topic_ids": discovered_topic_ids,
        "pinned_topic_ids": pinned_topic_ids,
    }
    assert set(discovered_topic_ids).issubset(set(first["discovered_topic_ids"]))
    assert set(pinned_topic_ids).issubset(set(first["pinned_topic_ids"]))

    required_keys = {"topic_id", "label", "category", "discovered", "pinned", "source_types"}
    topic_map = {topic["topic_id"]: topic for topic in first["topics"]}
    assert required_keys.issubset(topic_map[f"region.{region_id}"].keys())
    assert topic_map[f"region.{region_id}"]["category"] == "region"
    assert topic_map[f"region.{region_id}"]["discovered"] is True
    assert topic_map[f"region.{region_id}"]["pinned"] is True
    assert topic_map[f"faction.{faction_id}"]["category"] == "faction"
    assert topic_map[f"faction.{faction_id}"]["discovered"] is True
    assert isinstance(topic_map[f"faction.{faction_id}"]["source_types"], list)
    if settlement_id and settlement_id != region_id:
        assert topic_map[f"settlement.{settlement_id}"]["category"] == "settlement"
        assert topic_map[f"settlement.{settlement_id}"]["discovered"] is True


def test_discovered_topic_ids_order_survives_save_load() -> None:
    runtime, context = _make_campaign()
    authored_ids = ["custom.alpha", "custom.beta", "custom.gamma", "custom.delta"]

    context.kernel_runtime["game_state"].raw_payload["knowledge"] = {
        "discovered_topic_ids": list(authored_ids),
        "pinned_topic_ids": [],
        "topics": [{"topic_id": "derived_should_die"}],
    }

    runtime.save_campaign(context.campaign_id, "order_test_slot", "KnowledgeTester")
    loaded = runtime.load_campaign("order_test_slot")
    loaded_raw = loaded.kernel_runtime["game_state"].raw_payload["knowledge"]

    assert list(loaded_raw.keys()) == ["discovered_topic_ids", "pinned_topic_ids"]
    assert loaded_raw["discovered_topic_ids"] == authored_ids
    assert loaded_raw["pinned_topic_ids"] == []
    assert "topics" not in loaded_raw


def test_pinned_topic_ids_order_survives_save_load() -> None:
    runtime, context = _make_campaign()
    authored_discovered = ["custom.gamma", "custom.beta", "custom.alpha"]
    authored_pins = ["custom.gamma", "custom.alpha"]

    context.kernel_runtime["game_state"].raw_payload["knowledge"] = {
        "discovered_topic_ids": list(authored_discovered),
        "pinned_topic_ids": list(authored_pins),
        "facts": ["derived_should_die"],
    }

    runtime.save_campaign(context.campaign_id, "pin_order_slot", "KnowledgeTester")
    loaded = runtime.load_campaign("pin_order_slot")
    loaded_raw = loaded.kernel_runtime["game_state"].raw_payload["knowledge"]

    assert list(loaded_raw.keys()) == ["discovered_topic_ids", "pinned_topic_ids"]
    assert loaded_raw["discovered_topic_ids"] == authored_discovered
    assert loaded_raw["pinned_topic_ids"] == authored_pins
    assert "facts" not in loaded_raw


def test_advisor_residue_sanitization_does_not_mutate_knowledge_raw_owner() -> None:
    runtime, context = _make_campaign()
    authored_discovered = ["custom.alpha", "custom.beta", "custom.gamma"]
    authored_pins = ["custom.gamma", "custom.alpha"]

    context.kernel_runtime["game_state"].raw_payload["knowledge"] = {
        "discovered_topic_ids": list(authored_discovered),
        "pinned_topic_ids": list(authored_pins),
    }
    before = copy.deepcopy(context.kernel_runtime["game_state"].raw_payload["knowledge"])
    context.kernel_runtime["game_state"].raw_payload["advisor"] = {"leak": True}
    context.kernel_runtime["game_state"].raw_payload["advisor_view"] = {"leak": True}

    snapshot = runtime.snapshot(context.campaign_id, narrative="advisor-knowledge-cleanup")

    assert "advisor" not in snapshot["campaign"]
    assert "advisor_view" not in snapshot["campaign"]
    assert context.kernel_runtime["game_state"].raw_payload["knowledge"] == before
    assert "advisor" not in context.kernel_runtime["game_state"].raw_payload
    assert "advisor_view" not in context.kernel_runtime["game_state"].raw_payload
    assert list(context.kernel_runtime["game_state"].raw_payload["knowledge"].keys()) == [
        "discovered_topic_ids",
        "pinned_topic_ids",
    ]

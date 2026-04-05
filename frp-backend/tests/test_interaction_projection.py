from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
from engine.world.entity import Entity, EntityType


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="ProjectionTester", seed=123)
    return runtime, context


def _inject_fixture(
    context,
    *,
    fixture_id: str,
    name: str,
    role: str,
    template: str,
    context_actions: list[str],
    offset: tuple[int, int] = (1, 0),
) -> None:
    x = int(context.position[0]) + int(offset[0])
    y = int(context.position[1]) + int(offset[1])
    entity = Entity(
        id=fixture_id,
        entity_type=EntityType.FURNITURE,
        name=name,
        position=(x, y),
        glyph="#",
        color="orange",
        blocking=False,
        hp=1,
        max_hp=1,
        disposition="neutral",
        job=role,
    )
    context.spatial_index.add(entity)
    context.entities[fixture_id] = {
        "name": name,
        "type": "furniture",
        "position": [x, y],
        "role": role,
        "template": template,
        "context_actions": list(context_actions),
        "entity_ref": entity,
    }


def _world_entity(payload: dict, entity_id: str) -> dict:
    return next(item for item in payload["campaign"]["world_entities"] if item["id"] == entity_id)


def test_projected_npc_payload_includes_interaction_descriptor_contract() -> None:
    runtime, context = _make_campaign()

    payload = runtime.snapshot(context.campaign_id, narrative="projection")
    npc = next(
        item
        for item in payload["campaign"]["world_entities"]
        if item["entity_type"] == "npc" and item.get("interaction_target_type") == "npc_friendly"
    )

    assert "id" in npc
    assert "name" in npc
    assert "position" in npc
    assert "role" in npc
    assert "context_actions" in npc
    assert npc["target_kind"] == "npc"
    assert npc["primary_interaction_id"] in {item["interaction_id"] for item in npc["available_interactions"]}
    talk = next(item for item in npc["available_interactions"] if item["interaction_id"] == "talk")
    assert set(talk) == {
        "id",
        "label",
        "interaction_id",
        "governing_check",
        "requirements",
        "ap_cost",
        "available",
        "blocked_reason",
    }


def test_live_workstation_payload_exposes_canonical_interactions() -> None:
    runtime, context = _make_campaign()
    _inject_fixture(
        context,
        fixture_id="projection_forge_fixture",
        name="Projection Forge",
        role="practice_forge",
        template="practice_forge",
        context_actions=["examine", "use"],
    )

    payload = runtime.snapshot(context.campaign_id, narrative="projection")
    forge = _world_entity(payload, "projection_forge_fixture")
    interaction_ids = [item["interaction_id"] for item in forge["available_interactions"]]

    assert forge["interaction_target_type"] == "workstation"
    assert forge["target_kind"] == "furniture"
    assert forge["context_actions"] == ["examine", "use"]
    assert "craft" in interaction_ids
    assert "use" in interaction_ids
    assert "examine" in interaction_ids


def test_unsupported_loose_action_hints_are_not_exposed_as_active_descriptors() -> None:
    runtime, context = _make_campaign()
    _inject_fixture(
        context,
        fixture_id="projection_loose_fixture",
        name="Loose Forge",
        role="loose_forge",
        template="loose_forge",
        context_actions=["examine", "use", "sit"],
    )

    payload = runtime.snapshot(context.campaign_id, narrative="projection")
    forge = _world_entity(payload, "projection_loose_fixture")

    assert forge["context_actions"] == ["examine", "use"]
    assert all(item["interaction_id"] != "sit" for item in forge["available_interactions"])
    assert forge["primary_interaction_id"] in {"examine", "use", "craft"}

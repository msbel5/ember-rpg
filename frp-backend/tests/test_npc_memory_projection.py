from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign_commands import maybe_handle_talk_command
from engine.kernel.dialog import compute_npc_reaction
from engine.kernel.actor_records import create_monster_actor
from engine.world.entity import Entity, EntityType


SOCIAL_KEYS = {
    "identity_source",
    "named_npc_id",
    "memory_id",
    "recruitable_companion",
    "relationship_score",
    "relationship_label",
    "reaction_score",
    "has_met_player",
    "last_interaction",
    "recent_conversation_count",
    "known_facts_count",
    "memory_summary",
}


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="MemoryProjection", seed=77)
    return runtime, context


def _world_entity(payload: dict, entity_id: str) -> dict:
    return next(item for item in payload["campaign"]["world_entities"] if item["id"] == entity_id)


def _inject_generated_social_npc(
    context,
    *,
    actor_id: str = "generated_social_test_npc",
    name: str = "Shift Watcher",
    role: str = "custom_social",
) -> str:
    actor = create_monster_actor(
        {
            "id": actor_id,
            "name": name,
            "type": "monster",
            "hp": 10,
            "armor_class": 10,
            "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10},
        },
        faction_id="settlers",
    )
    actor.identity.actor_type = "npc"
    actor.raw_payload["role"] = role
    actor.raw_payload["template"] = role
    actor.raw_payload["identity_source"] = "generated"
    actor.raw_payload["named_npc_id"] = None
    actor.raw_payload["memory_id"] = actor_id
    actor.raw_payload["relationship_score"] = 7
    actor.raw_payload["recruitable_companion"] = False
    context.kernel_runtime["actors"][actor_id] = actor

    x = int(context.position[0]) + 2
    y = int(context.position[1])
    entity = Entity(
        id=actor_id,
        entity_type=EntityType.NPC,
        name=name,
        position=(x, y),
        glyph="A",
        color="light_blue",
        blocking=True,
        hp=10,
        max_hp=10,
        disposition="friendly",
        attitude="friendly",
        faction="settlers",
        job=role,
    )
    if context.spatial_index.get_position(actor_id) is None:
        context.spatial_index.add(entity)
    context.entities[actor_id] = {
        "name": name,
        "type": "npc",
        "position": [x, y],
        "faction": "settlers",
        "role": role,
        "attitude": "friendly",
        "disposition": "friendly",
        "template": role,
        "context_actions": ["talk", "examine"],
        "entity_ref": entity,
    }
    return actor_id


def test_authored_social_npc_payload_exposes_compact_memory_contract() -> None:
    runtime, context = _make_campaign()

    payload = runtime.snapshot(context.campaign_id, narrative="projection")
    authored = next(
        item
        for item in payload["campaign"]["world_entities"]
        if item["entity_type"] == "npc" and item.get("identity_source") == "authored"
    )
    actor = context.kernel_runtime["actors"][authored["id"]]
    game_state = context.kernel_runtime["game_state"]
    reputation = int(getattr(game_state, "global_variables", {}).get("reputation", 0))

    assert SOCIAL_KEYS.issubset(authored.keys())
    assert authored["named_npc_id"]
    assert authored["memory_id"] == authored["named_npc_id"]
    assert authored["identity_source"] == "authored"
    assert authored["relationship_score"] == int(actor.raw_payload.get("relationship_score", 0))
    assert authored["recruitable_companion"] == bool(actor.raw_payload.get("recruitable_companion", False))
    assert authored["reaction_score"] == compute_npc_reaction(context.player, actor, reputation)


def test_generated_social_fallback_payload_uses_same_contract_shape() -> None:
    runtime, context = _make_campaign()
    actor_id = _inject_generated_social_npc(context)

    payload = runtime.snapshot(context.campaign_id, narrative="projection")
    npc = _world_entity(payload, actor_id)

    assert SOCIAL_KEYS.issubset(npc.keys())
    assert npc["identity_source"] == "generated"
    assert npc["named_npc_id"] is None
    assert npc["memory_id"] == actor_id
    assert npc["relationship_score"] == 7
    assert npc["relationship_label"] == "stranger"


def test_non_social_entities_do_not_expose_fake_social_fields() -> None:
    runtime, context = _make_campaign()

    payload = runtime.snapshot(context.campaign_id, narrative="projection")
    furniture = next(item for item in payload["campaign"]["world_entities"] if item["entity_type"] == "furniture")
    hostile = next(item for item in payload["campaign"]["world_entities"] if item["target_kind"] == "enemy")

    assert SOCIAL_KEYS.isdisjoint(furniture.keys())
    assert SOCIAL_KEYS.isdisjoint(hostile.keys())


def test_talk_refreshes_compact_memory_state() -> None:
    runtime, context = _make_campaign()
    actors = context.kernel_runtime["actors"]
    target_id = next(
        entity_id
        for entity_id, record in context.entities.items()
        if entity_id in actors and record.get("type") == "npc"
    )
    actor = actors[target_id]
    memory_id = str(actor.raw_payload.get("memory_id", "")).strip() or str(actor.raw_payload.get("named_npc_id", "")).strip() or target_id
    memory = context.npc_memory.get_memory(memory_id, actor.identity.display_name)
    memory.last_interaction = ""

    result = maybe_handle_talk_command(context, f"talk {target_id}")

    assert result is not None
    assert memory.last_interaction
    assert memory.npc_id == memory_id
    assert memory.relationship_label

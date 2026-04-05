"""Runtime bridge tests for authored NPC identity and memory binding."""

from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.live_kernel import ensure_kernel_runtime
from engine.worldgen.npc_generator import generate_npc_population, runtime_npc_state
from engine.worldgen.registries import load_named_npc_records


def _sample_buildings() -> list[dict[str, object]]:
    return [
        {"id": "temple_0", "kind": "temple", "x": 4, "y": 4, "width": 8, "height": 8, "npc_roles": ["priest"]},
        {"id": "guard_post_0", "kind": "guard_post", "x": 14, "y": 4, "width": 8, "height": 8, "npc_roles": ["guard", "guard"]},
        {"id": "market_stall_0", "kind": "market_stall", "x": 24, "y": 4, "width": 8, "height": 8, "npc_roles": ["merchant"]},
        {"id": "tavern_0", "kind": "tavern", "x": 34, "y": 4, "width": 8, "height": 8, "npc_roles": ["innkeeper", "bard"]},
        {"id": "blacksmith_0", "kind": "blacksmith", "x": 44, "y": 4, "width": 8, "height": 8, "npc_roles": ["smith"]},
        {"id": "dock_0", "kind": "dock", "x": 54, "y": 4, "width": 8, "height": 8, "npc_roles": ["fishmonger"]},
    ]


def test_named_npc_loader_exists_and_population_prefers_authored_records():
    authored = load_named_npc_records()
    assert len(authored) >= 100

    npcs = generate_npc_population(
        settlement_id="node_region_024_11",
        buildings=_sample_buildings(),
        center_feature={"x": 40, "y": 30},
        seed=42,
        population_hint=120,
    )
    repeat = generate_npc_population(
        settlement_id="node_region_024_11",
        buildings=_sample_buildings(),
        center_feature={"x": 40, "y": 30},
        seed=42,
        population_hint=120,
    )

    authored_spawns = [npc for npc in npcs if npc.get("identity_source") == "authored"]
    assert authored_spawns, "expected at least one authored NPC spawn"
    authored_ids = [str(npc.get("named_npc_id")) for npc in authored_spawns]
    assert all(authored_ids)
    assert len(authored_ids) == len(set(authored_ids)), "authored NPC ids must not repeat in one settlement"
    assert authored_ids == [
        str(npc.get("named_npc_id"))
        for npc in repeat
        if npc.get("identity_source") == "authored"
    ]
    assert all(npc.get("location_id") for npc in authored_spawns)

    fallback_spawns = [npc for npc in npcs if npc.get("role") == "fishmonger"]
    assert fallback_spawns, "expected fishmonger fallback spawns"
    assert all(npc.get("identity_source") == "generated" for npc in fallback_spawns)
    assert all(npc.get("named_npc_id") is None for npc in fallback_spawns)
    assert all(npc.get("memory_id") == npc["id"] for npc in fallback_spawns)

    runtime_state = runtime_npc_state(npcs, 12)
    runtime_authored = [npc for npc in runtime_state if npc.get("identity_source") == "authored"]
    assert runtime_authored
    assert {npc["named_npc_id"] for npc in runtime_authored} == set(authored_ids)


def test_live_runtime_stamps_social_identity_and_persists_through_save_load():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("MemoryTester", seed=42)

    ensure_kernel_runtime(context)
    actors = {
        actor_id: actor
        for actor_id, actor in context.kernel_runtime["actors"].items()
        if actor_id != "player" and getattr(getattr(actor, "identity", None), "actor_type", "") == "npc"
    }
    authored_actor = next(
        actor for actor in actors.values() if actor.raw_payload.get("identity_source") == "authored"
    )
    memory_id = str(authored_actor.raw_payload.get("memory_id"))
    named_npc_id = str(authored_actor.raw_payload.get("named_npc_id"))

    assert named_npc_id
    assert memory_id == named_npc_id
    assert context.npc_memory is not None
    assert memory_id in context.npc_memory.memories
    memory = context.npc_memory.memories[memory_id]
    assert memory.npc_id == memory_id
    assert memory.name == authored_actor.identity.display_name
    assert memory.relationship_score == int(authored_actor.raw_payload.get("relationship_score", 0))

    slot_name = "named_npc_bridge_slot"
    runtime.save_campaign(context.campaign_id, slot_name, "MemoryTester")
    loaded = runtime.load_campaign(slot_name)
    loaded_authored_actor = next(
        actor
        for actor_id, actor in loaded.kernel_runtime["actors"].items()
        if actor_id != "player"
        and getattr(getattr(actor, "identity", None), "actor_type", "") == "npc"
        and actor.raw_payload.get("identity_source") == "authored"
    )

    assert loaded_authored_actor.raw_payload.get("named_npc_id") == named_npc_id
    assert loaded_authored_actor.raw_payload.get("memory_id") == memory_id
    assert loaded_authored_actor.raw_payload.get("identity_source") == "authored"
    assert loaded.npc_memory is not None
    assert memory_id in loaded.npc_memory.memories
    loaded_memory = loaded.npc_memory.memories[memory_id]
    assert loaded_memory.npc_id == memory_id
    assert loaded_memory.name == loaded_authored_actor.identity.display_name

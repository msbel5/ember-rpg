from engine.api.campaign.persistence import campaign_payload
from engine.api.campaign.runtime import CampaignRuntime
from engine.worldgen import generate_settlement_layout, generate_world, seed_civilizations, seed_species, simulate_history
from engine.worldgen.npc_generator import runtime_npc_state


def _npc_world(seed: int = 42):
    return simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard"))))


def test_campaign_payload_surfaces_generated_layout_npcs_and_quests():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Settler", adapter_id="fantasy_ember", seed=42)

    payload = campaign_payload(context)
    npc_entities = [entity for entity in payload["world_entities"] if entity["entity_type"] == "npc"]
    furniture_entities = [entity for entity in payload["world_entities"] if entity["entity_type"] == "furniture"]

    assert len(payload["region"]["layout"]["buildings"]) >= 10
    assert len(npc_entities) >= 10
    assert len(furniture_entities) >= 10
    assert len(payload["quest_offers"]) >= 5
    assert payload["settlement"]["economy"]["prices"]
    assert payload["world"]["weather"]

    response = runtime.run_command(context.campaign_id, "look around")
    updated_npcs = [entity for entity in response["campaign"]["world_entities"] if entity["entity_type"] == "npc"]

    # look around returns hours_advanced=0, so generated_events may be empty.
    # The command itself should succeed and return the campaign state.
    assert "campaign" in response
    assert len(updated_npcs) >= 10


def test_generated_layout_bridges_authored_named_npcs_without_duplicate_reuse() -> None:
    world = _npc_world(77)
    layout = generate_settlement_layout(world, world.settlements[0].region_id)

    authored = [npc for npc in layout.npc_spawns if npc.get("identity_source") == "authored"]
    generated = [npc for npc in layout.npc_spawns if npc.get("identity_source") == "generated"]
    named_ids = [str(npc.get("named_npc_id", "")).strip() for npc in authored]

    assert authored
    assert generated
    assert all(named_ids)
    assert len(named_ids) == len(set(named_ids))
    assert all(npc.get("named_npc_id") is None for npc in generated)


def test_runtime_npc_state_preserves_authored_identity_metadata() -> None:
    world = _npc_world(91)
    layout = generate_settlement_layout(world, world.settlements[0].region_id)

    runtime_npcs = runtime_npc_state(layout.npc_spawns, 8)
    authored = next(npc for npc in runtime_npcs if npc.get("identity_source") == "authored")

    assert authored["named_npc_id"]
    assert authored["identity_source"] == "authored"
    assert authored["schedule"]
    assert isinstance(authored.get("personality", {}), dict)

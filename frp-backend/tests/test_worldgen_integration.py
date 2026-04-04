from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.persistence import campaign_payload


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

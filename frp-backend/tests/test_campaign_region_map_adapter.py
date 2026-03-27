from engine.api.campaign_state import build_world, map_payload_from_region
from engine.worldgen import realize_region


def test_campaign_region_maps_are_named_and_playable():
    world = build_world(adapter_id="fantasy_ember", profile_id="standard", seed=42)
    region_id = world.settlements[0].region_id
    region = realize_region(world, region_id)

    payload = map_payload_from_region(region)

    assert payload["width"] == 80
    assert payload["height"] == 60
    assert payload["metadata"]["map_type"] == "campaign_region"
    assert len(payload["tiles"]) == 60
    assert len(payload["tiles"][0]) == 80
    assert isinstance(payload["tiles"][0][0], str)
    assert payload["spawn_point"][0] >= 0
    assert payload["spawn_point"][1] >= 0

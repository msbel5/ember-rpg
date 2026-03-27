from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_campaign_snapshot_contains_godot_ready_map_and_settlement_payload():
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "GodotProbe",
            "player_class": "warrior",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": 42,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    campaign = payload["campaign"]

    assert campaign["map_data"]["metadata"]["map_type"] == "campaign_region"
    assert len(campaign["map_data"]["tiles"]) == 60
    assert len(campaign["map_data"]["tiles"][0]) == 80
    assert campaign["world_entities"]
    assert campaign["settlement"]["residents"]
    assert campaign["recent_event_log"]


def test_campaign_command_preserves_godot_payload_shape():
    create = client.post(
        "/game/campaigns",
        json={
            "player_name": "GodotProbe",
            "player_class": "rogue",
            "adapter_id": "scifi_frontier",
            "profile_id": "standard",
            "seed": 99,
        },
    ).json()
    campaign_id = create["campaign_id"]

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": "defend"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["campaign"]["settlement"]["defense_posture"] == "fortified"
    assert payload["campaign"]["map_data"]["metadata"]["region_id"]
    assert payload["campaign"]["world"]["adapter_id"] == "scifi_frontier"

"""Targeted tests for the campaign-first API."""

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def _create_campaign(adapter_id: str = "fantasy_ember") -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "CampaignTester",
            "player_class": "warrior",
            "adapter_id": adapter_id,
            "profile_id": "standard",
            "seed": 42,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_create_campaign_returns_campaign_snapshot():
    payload = _create_campaign()
    assert payload["adapter_id"] == "fantasy_ember"
    assert payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["settlement"]["residents"]
    assert payload["campaign"]["region"]["width"] == 80
    assert payload["campaign"]["region"]["height"] == 60


def test_create_scifi_campaign_returns_scifi_world_state():
    payload = _create_campaign("scifi_frontier")
    assert payload["adapter_id"] == "scifi_frontier"
    assert payload["campaign"]["world"]["adapter_id"] == "scifi_frontier"
    assert payload["campaign"]["settlement"]["adapter_id"] == "scifi_frontier"


def test_campaign_command_and_region_endpoints_work():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]
    command = client.post(f"/game/campaigns/{campaign_id}/commands", json={"input": "look around"})
    assert command.status_code == 200
    body = command.json()
    assert body["command_type"] == "avatar"
    assert body["campaign"]["recent_event_log"]

    region = client.get(f"/game/campaigns/{campaign_id}/region/current")
    assert region.status_code == 200
    region_payload = region.json()
    assert region_payload["metadata"]["explainability"]["terrain_driver"]

    settlement = client.get(f"/game/campaigns/{campaign_id}/settlement/current")
    assert settlement.status_code == 200
    assert settlement.json()["rooms"]


def test_campaign_save_and_load_round_trip():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]
    saved = client.post(
        f"/game/campaigns/{campaign_id}/save",
        json={"player_id": "CampaignTester", "slot_name": "campaign_v2_slot"},
    )
    assert saved.status_code == 200
    save_id = saved.json()["save_id"]

    saves = client.get(f"/game/campaigns/{campaign_id}/saves")
    assert saves.status_code == 200
    assert any(entry["save_id"] == save_id for entry in saves.json())

    loaded = client.post(f"/game/campaigns/load/{save_id}")
    assert loaded.status_code == 200
    loaded_payload = loaded.json()
    assert loaded_payload["campaign"]["world"]["seed"] == 42
    assert loaded_payload["campaign"]["settlement"]["name"]

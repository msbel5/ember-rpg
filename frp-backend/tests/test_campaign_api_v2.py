"""Targeted tests for the campaign-first API."""

from pathlib import Path

from fastapi.testclient import TestClient

from engine.api.campaign_runtime import CampaignRuntime
from engine.api.game_engine import GameEngine
from engine.api.save_routes import SaveManagerCompat
from engine.api import campaign_routes, save_routes
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


def test_campaign_save_listing_filters_legacy_and_other_campaign_slots(tmp_path: Path):
    runtime = CampaignRuntime(llm=None)
    runtime.save_system.save_dir = tmp_path / "campaign_api_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)
    old_runtime = campaign_routes.campaign_runtime
    old_save_manager = save_routes.save_manager
    campaign_routes.campaign_runtime = runtime
    save_routes.save_manager = SaveManagerCompat(save_system=runtime.save_system)
    try:
        first = client.post(
            "/game/campaigns",
            json={
                "player_name": "CampaignTester",
                "player_class": "warrior",
                "adapter_id": "fantasy_ember",
                "profile_id": "standard",
                "seed": 100,
            },
        ).json()
        second = client.post(
            "/game/campaigns",
            json={
                "player_name": "CampaignTester",
                "player_class": "rogue",
                "adapter_id": "scifi_frontier",
                "profile_id": "standard",
                "seed": 101,
            },
        ).json()
        first_id = first["campaign_id"]
        client.post(f"/game/campaigns/{first_id}/save", json={"player_id": "CampaignTester", "slot_name": "first_slot"})
        client.post(f"/game/campaigns/{second['campaign_id']}/save", json={"player_id": "CampaignTester", "slot_name": "second_slot"})
        legacy_session = GameEngine(llm=None).new_session("CampaignTester", "warrior", location="Harbor Town")
        runtime.save_system.save_game(legacy_session, "legacy_slot", player_name="CampaignTester")

        player_saves = client.get("/game/saves/CampaignTester")
        assert player_saves.status_code == 200
        player_entries = {entry["save_id"]: entry for entry in player_saves.json()}
        assert player_entries["first_slot"]["campaign_compatible"] is True
        assert player_entries["second_slot"]["campaign_compatible"] is True
        assert player_entries["legacy_slot"]["campaign_compatible"] is False

        detail = client.get("/game/saves/file/legacy_slot")
        assert detail.status_code == 200
        assert detail.json()["campaign_compatible"] is False

        scoped = client.get(f"/game/campaigns/{first_id}/saves")
        assert scoped.status_code == 200
        assert [entry["save_id"] for entry in scoped.json()] == ["first_slot"]
    finally:
        campaign_routes.campaign_runtime = old_runtime
        save_routes.save_manager = old_save_manager

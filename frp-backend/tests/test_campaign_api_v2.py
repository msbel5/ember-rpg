"""Targeted tests for the campaign-first API."""

import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from engine.api.campaign_runtime import CampaignRuntime
from engine.api import campaign_routes
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
    assert payload["campaign"]["world_state"]["active_region_id"]
    assert payload["campaign"]["game_state"]["campaign_id"] == payload["campaign_id"]
    assert payload["campaign"]["game_state"]["current_area_id"] == payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["game_state"]["actors"]["player"]["identity"]["actor_id"] == "player"
    assert payload["campaign"]["world_state"]["regions"]
    assert payload["campaign"]["actors"]
    assert payload["campaign"]["actors"][0]["identity"]["actor_id"] == "player"
    assert payload["campaign"]["jobs"]
    assert payload["campaign"]["reactions"]
    assert payload["campaign"]["worksites"]
    assert payload["campaign"]["colony_pressure"]["food"] >= 0
    assert "shortages" in payload["campaign"]["production_ledger"]
    assert payload["campaign"]["path_authority"]["active_region_id"]
    assert payload["campaign"]["local_map_state"]["region_id"] == payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["military"]["squads"]
    assert "power_network" in payload["campaign"]["systems"]
    assert "syndrome_registry" in payload["campaign"]["systems"]
    assert payload["campaign"]["world_graph"]["nodes"]
    assert payload["campaign"]["travel_options"]
    assert all(entry["route_id"] for entry in payload["campaign"]["travel_options"])
    assert all(entry["reachable"] is True for entry in payload["campaign"]["travel_options"])
    assert all("is_current" in entry for entry in payload["campaign"]["travel_options"])
    assert payload["campaign"]["current_region_summary"]["settlement_node_id"]
    assert payload["campaign"]["settlement"]["residents"]
    assert payload["campaign"]["region"]["width"] == 80
    assert payload["campaign"]["region"]["height"] == 60


def test_campaign_client_health_endpoint_reports_required_capabilities():
    response = client.get("/game/health/campaign-client")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "campaign_creation": True,
        "campaign_runtime": True,
        "campaign_save_load": True,
        "schema_version": "4.0",
    }


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
    assert body["command_type"] == "exploration"
    assert body["campaign"]["recent_event_log"]
    assert body["campaign"]["jobs"]
    assert "unrest" in body["campaign"]["colony_pressure"]
    assert body["campaign"]["path_authority"]["active_region_id"] == body["campaign"]["world"]["active_region_id"]
    assert body["campaign"]["systems"]["power_network"]["total_required"] >= 0

    region = client.get(f"/game/campaigns/{campaign_id}/region/current")
    assert region.status_code == 200
    region_payload = region.json()
    assert region_payload["metadata"]["explainability"]["terrain_driver"]

    settlement = client.get(f"/game/campaigns/{campaign_id}/settlement/current")
    assert settlement.status_code == 200
    assert settlement.json()["rooms"]


def test_campaign_talk_command_returns_dialog_payload_when_conversation_is_active():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]
    talkables = [
        entity
        for entity in payload["campaign"]["world_entities"]
        if entity.get("entity_type") == "npc" and "talk" in entity.get("context_actions", [])
    ]

    for talkable in talkables:
        target_name = str(talkable["name"])
        target_position = talkable["position"]
        move_x = max(0, int(target_position[0]) - 3)
        move_y = int(target_position[1])

        moved = client.post(f"/game/campaigns/{campaign_id}/commands", json={"input": f"move to {move_x},{move_y}"})
        assert moved.status_code == 200

        response = client.post(f"/game/campaigns/{campaign_id}/commands", json={"input": f"talk {target_name}"})
        assert response.status_code == 200
        body = response.json()
        if body.get("dialog_npc") != target_name:
            continue

        assert body.get("dialog_text")
        assert body.get("dialog_options")
        assert all(opt["command"].startswith("dialog ") for opt in body["dialog_options"])
        assert all("enabled" in option for option in body["dialog_options"])
        assert all("disabled_reason" in option for option in body["dialog_options"])
        assert any("skill_check" in option for option in body["dialog_options"])
        break
    else:
        pytest.skip("No authored dialog available for talkable NPCs in this campaign seed")


def test_campaign_attack_command_marks_scene_as_combat_when_combat_payload_exists():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]

    # Find an actual NPC to attack (campaign-native, no enemy spawning).
    npcs = [
        actor for actor in payload["campaign"]["actors"]
        if actor["identity"]["actor_id"] != "player"
        and actor["identity"].get("actor_type") == "npc"
        and actor.get("alive", True)
    ]
    if not npcs:
        pytest.skip("No NPCs in fresh campaign to attack")
    target_name = npcs[0]["identity"]["display_name"]

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"attack {target_name}"},
    )
    assert response.status_code == 200
    body = response.json()

    # Combat bridge returns command_type="combat" and builds combat state.
    assert body["command_type"] == "combat"
    assert body["campaign"]["scene"] == "combat"
    assert body["campaign"]["combat"]
    assert body["campaign"]["combat"]["phase"]
    assert "turn_actor_id" in body["campaign"]["combat"]
    assert "available_actions" in body["campaign"]["combat"]
    assert "targets" in body["campaign"]["combat"]


def test_campaign_save_and_load_round_trip():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]
    saved = client.post(
        f"/game/campaigns/{campaign_id}/save",
        json={"player_id": "CampaignTester", "slot_name": "campaign_v3_slot"},
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
    assert loaded_payload["campaign"]["world_state"]["seed"] == 42
    assert loaded_payload["campaign"]["game_state"]["seed"] == 42
    assert loaded_payload["campaign"]["game_state"]["party"] == ["player"]
    assert loaded_payload["campaign"]["actors"]
    assert loaded_payload["campaign"]["systems"]["temperature_state"]["ambient_band"]
    assert loaded_payload["campaign"]["settlement"]["name"]


def test_campaign_save_listing_filters_legacy_and_other_campaign_slots(tmp_path: Path):
    runtime = CampaignRuntime(llm=None)
    runtime.save_system.save_dir = tmp_path / "campaign_api_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)
    old_runtime = campaign_routes.campaign_runtime
    campaign_routes.campaign_runtime = runtime
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
        player_saves = client.get("/game/campaigns/saves/player/CampaignTester")
        assert player_saves.status_code == 200
        player_entries = {entry["save_id"]: entry for entry in player_saves.json()}
        assert set(player_entries) == {"first_slot", "second_slot"}
        assert player_entries["first_slot"]["player_id"] == "CampaignTester"
        assert player_entries["second_slot"]["player_id"] == "CampaignTester"

        scoped = client.get(f"/game/campaigns/{first_id}/saves")
        assert scoped.status_code == 200
        assert [entry["save_id"] for entry in scoped.json()] == ["first_slot"]
    finally:
        campaign_routes.campaign_runtime = old_runtime


def test_legacy_session_routes_are_not_mounted():
    create_response = client.post("/game/session/new", json={"player_name": "Legacy", "player_class": "warrior"})
    save_response = client.get("/game/saves/Legacy")

    assert create_response.status_code == 404
    assert save_response.status_code == 404

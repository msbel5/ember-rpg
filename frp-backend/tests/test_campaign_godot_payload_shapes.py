import pytest
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

    assert campaign["world_state"]["seed"] == 42
    assert campaign["game_state"]["campaign_id"] == payload["campaign_id"]
    assert campaign["game_state"]["party"] == ["player"]
    assert campaign["actors"]
    assert campaign["jobs"]
    assert campaign["systems"]["power_network"]["total_required"] >= 0
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
    assert payload["campaign"]["world_state"]["active_region_id"] == payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["game_state"]["current_area_id"] == payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["systems"]["temperature_state"]["ambient_band"]


def test_campaign_combat_payload_shape_is_present_for_godot_consumers():
    create = client.post(
        "/game/campaigns",
        json={
            "player_name": "GodotCombatProbe",
            "player_class": "warrior",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": 101,
        },
    ).json()
    campaign_id = create["campaign_id"]

    npcs = [
        actor for actor in create["campaign"]["actors"]
        if actor["identity"]["actor_id"] != "player"
        and actor["identity"].get("actor_type") == "npc"
        and actor.get("alive", True)
    ]
    if not npcs:
        pytest.skip("No NPCs in fresh campaign to attack")

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"attack {npcs[0]['identity']['display_name']}"},
    )
    assert response.status_code == 200
    payload = response.json()
    combat = payload["campaign"]["combat"]

    assert isinstance(combat["phase"], str)
    assert isinstance(combat["round"], int)
    assert isinstance(combat["turn_actor_id"], str)
    assert isinstance(combat["available_actions"], list)
    assert "cast" not in combat["available_actions"]
    assert "use_item" not in combat["available_actions"]
    assert isinstance(combat["combatants"], list)
    assert isinstance(combat["targets"], list)
    assert isinstance(combat["move_options"], list)
    assert any(entry["is_player"] for entry in combat["combatants"])
    assert all(isinstance(entry["position"], list) and len(entry["position"]) == 2 for entry in combat["combatants"])

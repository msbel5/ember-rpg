"""Character sheet payload coverage for campaign runtime."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def _create_campaign() -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "SheetProbe",
            "player_class": "priest",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": 88,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_campaign_snapshot_contains_character_sheet():
    payload = _create_campaign()
    sheet = payload["campaign"]["character_sheet"]

    assert sheet["name"] == "SheetProbe"
    assert sheet["class_name"] == "Priest"
    assert sheet["alignment"]
    assert len(sheet["stats"]) == 6
    assert sheet["resources"]["hp"]["max"] >= sheet["resources"]["hp"]["current"]
    assert "creation_summary" in sheet


def test_campaign_command_preserves_character_sheet_shape():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": "look around"},
    )
    assert response.status_code == 200
    command_payload = response.json()
    sheet = command_payload["campaign"]["character_sheet"]

    assert sheet["name"] == "SheetProbe"
    assert sheet["class_name"] == "Priest"
    assert sheet["resources"]["ap"]["max"] >= sheet["resources"]["ap"]["current"]
    assert isinstance(sheet["skills"], list)

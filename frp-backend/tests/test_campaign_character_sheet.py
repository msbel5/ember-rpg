"""Character sheet payload coverage for campaign runtime."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.api.campaign.runtime import CampaignRuntime
from engine.data.classes import get_class_default_stats
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


def test_character_sheet_inventory_exposes_magical_item_metadata():
    from engine.kernel.actor_items import ItemStack

    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="SheetMage", player_class="mage", seed=99)
    player = context.kernel_runtime["actors"]["player"]
    player.inventory.append(
        ItemStack(
            instance_id="wand_sheet_1",
            item_def_id="wand_of_healing",
            quantity=1,
            payload={"name": "Wand of Healing", "charges": 4, "identified": False},
        )
    )
    player.inventory.append(
        ItemStack(
            instance_id="ring_sheet_1",
            item_def_id="ring_of_protection",
            quantity=1,
            payload={"name": "Ring of Protection"},
        )
    )

    payload = runtime.snapshot(context.campaign_id)
    sheet = payload["campaign"]["character_sheet"]
    wand = next(item for item in sheet["inventory"] if item["id"] == "wand_of_healing")
    ring = next(item for item in sheet["inventory"] if item["id"] == "ring_of_protection")

    assert wand["magical"] is True
    assert wand["identified"] is False
    assert wand["charges"] == 4
    assert ring["magical"] is True
    assert "inventory" in sheet


def test_character_sheet_progression_exposes_runtime_class_ability_metadata():
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="SheetWarrior", player_class="warrior", seed=101)
    player = context.kernel_runtime["actors"]["player"]
    player.raw_payload["level"] = 2
    player.raw_payload["class_ability_state"] = {"second_wind": {"used": True}}

    payload = runtime.snapshot(context.campaign_id)
    progression = payload["campaign"]["character_sheet"]["progression"]
    second_wind = next(item for item in progression["class_abilities"] if item["id"] == "second_wind")
    battle_hardened = next(item for item in progression["class_abilities"] if item["id"] == "battle_hardened")

    assert second_wind["unlocked"] is True
    assert second_wind["active"] is True
    assert second_wind["implemented"] is True
    assert second_wind["uses_remaining"] == 0
    assert second_wind["runtime_status"] == "expended_until_long_rest"
    assert battle_hardened["implemented"] is False
    assert "resource_cost" in second_wind


@pytest.mark.parametrize(
    ("requested_class", "canonical_class", "expected_label"),
    [
        ("ranger", "ranger", "Ranger"),
        ("Paladin", "paladin", "Paladin"),
        ("BARD", "bard", "Bard"),
    ],
)
def test_character_sheet_supports_extended_classes_without_silent_fallback(
    requested_class: str,
    canonical_class: str,
    expected_label: str,
):
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="SheetProbe", player_class=requested_class, seed=131)
    payload = runtime.snapshot(context.campaign_id)

    player = context.kernel_runtime["actors"]["player"]
    sheet = payload["campaign"]["character_sheet"]
    stats = {entry["id"]: int(entry["value"]) for entry in sheet["stats"]}
    class_abilities = sheet["progression"]["class_abilities"]

    assert str(player.raw_payload.get("class_name")) == canonical_class
    assert sheet["class_name"] == expected_label
    assert stats == get_class_default_stats(canonical_class)
    assert len(class_abilities) == 5
    assert all(entry["class_name"] == canonical_class for entry in class_abilities)
    assert class_abilities[0]["unlocked"] is True

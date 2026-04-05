from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel.actor_items import item_stack_from_legacy_payload


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="EquipmentTester", seed=77)
    return runtime, context


def test_character_sheet_exposes_additive_equipment_topology_fields() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.equipment.slots = {}
    player.equipment.add_item(
        "armor",
        item_stack_from_legacy_payload(
            {
                "id": "chain_mail",
                "name": "Chain Mail",
                "type": "armor",
                "material": "iron",
                "slot": "armor",
            }
        ),
    )
    player.equipment.add_item(
        "weapon",
        item_stack_from_legacy_payload(
            {
                "id": "iron_sword",
                "name": "Iron Sword",
                "type": "weapon",
                "material": "iron",
                "slot": "weapon",
            }
        ),
    )
    player.equipment.add_item(
        "left_ring",
        item_stack_from_legacy_payload(
            {
                "id": "ring_of_focus",
                "name": "Ring of Focus",
                "type": "trinket",
                "slot": "left_ring",
                "attunement_required": True,
                "attuned": True,
            }
        ),
    )

    sheet = runtime.snapshot(context.campaign_id, narrative="equipment-topology")["campaign"]["character_sheet"]
    armor = sheet["equipment"]["slots"]["armor"][0]
    weapon = sheet["equipment"]["slots"]["weapon"][0]
    ring = sheet["equipment"]["slots"]["left_ring"][0]

    assert armor["canonical_slot"] == "body"
    assert armor["legacy_slot"] == "armor"
    assert armor["coverage_zones"] == ["chest", "torso"]
    assert armor["armor_weight_class"] == "medium"
    assert armor["attunement_required"] is False
    assert weapon["canonical_slot"] == "main_hand"
    assert weapon["coverage_zones"] == []
    assert weapon["armor_weight_class"] == "none"
    assert ring["canonical_slot"] == "ring_left"
    assert ring["attunement_required"] is True
    assert sheet["equipment_topology"]["slots"]["body"]["item_def_id"] == "chain_mail"
    assert sheet["equipment_topology"]["slots"]["main_hand"]["item_def_id"] == "iron_sword"
    assert sheet["equipment_topology"]["slots"]["ring_left"]["item_def_id"] == "ring_of_focus"
    assert sheet["equipment_topology"]["legacy_slot_aliases"]["main_hand"] == ["weapon", "main_hand", "weapon_1"]
    assert sheet["attunement"] == {
        "slot_count": 3,
        "attuned_item_ids": ["ring_of_focus"],
        "available_slots": 2,
    }


def test_equipment_topology_remains_additive_and_backward_compatible() -> None:
    runtime, context = _make_campaign()

    sheet = runtime.snapshot(context.campaign_id, narrative="equipment-compat")["campaign"]["character_sheet"]

    assert "equipment" in sheet
    assert "slots" in sheet["equipment"]
    assert isinstance(sheet["equipment"]["slots"], dict)
    assert "equipment_topology" in sheet
    assert "equipment_modifiers" in sheet
    assert "attunement" in sheet
    assert set(sheet["attunement"]) == {"slot_count", "attuned_item_ids", "available_slots"}

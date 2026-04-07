from __future__ import annotations

from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel.actor_items import item_stack_from_payload


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="EquipmentTester", seed=77)
    return runtime, context


def test_character_sheet_exposes_additive_equipment_topology_fields() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.equipment.slots = {}
    player.equipment.add_item(
        "chest",
        item_stack_from_payload(
            {
                "id": "chain_mail",
                "name": "Chain Mail",
                "type": "armor",
                "material": "iron",
                "slot": "chest",
            }
        ),
    )
    player.equipment.add_item(
        "main_hand",
        item_stack_from_payload(
            {
                "id": "iron_sword",
                "name": "Iron Sword",
                "type": "weapon",
                "material": "iron",
                "slot": "main_hand",
            }
        ),
    )
    player.equipment.add_item(
        "ring_left",
        item_stack_from_payload(
            {
                "id": "ring_of_focus",
                "name": "Ring of Focus",
                "type": "trinket",
                "slot": "ring_left",
                "attunement_required": True,
                "attuned": True,
            }
        ),
    )

    sheet = runtime.snapshot(context.campaign_id, narrative="equipment-topology")["campaign"]["character_sheet"]
    armor = sheet["equipment_topology"]["slots"]["chest"]
    weapon = sheet["equipment_topology"]["slots"]["main_hand"]
    ring = sheet["equipment_topology"]["slots"]["ring_left"]

    assert "equipment" not in sheet
    assert armor["canonical_slot"] == "chest"
    assert armor["coverage_zones"] == ["chest", "torso"]
    assert armor["armor_weight_class"] == "chain_mail"
    assert armor["attunement_required"] is False
    assert weapon["canonical_slot"] == "main_hand"
    assert weapon["coverage_zones"] == []
    assert weapon["armor_weight_class"] == "none"
    assert ring["canonical_slot"] == "ring_left"
    assert ring["attunement_required"] is True
    assert sheet["equipment_topology"]["slots"]["chest"]["item_def_id"] == "chain_mail"
    assert sheet["equipment_topology"]["slots"]["main_hand"]["item_def_id"] == "iron_sword"
    assert sheet["equipment_topology"]["slots"]["ring_left"]["item_def_id"] == "ring_of_focus"
    assert sheet["attunement"] == {
        "slot_count": 3,
        "attuned_item_ids": ["ring_of_focus"],
        "available_slots": 2,
    }


def test_equipment_topology_remains_additive_and_canonical_only() -> None:
    runtime, context = _make_campaign()

    sheet = runtime.snapshot(context.campaign_id, narrative="equipment-compat")["campaign"]["character_sheet"]

    assert "equipment" not in sheet
    assert "equipment_topology" in sheet
    assert "equipment_modifiers" in sheet
    assert "attunement" in sheet
    assert set(sheet["attunement"]) == {"slot_count", "attuned_item_ids", "available_slots"}



from __future__ import annotations

from engine.kernel.actor_items import (
    EquipmentLoadout,
    ItemStack,
    build_equipment_topology_payload,
    canonical_slot_for_item_payload,
    coverage_zones_for_item,
)


def _stack(
    item_def_id: str,
    *,
    name: str,
    slot: str | None = None,
    payload: dict | None = None,
) -> ItemStack:
    item_payload = {"id": item_def_id, "item_def_id": item_def_id, "name": name, **dict(payload or {})}
    if slot is not None:
        item_payload.setdefault("slot", slot)
    return ItemStack(
        instance_id=f"{item_def_id}_instance",
        item_def_id=item_def_id,
        quantity=1,
        payload=item_payload,
    )


def test_ring_candidates_fall_back_to_right_ring_when_left_is_occupied():
    payload = {"id": "ring_of_protection", "name": "Ring of Protection", "type": "armor"}

    resolved = canonical_slot_for_item_payload(payload, occupied_slots={"ring_left"})

    assert resolved == "ring_right"


def test_coverage_fallback_uses_canonical_body_zones_for_chest_armor():
    armor = _stack("chain_mail", name="Chain Mail", payload={"type": "armor"})

    coverage = coverage_zones_for_item(armor, "chest")

    assert coverage == ["chest", "torso"]


def test_topology_payload_excludes_nonwearable_quick_slots():
    loadout = EquipmentLoadout(
        slots={
            "main_hand": [_stack("iron_sword", name="Iron Sword", payload={"type": "weapon"})],
            "quick_item_1": [_stack("field_tonic", name="Field Tonic", payload={"type": "consumable"})],
            "quiver_1": [_stack("arrow_bundle", name="Arrow Bundle", payload={"type": "ammunition"})],
        }
    )

    topology = build_equipment_topology_payload(loadout)

    assert topology["slots"]["main_hand"] is not None
    assert topology["slots"]["main_hand"]["id"] == "iron_sword"
    assert all("field_tonic" not in item_ids for item_ids in topology["coverage_summary"].values())
    assert all("arrow_bundle" not in item_ids for item_ids in topology["coverage_summary"].values())

"""
Canonical-only Phase 14 contract regression tests.

Freezes the removal of legacy slot concepts from public equipment
topology and ensures the canonical equipment system is clean.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────


def _create_campaign(seed: int = 42) -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "CanonProbe",
            "player_class": "warrior",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200
    return response.json()


def _player_actor(payload: dict) -> dict:
    return next(
        a for a in payload["campaign"]["actors"]
        if a["identity"]["actor_id"] == "player"
    )


# ═════════════════════════════════════════════════════════════════════
#  No legacy_slot in public equipment topology
# ═════════════════════════════════════════════════════════════════════


class TestNoLegacySlotInPublicTopology:
    """Phase 14: public actor payloads must not expose legacy_slot or
    legacy_slot_aliases at the top level of equipment topology."""

    def test_player_actor_has_no_legacy_slot_aliases_in_snapshot(self):
        payload = _create_campaign(seed=100)
        player = _player_actor(payload)
        # legacy_slot_aliases should NOT be in the public actor payload
        assert "legacy_slot_aliases" not in player, (
            "Player actor snapshot exposes legacy_slot_aliases — Phase 14 requires removal"
        )

    def test_player_equipment_items_have_no_legacy_slot_field(self):
        payload = _create_campaign(seed=101)
        player = _player_actor(payload)
        equipment = player.get("equipment", {})
        if isinstance(equipment, dict):
            for slot_id, items in equipment.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            assert "legacy_slot" not in item, (
                                f"Equipment item in slot {slot_id!r} exposes 'legacy_slot' — "
                                "Phase 14 requires canonical-only slot ids"
                            )


# ═════════════════════════════════════════════════════════════════════
#  No character_sheet.equipment in public payload
# ═════════════════════════════════════════════════════════════════════


class TestNoCharacterSheetEquipment:
    """Phase 14: character_sheet payload must not duplicate equipment."""

    def test_campaign_snapshot_has_no_character_sheet_equipment(self):
        payload = _create_campaign(seed=102)
        campaign = payload["campaign"]
        # If character_sheet exists at top level, it should not have equipment
        if "character_sheet" in campaign:
            assert "equipment" not in campaign["character_sheet"], (
                "campaign.character_sheet.equipment should not exist — "
                "equipment lives in actor topology only"
            )

    def test_player_actor_has_no_character_sheet_equipment(self):
        payload = _create_campaign(seed=103)
        player = _player_actor(payload)
        if "character_sheet" in player:
            assert "equipment" not in player["character_sheet"], (
                "player.character_sheet.equipment should not exist — "
                "equipment lives in actor.equipment only"
            )


# ═════════════════════════════════════════════════════════════════════
#  Canonical slot ids only
# ═════════════════════════════════════════════════════════════════════


class TestCanonicalSlotIdsOnly:
    """Public equipment topology must use canonical slot ids only."""

    # Known canonical slot ids from the kernel
    CANONICAL_SLOTS = {
        "main_hand",
        "off_hand",
        "head",
        "face",
        "neck",
        "shoulders",
        "chest",
        "arms",
        "hands",
        "belt",
        "legs",
        "feet",
        "ring_left",
        "ring_right",
        "trinket_1",
        "trinket_2",
        "attunement_1",
        "attunement_2",
        "attunement_3",
    }

    def test_equipment_slots_are_canonical(self):
        payload = _create_campaign(seed=104)
        topology_slots = payload["campaign"]["character_sheet"]["equipment_topology"]["slots"]
        assert set(topology_slots).issubset(self.CANONICAL_SLOTS)


# ═════════════════════════════════════════════════════════════════════
#  Equipment topology survives save/load
# ═════════════════════════════════════════════════════════════════════


class TestEquipmentTopologySaveLoad:
    """Equipment canonical topology must survive save/load cycle."""

    def test_equipment_topology_stable_across_save_load(self):
        payload = _create_campaign(seed=105)
        campaign_id = payload["campaign_id"]
        topology_before = payload["campaign"]["character_sheet"]["equipment_topology"]

        save_response = client.post(
            f"/game/campaigns/{campaign_id}/save",
            json={"player_id": "CanonProbe", "slot_name": "canon_topology_slot"},
        )
        assert save_response.status_code == 200
        loaded = client.post(
            f"/game/campaigns/load/{save_response.json()['save_id']}"
        ).json()
        topology_after = loaded["campaign"]["character_sheet"]["equipment_topology"]
        assert topology_before == topology_after

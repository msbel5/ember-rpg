"""Phase 2: ActorRecord factory lifecycle tests.

Tests that actors can be created directly from creation data and monster
templates without going through the legacy Character class.
"""

from engine.kernel.actor_records import (
    ActorRecord,
    create_monster_actor,
    create_player_actor,
)


# ── Player creation ──────────────────────────────────────────────────

def test_create_player_from_creation_data():
    """Factory must build a combat-ready player ActorRecord."""
    actor = create_player_actor(
        name="Arin",
        class_name="warrior",
        stats={"MIG": 16, "AGI": 12, "END": 14, "MND": 8, "INS": 10, "PRE": 10},
    )
    assert actor.identity.actor_id == "player"
    assert actor.identity.display_name == "Arin"
    assert actor.identity.actor_type == "pc"
    assert actor.alive is True
    assert actor.stats["MIG"] == 16
    assert actor.stats["hp"] > 0
    assert actor.stats["max_hp"] > 0
    assert actor.body_state is not None


def test_player_has_class_bab():
    """Player should have BAB from class data in raw_payload."""
    actor = create_player_actor(
        name="Mage",
        class_name="mage",
        stats={"MIG": 8, "AGI": 10, "END": 10, "MND": 16, "INS": 14, "PRE": 12},
    )
    # BAB should exist in raw_payload (may be 0 for mage level 1)
    assert "bab" in actor.raw_payload


def test_player_has_valid_body_state():
    """Player must have BodyState with 8 body parts."""
    actor = create_player_actor(
        name="Test",
        class_name="warrior",
        stats={"MIG": 14, "AGI": 12, "END": 14, "MND": 10, "INS": 10, "PRE": 10},
    )
    assert actor.body_state is not None
    assert len(actor.body_state.parts) >= 8  # head, neck, chest, torso, arms, legs


# ── Monster creation ─────────────────────────────────────────────────

def test_create_monster_from_template():
    """Factory must build a combat-ready monster ActorRecord."""
    template = {
        "id": "goblin_01",
        "name": "Goblin",
        "type": "humanoid",
        "cr": 0.25,
        "hp": 7,
        "armor_class": 15,
        "stats": {"MIG": 8, "AGI": 14, "END": 10, "MND": 10, "INS": 8, "PRE": 8},
        "attacks": [{"name": "Scimitar", "attack_bonus": 4, "damage_dice": "1d6+2"}],
    }
    actor = create_monster_actor(template)
    assert actor.identity.display_name == "Goblin"
    assert actor.identity.actor_type == "npc"
    assert actor.alive is True
    # Ember-native stats
    assert actor.stats["MIG"] == 8
    assert actor.stats["AGI"] == 14
    assert actor.stats["END"] == 10
    assert actor.stats["hp"] == 7
    assert actor.stats["max_hp"] == 7


def test_monster_has_valid_body_state():
    """Monster must have BodyState."""
    template = {
        "id": "wolf",
        "name": "Wolf",
        "type": "beast",
        "hp": 11,
        "armor_class": 13,
        "stats": {"MIG": 12, "AGI": 15, "END": 12, "MND": 3, "INS": 12, "PRE": 6},
    }
    actor = create_monster_actor(template)
    assert actor.body_state is not None


def test_monster_maps_attack_bonus_to_skills():
    """Monster attack bonus should map to melee skill."""
    template = {
        "id": "orc",
        "name": "Orc",
        "type": "humanoid",
        "hp": 15,
        "armor_class": 13,
        "stats": {"MIG": 16, "AGI": 12, "END": 16, "MND": 7, "INS": 11, "PRE": 10},
        "attacks": [{"name": "Greataxe", "attack_bonus": 5, "damage_dice": "1d12+3"}],
    }
    actor = create_monster_actor(template)
    assert "melee" in actor.skills


def test_monster_unique_actor_id():
    """Each monster should get a unique actor_id."""
    template = {"id": "rat", "name": "Rat", "hp": 1, "stats": {}}
    a = create_monster_actor(template)
    b = create_monster_actor(template)
    assert a.identity.actor_id != b.identity.actor_id


# ── Serialization round-trip ──────────────────────────────────────────

def test_player_serialization_round_trip():
    """Player actor survives to_dict -> from_dict."""
    actor = create_player_actor(
        name="RoundTrip",
        class_name="rogue",
        stats={"MIG": 10, "AGI": 16, "END": 12, "MND": 14, "INS": 10, "PRE": 12},
    )
    data = actor.to_dict()
    restored = ActorRecord.from_dict(data)
    assert restored.identity.display_name == "RoundTrip"
    assert restored.stats["AGI"] == 16
    assert restored.alive is True


def test_monster_serialization_round_trip():
    """Monster actor survives to_dict -> from_dict."""
    template = {
        "id": "skeleton",
        "name": "Skeleton",
        "type": "undead",
        "hp": 13,
        "armor_class": 13,
        "stats": {"MIG": 10, "AGI": 14, "END": 15, "MND": 6, "INS": 8, "PRE": 5},
    }
    actor = create_monster_actor(template)
    data = actor.to_dict()
    restored = ActorRecord.from_dict(data)
    assert restored.identity.display_name == "Skeleton"
    assert restored.stats["AGI"] == 14
    assert restored.stats["hp"] == 13


# ── Body state wound persistence ──────────────────────────────────────

def test_body_state_persists_wounds():
    """Wounds applied to BodyState must survive serialization."""
    from engine.kernel.actor_body import WoundRecord

    actor = create_player_actor(
        name="Wounded",
        class_name="warrior",
        stats={"MIG": 14, "AGI": 12, "END": 14, "MND": 10, "INS": 10, "PRE": 10},
    )
    wound = WoundRecord(
        wound_id="w1",
        body_part_id="chest",
        damage_type="slashing",
        damage_amount=5,
        bleeding=2,
        pain=3,
        open_wound=True,
    )
    actor.body_state.wounds.append(wound)
    data = actor.to_dict()
    restored = ActorRecord.from_dict(data)
    assert len(restored.body_state.wounds) == 1
    assert restored.body_state.wounds[0].body_part_id == "chest"
    assert restored.body_state.wounds[0].bleeding == 2

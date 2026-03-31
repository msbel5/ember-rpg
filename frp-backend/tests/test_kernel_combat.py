from engine.kernel import (
    actor_record_from_character,
    actor_record_from_entity,
    item_stack_from_legacy_payload,
    resolve_strike,
    sync_body_state_to_tracker,
)
from engine.world.body_parts import BodyPartTracker
from engine.world.entity import Entity, EntityType
from engine.world.npc_needs import NPCNeeds
from engine.core.character import Character


def _defender(*, armored: bool = False) -> Entity:
    inventory = []
    if armored:
        inventory.append(
            {
                "id": "mail_shirt_01",
                "name": "Mail Shirt",
                "slot": "armor",
                "coverage": ["chest", "torso"],
                "coverage_percentage": 100,
                "material_id": "steel",
                "quality": 3,
                "wear": 0,
            }
        )
    return Entity(
        id="defender_01",
        entity_type=EntityType.NPC,
        name="Defender",
        position=(4, 4),
        glyph="D",
        color="white",
        blocking=True,
        needs=NPCNeeds(),
        inventory=inventory,
        body=BodyPartTracker(),
        hp=18,
        max_hp=18,
        skills={"melee": 2},
        faction="watch",
    )


def _attacker() -> tuple[Character, dict]:
    character = Character(
        name="Attacker",
        hp=20,
        max_hp=20,
        stats={"MIG": 16, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        skills={"melee": 4, "sword": 4},
    )
    weapon = {
        "id": "iron_longsword",
        "name": "Iron Longsword",
        "slot": "weapon",
        "material_id": "iron",
        "quality": 2,
        "damage": 8,
        "damage_type": "slashing",
        "sharpness": 100,
    }
    return character, weapon


def test_resolve_strike_is_deterministic_for_same_seed():
    attacker_character, weapon_payload = _attacker()
    attacker = actor_record_from_character(
        attacker_character,
        actor_id="player",
        equipment_payloads={"weapon": weapon_payload},
    )
    defender_a = actor_record_from_entity(_defender())
    defender_b = actor_record_from_entity(_defender())
    weapon = item_stack_from_legacy_payload(weapon_payload)

    outcome_a = resolve_strike(attacker, defender_a, weapon=weapon, seed=7, raw_damage=9)
    outcome_b = resolve_strike(attacker, defender_b, weapon=weapon, seed=7, raw_damage=9)

    assert outcome_a.to_dict() == outcome_b.to_dict()


def test_resolve_strike_applies_armor_and_wear_updates():
    attacker_character, weapon_payload = _attacker()
    attacker = actor_record_from_character(
        attacker_character,
        actor_id="player",
        equipment_payloads={"weapon": weapon_payload},
    )
    defender = actor_record_from_entity(_defender(armored=True))
    weapon = item_stack_from_legacy_payload(weapon_payload)

    outcome = resolve_strike(
        attacker,
        defender,
        weapon=weapon,
        seed=4,
        raw_damage=10,
        explicit_hit_part="chest",
    )

    assert outcome.hit is True
    assert outcome.hit_part_id == "chest"
    assert outcome.armor_absorbed > 0
    assert outcome.effective_damage < outcome.attack_force
    assert outcome.equipment_wear
    assert defender.equipment.slots["armor"][0].wear > 0


def test_resolve_strike_marks_vital_wound_and_syncs_back_to_tracker():
    attacker_character, weapon_payload = _attacker()
    attacker = actor_record_from_character(
        attacker_character,
        actor_id="player",
        equipment_payloads={"weapon": weapon_payload},
    )
    live_defender = _defender()
    defender = actor_record_from_entity(live_defender)
    weapon = item_stack_from_legacy_payload(weapon_payload)

    outcome = resolve_strike(
        attacker,
        defender,
        weapon=weapon,
        seed=1,
        raw_damage=18,
        crit=True,
        explicit_hit_part="chest",
    )
    sync_body_state_to_tracker(defender.body_state, live_defender.body)

    assert outcome.wound is not None
    assert outcome.wound.open_wound is True
    assert outcome.wound.bleeding >= 1
    assert outcome.defender_viable is False
    assert live_defender.body.current_hp["chest"] == defender.body_state.parts["chest"].current_hp

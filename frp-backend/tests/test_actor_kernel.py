from engine.kernel import ActorRecord, BodyState, WoundRecord, actor_record_from_entity
from engine.world.body_parts import BodyPartTracker
from engine.world.entity import Entity, EntityType
from engine.world.npc_needs import NPCNeeds


def _legacy_entity(entity_type: EntityType) -> Entity:
    body = BodyPartTracker()
    body.apply_damage("left_arm", 4)
    return Entity(
        id=f"{entity_type.value}_001",
        entity_type=entity_type,
        name="Kernel Subject",
        position=(7, 9),
        glyph="@",
        color="white",
        blocking=True,
        needs=NPCNeeds(safety=55, social=35, sustenance=80),
        inventory=[
            {"id": "iron_sword_1", "name": "Iron Sword", "slot": "main_hand", "quality": 2},
            {"id": "travel_cloak_1", "name": "Travel Cloak", "slot": "cover", "coverage": ["torso", "chest"]},
        ],
        skills={"sword": 4, "insight": 2},
        body=body,
        faction="watch",
        alive=True,
        hp=8,
        max_hp=10,
        ap=3,
        max_ap=4,
    )


def test_actor_record_adapter_unifies_npc_and_creature_roots():
    npc_record = actor_record_from_entity(_legacy_entity(EntityType.NPC), site_id="site_alpha", species_id="human")
    creature_record = actor_record_from_entity(
        _legacy_entity(EntityType.CREATURE), site_id="site_alpha", species_id="wolf"
    )

    assert isinstance(npc_record, ActorRecord)
    assert isinstance(creature_record, ActorRecord)
    assert npc_record.identity.actor_type == "npc"
    assert creature_record.identity.actor_type == "creature"


def test_actor_record_preserves_body_inventory_and_legacy_payload():
    record = actor_record_from_entity(_legacy_entity(EntityType.NPC), site_id="site_alpha", species_id="human")

    assert record.identity.faction_id == "watch"
    assert record.body_state is not None
    assert record.body_state.parts["left_arm"].status == "bruised"
    assert len(record.inventory) == 2
    assert record.equipment.slots["main_hand"][0].item_def_id == "iron_sword"
    assert record.raw_payload["legacy_glyph"] == "@"


def test_actor_record_round_trip_keeps_identity_and_body_state():
    original = actor_record_from_entity(_legacy_entity(EntityType.NPC), site_id="site_alpha", species_id="human")
    serialized = original.to_dict()
    restored = ActorRecord.from_dict(serialized)

    assert restored.identity.actor_id == original.identity.actor_id
    assert restored.position.x == 7
    assert restored.body_state is not None
    assert restored.body_state.parts["left_arm"].current_hp == original.body_state.parts["left_arm"].current_hp
    assert restored.inventory[0].instance_id == original.inventory[0].instance_id
    assert "action_points" not in serialized
    assert "max_action_points" not in serialized
    assert restored.turn_resources["action_available"] is True
    assert restored.turn_resources["movement_remaining"] == 3


def test_body_state_apply_wound_marks_vital_part_non_viable():
    body_state = BodyState.from_tracker(BodyPartTracker())
    body_state.apply_wound(
        WoundRecord(
            wound_id="wound_01",
            body_part_id="chest",
            damage_type="cut",
            damage_amount=20,
        )
    )

    assert body_state.parts["chest"].status == "destroyed"
    assert body_state.is_viable() is False

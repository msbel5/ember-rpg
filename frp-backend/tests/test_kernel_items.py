from __future__ import annotations

from engine.kernel.actor import (
    ActorIdentity,
    ActorPosition,
    ActorRecord,
    BodyPartDef,
    BodyPartState,
    BodyPlanDef,
    BodyState,
    EquipmentLoadout,
    MaterialDef,
    TissueLayerDef,
)
from engine.kernel.effects import EffectDef, compute_effective_stat
from engine.kernel.items import (
    CombatHeader,
    ItemDef,
    ItemInstance,
    ItemRequirements,
    apply_item_wear,
    bypasses_weapon_immunity,
    can_equip,
    can_stack,
    compute_encumbrance,
    compute_item_wear,
    equip_item,
    identify_item,
    unequip_item,
    use_item,
)


def _body_state() -> BodyState:
    plan = BodyPlanDef(
        plan_id="humanoid",
        label="Humanoid",
        parts=[
            BodyPartDef(
                part_id="torso",
                label="Torso",
                max_hp=12,
                vital=True,
                relative_size=12,
                layers=[
                    TissueLayerDef("skin", "skin", relative_thickness=2),
                    TissueLayerDef("organs", "organ", relative_thickness=2, vital=True),
                ],
            )
        ],
    )
    return BodyState(
        plan=plan,
        parts={"torso": BodyPartState(part_id="torso", current_hp=12, max_hp=12)},
    )


def _actor(*, stats: dict[str, int] | None = None, skills: dict[str, int] | None = None, raw_payload: dict | None = None) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id="actor_1", display_name="Actor", actor_type="npc"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats=stats or {"STR": 12, "DEX": 10, "INT": 10, "WIS": 10, "CON": 10, "CHA": 10, "hp": 20, "max_hp": 20},
        skills=skills or {},
        body_state=_body_state(),
        inventory=[],
        equipment=EquipmentLoadout(),
        raw_payload=raw_payload or {},
    )


def _effect_registry() -> dict[str, EffectDef]:
    return {
        "str_bonus_2": EffectDef(
            effect_def_id="str_bonus_2",
            label="Strength +2",
            category="stat_mod",
            target_stat="STR",
            modifier_type="flat",
            modifier_value=2,
            timing_mode="while_equipped",
            base_duration_ticks=-1,
        ),
        "heal_20": EffectDef(
            effect_def_id="heal_20",
            label="Heal 20",
            category="healing",
            healing_per_tick=20,
            timing_mode="instant",
        ),
    }


def test_ac01_can_equip_checks_minimum_stat_requirements():
    actor = _actor(stats={"STR": 12, "DEX": 10, "INT": 10, "WIS": 10, "CON": 10, "CHA": 10, "hp": 20, "max_hp": 20})
    item_def = ItemDef(
        item_def_id="greatsword",
        label="Greatsword",
        item_type="weapon",
        item_category="sword",
        weight=30,
        base_price=100,
        requirements=ItemRequirements(min_str=14),
    )

    allowed, failures = can_equip(actor, item_def)

    assert allowed is False
    assert failures == ["min_str: need 14 have 12"]


def test_ac02_equip_and_unequip_apply_and_remove_effects():
    actor = _actor(raw_payload={"effect_registry": _effect_registry()})
    item_def = ItemDef(
        item_def_id="belt_of_might",
        label="Belt of Might",
        item_type="belt",
        item_category="belt",
        weight=10,
        base_price=500,
        equip_effect_ids=["str_bonus_2"],
    )
    item = ItemInstance(instance_id="belt_1", item_def_id=item_def.item_def_id)
    actor.inventory.append(item)

    equip_item(actor, item, "belt", item_def)
    assert compute_effective_stat(actor, "STR") == 14

    unequip_item(actor, "belt")
    assert compute_effective_stat(actor, "STR") == 12


def test_ac03_compute_item_wear_uses_quality_multiplier():
    item_def = ItemDef(
        item_def_id="iron_sword",
        label="Iron Sword",
        item_type="weapon",
        item_category="sword",
        weight=30,
        base_price=100,
        base_durability=100,
    )
    material = MaterialDef(
        material_id="iron",
        label="Iron",
        category="metal",
        density=1000,
        impact_fracture=100,
    )
    item = ItemInstance(instance_id="sword_1", item_def_id=item_def.item_def_id, quality=3)

    max_wear = compute_item_wear(item, item_def, material)

    assert max_wear == 160


def test_ac04_apply_item_wear_breaks_item_at_cap():
    item = ItemInstance(instance_id="armor_1", item_def_id="chain_mail", wear=99, max_wear=100)

    just_broke = apply_item_wear(item, 2)

    assert just_broke is True
    assert item.wear == 100
    assert item.is_broken is True


def test_ac05_identify_item_succeeds_with_enough_lore():
    actor = _actor(skills={"lore": 45})
    item_def = ItemDef(
        item_def_id="mystery_ring",
        label="Mystery Ring",
        item_type="ring",
        item_category="ring",
        weight=1,
        base_price=250,
        lore_to_identify=40,
    )
    item = ItemInstance(instance_id="ring_1", item_def_id=item_def.item_def_id)

    assert identify_item(actor, item, item_def) is True
    assert item.identified is True


def test_ac06_identify_item_fails_without_enough_lore():
    actor = _actor(skills={"lore": 35})
    item_def = ItemDef(
        item_def_id="mystery_ring",
        label="Mystery Ring",
        item_type="ring",
        item_category="ring",
        weight=1,
        base_price=250,
        lore_to_identify=40,
    )
    item = ItemInstance(instance_id="ring_1", item_def_id=item_def.item_def_id)

    assert identify_item(actor, item, item_def) is False
    assert item.identified is False


def test_ac07_can_stack_requires_same_template_material_and_quality():
    first = ItemInstance(instance_id="arrow_stack_a", item_def_id="arrow", material_id="wood", quality=1, stack_count=8)
    second = ItemInstance(instance_id="arrow_stack_b", item_def_id="arrow", material_id="wood", quality=1, stack_count=5)

    assert can_stack(first, second) is True


def test_ac08_use_item_applies_effect_and_destroys_spent_potion():
    registry = _effect_registry()
    actor = _actor(raw_payload={"effect_registry": registry})
    actor.stats["hp"] = 5
    target = actor
    item_def = ItemDef(
        item_def_id="potion_healing",
        label="Potion of Healing",
        item_type="potion",
        item_category="healing",
        weight=1,
        base_price=50,
        use_effect_ids=["heal_20"],
    )
    item = ItemInstance(instance_id="potion_1", item_def_id=item_def.item_def_id, charges=1)

    result = use_item(actor, item, item_def, target)

    assert result["destroyed"] is True
    assert actor.stats["hp"] == 20


def test_ac09_combat_header_exposes_attack_and_damage_bonuses():
    header = CombatHeader(
        attack_type="melee",
        range=0,
        speed_factor=4,
        thac0_bonus=2,
        dice_count=1,
        dice_sides=8,
        damage_bonus=3,
        damage_type="slashing",
    )

    assert header.thac0_bonus == 2
    assert header.damage_bonus == 3


def test_ac10_item_def_and_instance_round_trip_without_loss():
    item_def = ItemDef(
        item_def_id="wand_fire",
        label="Wand of Fire",
        item_type="wand",
        item_category="wand",
        weight=2,
        base_price=1500,
        max_stack=1,
        enchantment=2,
        requirements=ItemRequirements(min_int=12, class_usability=["mage"]),
        combat_headers=[CombatHeader(attack_type="launcher", range=30, speed_factor=1)],
        equip_effect_ids=["str_bonus_2"],
        use_effect_ids=["heal_20"],
        lore_to_identify=30,
        base_durability=80,
        flags=["magical"],
        description="A charred wand.",
        identified_description="A wand of fire.",
    )
    item = ItemInstance(
        instance_id="wand_1",
        item_def_id=item_def.item_def_id,
        material_id="ash",
        quality=2,
        wear=5,
        max_wear=80,
        identified=True,
        charges=7,
        stack_count=1,
        equipped_slot="weapon_1",
    )

    assert ItemDef.from_dict(item_def.to_dict()) == item_def
    assert ItemInstance.from_dict(item.to_dict()) == item


def test_ac11_equip_item_replaces_existing_weapon_to_inventory():
    actor = _actor(raw_payload={"effect_registry": _effect_registry()})
    sword_def = ItemDef(item_def_id="sword", label="Sword", item_type="weapon", item_category="sword", weight=20, base_price=50)
    axe_def = ItemDef(item_def_id="axe", label="Axe", item_type="weapon", item_category="axe", weight=25, base_price=60)
    sword = ItemInstance(instance_id="sword_1", item_def_id="sword")
    axe = ItemInstance(instance_id="axe_1", item_def_id="axe")
    actor.equipment.slots["weapon_1"] = [sword]
    actor.inventory.append(axe)

    equip_item(actor, axe, "weapon_1", axe_def)

    assert actor.equipment.slots["weapon_1"][0].instance_id == "axe_1"
    assert any(item.instance_id == "sword_1" for item in actor.inventory)


def test_ac12_enchanted_weapon_bypasses_non_magical_immunity():
    item_def = ItemDef(
        item_def_id="longsword_plus_two",
        label="Longsword +2",
        item_type="weapon",
        item_category="sword",
        weight=20,
        base_price=5000,
        enchantment=2,
    )

    assert bypasses_weapon_immunity(item_def, {"immune_to_nonmagical_weapons": True}) is True


def test_compute_encumbrance_sums_item_weight_and_stack_counts():
    item_registry = {
        "arrow": ItemDef(item_def_id="arrow", label="Arrow", item_type="ammunition", item_category="arrow", weight=1, base_price=1, max_stack=20),
        "armor": ItemDef(item_def_id="armor", label="Armor", item_type="armor", item_category="mail", weight=40, base_price=100),
    }
    inventory = [
        ItemInstance(instance_id="a", item_def_id="arrow", stack_count=10),
        ItemInstance(instance_id="b", item_def_id="armor", stack_count=1),
    ]

    assert compute_encumbrance(inventory, item_registry) == 50

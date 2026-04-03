from __future__ import annotations

import pytest

from engine.kernel.actor import (
    ActorIdentity,
    ActorPosition,
    ActorRecord,
    BodyPartDef,
    BodyPartState,
    BodyPlanDef,
    BodyState,
    EquipmentLoadout,
    ItemStack,
    TissueLayerDef,
)
from engine.kernel.combat import (
    BloodState,
    MoraleState,
    PainState,
    check_morale,
    compute_attack_roll,
    compute_attacks_per_round,
    compute_defense_ac,
    resolve_attack,
)


def _body_state() -> BodyState:
    plan = BodyPlanDef(
        plan_id="humanoid",
        label="Humanoid",
        parts=[
            BodyPartDef(
                part_id="head",
                label="Head",
                max_hp=8,
                vital=True,
                relative_size=6,
                layers=[
                    TissueLayerDef("skin", "skin", relative_thickness=1),
                    TissueLayerDef("bone", "bone", relative_thickness=2, structural=True),
                    TissueLayerDef("brain", "organ", relative_thickness=2, vital=True),
                ],
            ),
            BodyPartDef(
                part_id="torso",
                label="Torso",
                max_hp=12,
                vital=True,
                relative_size=12,
                layers=[
                    TissueLayerDef("skin", "skin", relative_thickness=2, under_pressure=True),
                    TissueLayerDef("muscle", "muscle", relative_thickness=2),
                    TissueLayerDef("organs", "organ", relative_thickness=2, vital=True),
                ],
            ),
            BodyPartDef(
                part_id="chest",
                label="Chest",
                max_hp=10,
                vital=True,
                relative_size=10,
                layers=[
                    TissueLayerDef("skin", "skin", relative_thickness=2, under_pressure=True),
                    TissueLayerDef("ribcage", "bone", relative_thickness=2, structural=True),
                    TissueLayerDef("lungs", "organ", relative_thickness=2, vital=True),
                ],
            ),
        ],
    )
    return BodyState(
        plan=plan,
        parts={
            "head": BodyPartState(part_id="head", current_hp=8, max_hp=8),
            "torso": BodyPartState(part_id="torso", current_hp=12, max_hp=12),
            "chest": BodyPartState(part_id="chest", current_hp=10, max_hp=10),
        },
    )


def _weapon(
    *,
    instance_id: str = "weapon_1",
    damage: int = 6,
    damage_type: str = "slashing",
    crit_multiplier: int = 2,
    threat_min: int = 20,
    light: bool = False,
) -> ItemStack:
    return ItemStack(
        instance_id=instance_id,
        item_def_id="test_weapon",
        payload={
            "slot": "weapon",
            "damage": damage,
            "damage_type": damage_type,
            "crit_multiplier": crit_multiplier,
            "threat_min": threat_min,
            "light": light,
        },
    )


def _armor(*, armor_bonus: int = 5, max_dex: int = 2) -> ItemStack:
    return ItemStack(
        instance_id="armor_1",
        item_def_id="chain_mail",
        payload={
            "slot": "armor",
            "coverage": ["torso", "chest"],
            "coverage_percentage": 100,
            "armor_bonus": armor_bonus,
            "max_dex": max_dex,
        },
    )


def _shield(*, shield_bonus: int = 2) -> ItemStack:
    return ItemStack(
        instance_id="shield_1",
        item_def_id="kite_shield",
        payload={
            "slot": "shield",
            "coverage": ["torso", "chest"],
            "coverage_percentage": 100,
            "shield_bonus": shield_bonus,
        },
    )


def _actor(
    *,
    actor_id: str = "actor_1",
    stats: dict[str, int] | None = None,
    skills: dict[str, int] | None = None,
    raw_payload: dict | None = None,
    equipment: EquipmentLoadout | None = None,
    inventory: list[ItemStack] | None = None,
) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats=stats or {"MIG": 10, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20},
        skills=skills or {},
        body_state=_body_state(),
        equipment=equipment or EquipmentLoadout(),
        inventory=inventory or [],
        raw_payload=raw_payload or {},
    )


def test_ac01_compute_attack_roll_uses_bab_ability_and_proficiency():
    attacker = _actor(
        stats={"MIG": 16, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20},
        raw_payload={"bab": 5, "weapon_proficiency_bonus": 2},
    )

    roll = compute_attack_roll(attacker, weapon=_weapon(), d20_roll=12)

    assert roll.total == 22


def test_ac02_compute_defense_ac_uses_armor_shield_and_capped_dex():
    armor = _armor(armor_bonus=5, max_dex=2)
    shield = _shield(shield_bonus=2)
    defender = _actor(
        stats={"MIG": 10, "AGI": 14, "INS": 10, "hp": 20, "max_hp": 20},
        equipment=EquipmentLoadout(slots={"armor": [armor], "shield": [shield]}),
        inventory=[armor, shield],
    )

    defense = compute_defense_ac(defender)

    assert defense.total == 19


def test_ac03_attack_misses_when_total_below_ac():
    attacker = _actor(stats={"MIG": 16, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20}, raw_payload={"bab": 3})
    armor = _armor(armor_bonus=5, max_dex=2)
    shield = _shield(shield_bonus=2)
    defender = _actor(
        stats={"MIG": 10, "AGI": 14, "INS": 10, "hp": 20, "max_hp": 20},
        equipment=EquipmentLoadout(slots={"armor": [armor], "shield": [shield]}),
        inventory=[armor, shield],
    )

    result = resolve_attack(attacker, defender, weapon=_weapon(), d20_roll=12, raw_damage=6)

    assert result.hit is False


def test_ac04_natural_one_always_misses():
    attacker = _actor(stats={"MIG": 20, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20}, raw_payload={"bab": 10})
    defender = _actor(stats={"MIG": 10, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20})

    result = resolve_attack(attacker, defender, weapon=_weapon(), d20_roll=1, raw_damage=6)

    assert result.attack_roll.is_natural_one is True
    assert result.hit is False


def test_ac05_natural_twenty_always_hits():
    attacker = _actor(stats={"MIG": 10, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20}, raw_payload={"bab": 0})
    armor = _armor(armor_bonus=15, max_dex=0)
    shield = _shield(shield_bonus=5)
    defender = _actor(
        stats={"MIG": 10, "AGI": 20, "INS": 10, "hp": 20, "max_hp": 20},
        equipment=EquipmentLoadout(slots={"armor": [armor], "shield": [shield]}),
        inventory=[armor, shield],
    )

    result = resolve_attack(attacker, defender, weapon=_weapon(), d20_roll=20, confirm_roll=1, raw_damage=6)

    assert result.attack_roll.is_natural_twenty is True
    assert result.hit is True


def test_ac06_critical_is_confirmed_when_confirmation_beats_ac():
    attacker = _actor(stats={"MIG": 16, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20}, raw_payload={"bab": 6})
    defender = _actor(stats={"MIG": 10, "AGI": 14, "INS": 10, "hp": 20, "max_hp": 20})

    result = resolve_attack(attacker, defender, weapon=_weapon(damage=6), d20_roll=20, confirm_roll=14, raw_damage=6)

    assert result.critical_threatened is True
    assert result.critical_confirmed is True


def test_ac07_critical_is_not_confirmed_when_confirmation_misses():
    attacker = _actor(stats={"MIG": 16, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20}, raw_payload={"bab": 6})
    armor = _armor(armor_bonus=5, max_dex=2)
    shield = _shield(shield_bonus=2)
    defender = _actor(
        stats={"MIG": 10, "AGI": 14, "INS": 10, "hp": 20, "max_hp": 20},
        equipment=EquipmentLoadout(slots={"armor": [armor], "shield": [shield]}),
        inventory=[armor, shield],
    )

    result = resolve_attack(attacker, defender, weapon=_weapon(damage=6), d20_roll=20, confirm_roll=8, raw_damage=6)

    assert result.critical_threatened is True
    assert result.critical_confirmed is False


def test_ac08_backstab_adds_level_times_weapon_base_damage():
    attacker = _actor(
        stats={"MIG": 16, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20},
        raw_payload={"bab": 5, "backstab_level": 3},
    )
    defender = _actor(stats={"MIG": 10, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20})

    result = resolve_attack(
        attacker,
        defender,
        weapon=_weapon(damage=6),
        d20_roll=15,
        raw_damage=6,
        backstab=True,
        flanking=True,
    )

    assert result.backstab_applied is True
    assert any(event.get("type") == "backstab" and event.get("extra_damage") == 18 for event in result.events)


def test_ac09_called_shot_applies_minus_four_penalty():
    attacker = _actor(stats={"MIG": 16, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20}, raw_payload={"bab": 5})

    roll = compute_attack_roll(attacker, weapon=_weapon(), d20_roll=12, called_shot="head")

    assert roll.situational == -4


def test_ac10_pain_state_hits_unconscious_at_point_eight_ratio():
    state = PainState(current_pain=80, base_max_pain=100, willpower_modifier=0.0)

    assert state.pain_ratio == 0.8
    assert state.is_unconscious is True


def test_ac11_willpower_reduces_effective_pain_before_thresholds():
    state = PainState(current_pain=80, base_max_pain=100, willpower_modifier=0.2)

    assert state.effective_pain == 64
    assert state.pain_ratio == 0.64
    assert state.is_stunned is True
    assert state.is_unconscious is False


def test_ac12_unconscious_from_pain_drops_items_and_prevents_actions():
    weapon = _weapon(instance_id="main_hand_weapon", damage=20)
    attacker = _actor(stats={"MIG": 20, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20}, raw_payload={"bab": 8})
    defender = _actor(
        stats={"MIG": 10, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20},
        raw_payload={"base_max_pain": 20},
        equipment=EquipmentLoadout(slots={"weapon": [weapon]}),
        inventory=[weapon],
    )
    defender.body_state.parts["torso"].pain = 12

    result = resolve_attack(attacker, defender, weapon=_weapon(damage=4), d20_roll=15, raw_damage=4, called_shot="torso")

    assert result.incapacitation == "unconscious"
    assert defender.raw_payload.get("prone") is True
    assert defender.raw_payload.get("can_act") is False
    assert defender.equipment.slots.get("weapon", []) == []
    assert defender.raw_payload.get("dropped_items") == ["main_hand_weapon"]


def test_ac13_blood_state_unconscious_at_half_blood():
    state = BloodState(blood_count=2500, max_blood=5000)

    assert state.is_unconscious is True


def test_ac14_blood_state_dead_at_zero():
    state = BloodState(blood_count=0, max_blood=5000)

    assert state.is_dead is True


def test_ac15_morale_check_failure_sets_fleeing():
    actor = _actor(stats={"MIG": 10, "AGI": 10, "INS": 14, "hp": 20, "max_hp": 20})
    morale = MoraleState(base_morale=4)

    result = check_morale(actor, morale, "ally_death", d20_roll=10)

    assert result["passed"] is False
    assert morale.fleeing is True


def test_ac16_morale_check_success_does_not_flee():
    actor = _actor(stats={"MIG": 10, "AGI": 10, "INS": 14, "hp": 20, "max_hp": 20})
    morale = MoraleState(base_morale=4)

    result = check_morale(actor, morale, "ally_death", d20_roll=12)

    assert result["passed"] is True
    assert morale.fleeing is False


def test_ac17_attacks_per_round_for_bab_eleven_are_three_attacks():
    attacker = _actor(raw_payload={"bab": 11})

    schedule = compute_attacks_per_round(attacker)

    assert [attack["bab_for_attack"] for attack in schedule.attacks] == [11, 6, 1]


def test_ac18_dual_wield_light_weapon_adds_offhand_attack():
    attacker = _actor(raw_payload={"bab": 6})

    schedule = compute_attacks_per_round(attacker, dual_wield=True, off_hand_light=True)

    assert [attack["bab_for_attack"] for attack in schedule.attacks] == [6, 1, 4]


def test_ac19_haste_adds_extra_full_bab_attack():
    attacker = _actor(raw_payload={"bab": 6})

    schedule = compute_attacks_per_round(attacker, haste=True)

    assert [attack["bab_for_attack"] for attack in schedule.attacks] == [6, 6, 1]
    assert schedule.attacks[0]["is_haste"] is True


def test_ac20_resolve_attack_delegates_to_existing_resolve_strike_force_model(monkeypatch):
    attacker = _actor(stats={"MIG": 16, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20}, raw_payload={"bab": 6})
    defender = _actor(stats={"MIG": 10, "AGI": 10, "INS": 10, "hp": 20, "max_hp": 20})
    captured: dict[str, object] = {}

    from engine.kernel import combat as combat_module

    original = combat_module.resolve_strike

    def _wrapped(*args, **kwargs):
        captured.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(combat_module, "resolve_strike", _wrapped)

    result = resolve_attack(attacker, defender, weapon=_weapon(damage=8), d20_roll=15, raw_damage=8, seed=7)

    assert result.hit is True
    assert result.strike_resolution is not None
    assert captured["raw_damage"] == 8
    assert "seed" in captured


def test_ac21_flat_footed_excludes_dex_bonus():
    defender = _actor(stats={"MIG": 10, "AGI": 14, "INS": 10, "hp": 20, "max_hp": 20})

    defense = compute_defense_ac(defender, flat_footed=True)

    assert defense.dex_bonus == 0
    assert defense.total == 10


def test_ac22_touch_attack_ignores_armor_and_shield():
    armor = _armor(armor_bonus=5, max_dex=2)
    shield = _shield(shield_bonus=2)
    defender = _actor(
        stats={"MIG": 10, "AGI": 14, "INS": 10, "hp": 20, "max_hp": 20},
        equipment=EquipmentLoadout(slots={"armor": [armor], "shield": [shield]}),
        inventory=[armor, shield],
    )

    defense = compute_defense_ac(defender, touch_attack=True)

    assert defense.armor_bonus == 0
    assert defense.shield_bonus == 0
    assert defense.total == 12

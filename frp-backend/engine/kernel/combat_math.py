from __future__ import annotations

from random import Random

from engine.kernel.actor import ActorRecord, ItemStack
from engine.kernel.effects import compute_effective_stat

from .combat_types import AttackRoll, DefenseProfile, RoundAttackSchedule


def compute_attack_roll(
    attacker: ActorRecord,
    *,
    weapon: ItemStack | None = None,
    d20_roll: int | None = None,
    rng: Random | None = None,
    called_shot: str | None = None,
    flanking: bool = False,
    bab_override: int | None = None,
    situational_bonus: int = 0,
) -> AttackRoll:
    roll = clamp_d20(d20_roll if d20_roll is not None else rng_or_default(rng).randint(1, 20))
    bab = max(0, int(actor_bab(attacker) if bab_override is None else bab_override))
    ability_mod = ability_modifier(attack_stat(attacker, weapon))
    proficiency_bonus = weapon_proficiency_bonus(attacker, weapon)
    effect_bonuses = int(attacker.raw_payload.get("attack_bonus", 0))
    situational = int(situational_bonus)
    if called_shot:
        situational -= 4
    if flanking:
        situational += 2
    total = roll + bab + ability_mod + proficiency_bonus + effect_bonuses + situational
    return AttackRoll(
        d20_natural=roll,
        bab=bab,
        ability_mod=ability_mod,
        proficiency_bonus=proficiency_bonus,
        effect_bonuses=effect_bonuses,
        situational=situational,
        total=total,
        is_natural_one=roll == 1,
        is_natural_twenty=roll == 20,
    )


def compute_defense_ac(
    defender: ActorRecord,
    *,
    flat_footed: bool = False,
    touch_attack: bool = False,
) -> DefenseProfile:
    armor_bonus = 0
    shield_bonus = 0
    armor_max_dex = None
    for slot, items in defender.equipment.slots.items():
        for item in items:
            payload = getattr(item, "payload", {}) or {}
            item_type = str(payload.get("type", "")).strip().lower()
            if slot == "chest":
                armor_bonus += int(item.payload.get("armor_bonus", 0))
                item_max_dex = item.payload.get("max_dex")
                if item_max_dex is not None:
                    armor_max_dex = int(item_max_dex) if armor_max_dex is None else min(armor_max_dex, int(item_max_dex))
            if slot == "off_hand" and item_type == "shield":
                shield_bonus += int(item.payload.get("shield_bonus", 0))
    agi_bonus = 0
    if not flat_footed:
        agi_bonus = ability_modifier(defense_agi_stat(defender))
        if armor_max_dex is not None:
            agi_bonus = min(agi_bonus, armor_max_dex)
    size_mod = int(defender.raw_payload.get("size_mod", 0))
    deflection = int(defender.raw_payload.get("deflection_bonus", 0))
    effect_bonuses = int(defender.raw_payload.get("ac_bonus", 0))
    if touch_attack:
        armor_bonus = 0
        shield_bonus = 0
    total = 10 + armor_bonus + shield_bonus + agi_bonus + size_mod + deflection + effect_bonuses
    return DefenseProfile(
        base=10,
        armor_bonus=armor_bonus,
        shield_bonus=shield_bonus,
        agi_bonus=agi_bonus,
        size_mod=size_mod,
        deflection=deflection,
        effect_bonuses=effect_bonuses,
        total=total,
    )


def compute_attacks_per_round(
    attacker: ActorRecord,
    *,
    dual_wield: bool = False,
    off_hand_light: bool = False,
    haste: bool = False,
) -> RoundAttackSchedule:
    bab = actor_bab(attacker)
    attacks: list[dict[str, int | bool]] = []
    if haste:
        attacks.append({"attack_index": 0, "bab_for_attack": bab, "is_offhand": False, "is_haste": True})
    main_count = 1 + max(0, (max(0, bab) - 1) // 5)
    for index in range(main_count):
        attacks.append(
            {
                "attack_index": len(attacks),
                "bab_for_attack": bab - (index * 5),
                "is_offhand": False,
                "is_haste": False,
            }
        )
    if dual_wield:
        offhand_penalty = 2 if off_hand_light else 4
        attacks.append(
            {
                "attack_index": len(attacks),
                "bab_for_attack": bab - offhand_penalty,
                "is_offhand": True,
                "is_haste": False,
            }
        )
    return RoundAttackSchedule(attacks=attacks)


def rng_or_default(rng: Random | None) -> Random:
    return rng if rng is not None else Random(0)


def clamp_d20(value: int) -> int:
    return max(1, min(20, int(value)))


def stat_value(actor: ActorRecord, *names: str) -> int:
    for name in names:
        if name in actor.stats:
            return int(actor.stats[name])
    return 10


def ability_modifier(value: int) -> int:
    return (int(value) - 10) // 2


def actor_bab(actor: ActorRecord) -> int:
    return max(
        0,
        int(
            actor.raw_payload.get(
                "bab",
                actor.stats.get("BAB", actor.skills.get("bab", actor.raw_payload.get("level", 0))),
            )
        ),
    )


def attack_stat(actor: ActorRecord, weapon: ItemStack | None) -> int:
    """Return the attack ability score: AGI for finesse/ranged, MIG otherwise."""
    use_agi = bool(weapon and (weapon.payload.get("finesse") or weapon.payload.get("ranged")))
    stat_name = "AGI" if use_agi else "MIG"
    if stat_name in actor.stats:
        return compute_effective_stat(actor, stat_name)
    return stat_value(actor, stat_name)


def defense_agi_stat(actor: ActorRecord) -> int:
    """Return the defensive agility score (AGI) for AC calculation."""
    if "AGI" in actor.stats:
        return compute_effective_stat(actor, "AGI")
    return stat_value(actor, "AGI")


def weapon_proficiency_bonus(attacker: ActorRecord, weapon: ItemStack | None) -> int:
    if "weapon_proficiency_bonus" in attacker.raw_payload:
        return int(attacker.raw_payload["weapon_proficiency_bonus"])
    if weapon is not None:
        item_key = str(weapon.item_def_id).lower()
        if item_key in attacker.skills:
            return int(attacker.skills[item_key])
    return int(attacker.skills.get("weapon_proficiency", 0))


def attack_hits(attack_roll: AttackRoll, target_ac: int) -> bool:
    if attack_roll.is_natural_one:
        return False
    if attack_roll.is_natural_twenty:
        return True
    return attack_roll.total >= target_ac


def weapon_threat_min(weapon: ItemStack | None) -> int:
    if weapon is None:
        return 20
    return int(weapon.payload.get("threat_min", 20))


def weapon_crit_multiplier(weapon: ItemStack | None) -> int:
    if weapon is None:
        return 2
    return max(2, int(weapon.payload.get("crit_multiplier", 2)))


def weapon_base_damage(weapon: ItemStack | None) -> int:
    if weapon is None:
        return 1
    return max(1, int(weapon.payload.get("damage", 1)))


__all__ = [
    "ability_modifier",
    "actor_bab",
    "attack_hits",
    "attack_stat",
    "clamp_d20",
    "compute_attack_roll",
    "compute_attacks_per_round",
    "compute_defense_ac",
    "defense_agi_stat",
    "rng_or_default",
    "stat_value",
    "weapon_base_damage",
    "weapon_crit_multiplier",
    "weapon_proficiency_bonus",
    "weapon_threat_min",
]

from __future__ import annotations

from random import Random

from engine.kernel.actor import ActorRecord, ItemStack

from .combat_math import (
    ability_modifier,
    compute_attack_roll,
    compute_attacks_per_round,
    compute_defense_ac,
    rng_or_default,
    stat_value,
    weapon_base_damage,
    weapon_threat_min,
    attack_hits,
    weapon_crit_multiplier,
)
from .combat_types import BloodState, CombatResult, MoraleState, PainState, StrikeResolution
from .combat_wounds import (
    attack_force,
    build_wound,
    choose_hit_part,
    damage_type_for_weapon,
    resolve_armor,
)


def resolve_strike(
    attacker: ActorRecord,
    defender: ActorRecord,
    *,
    weapon: ItemStack | None = None,
    seed: int | None = None,
    raw_damage: int = 0,
    hit: bool = True,
    crit: bool = False,
    explicit_hit_part: str | None = None,
) -> StrikeResolution:
    if not hit or defender.body_state is None:
        return StrikeResolution(hit=False, defender_viable=True)

    rng = Random(seed)
    damage_type = damage_type_for_weapon(weapon)
    hit_part_id = explicit_hit_part or choose_hit_part(defender.body_state, rng)
    total_force = attack_force(attacker, weapon, raw_damage=raw_damage, crit=crit, damage_type=damage_type)
    armor_interactions, equipment_wear, armor_absorbed = resolve_armor(
        defender.equipment,
        hit_part_id,
        total_force,
        rng,
    )
    remaining_force = max(0, total_force - armor_absorbed)
    effective_damage = max(1, int(round(remaining_force / 55.0))) if remaining_force > 0 else 0
    wound = build_wound(
        defender.body_state,
        hit_part_id,
        damage_type=damage_type,
        effective_damage=effective_damage,
        attack_force=remaining_force,
        source_item_id=weapon.instance_id if weapon is not None else None,
    )
    if wound is not None:
        defender.body_state.apply_wound(wound)
    return StrikeResolution(
        hit=True,
        hit_part_id=hit_part_id,
        damage_type=damage_type,
        attack_force=total_force,
        armor_absorbed=armor_absorbed,
        effective_damage=effective_damage,
        wound=wound,
        armor_interactions=armor_interactions,
        equipment_wear=equipment_wear,
        defender_viable=defender.body_state.is_viable(),
        blood_loss_rate=defender.body_state.blood_loss_rate(),
        total_pain=defender.body_state.total_pain(),
    )


def resolve_attack(
    attacker: ActorRecord,
    defender: ActorRecord,
    *,
    weapon: ItemStack | None = None,
    seed: int | None = None,
    called_shot: str | None = None,
    flanking: bool = False,
    backstab: bool = False,
    flat_footed: bool = False,
    raw_damage: int = 0,
    d20_roll: int | None = None,
    confirm_roll: int | None = None,
    bab_override: int | None = None,
    strike_resolver=None,
) -> CombatResult:
    rng = Random(seed) if seed is not None else Random(0)
    if defender.body_state is None:
        attack_roll = compute_attack_roll(attacker, weapon=weapon, d20_roll=d20_roll, rng=rng, called_shot=called_shot, flanking=flanking, bab_override=bab_override)
        defense = compute_defense_ac(defender, flat_footed=flat_footed)
        return CombatResult(attack_roll=attack_roll, defense=defense, hit=False, events=[{"type": "missing_body_state"}])
    if called_shot and called_shot not in defender.body_state.parts:
        raise ValueError(f"Unknown called shot `{called_shot}`")

    attack_roll = compute_attack_roll(
        attacker,
        weapon=weapon,
        d20_roll=d20_roll,
        rng=rng,
        called_shot=called_shot,
        flanking=flanking,
        bab_override=bab_override,
    )
    defense = compute_defense_ac(defender, flat_footed=flat_footed)
    hit = attack_hits(attack_roll, defense.total)
    events: list[dict[str, Any]] = []
    if not hit:
        return CombatResult(attack_roll=attack_roll, defense=defense, hit=False, events=events)

    critical_threatened = attack_roll.is_natural_twenty or attack_roll.d20_natural >= weapon_threat_min(weapon)
    critical_confirmed = False
    if critical_threatened:
        confirm = compute_attack_roll(
            attacker,
            weapon=weapon,
            d20_roll=confirm_roll,
            rng=rng,
            called_shot=called_shot,
            flanking=flanking,
            bab_override=bab_override,
        )
        critical_confirmed = attack_hits(confirm, defense.total)

    adjusted_damage = max(1, int(raw_damage or weapon_base_damage(weapon)))
    backstab_applied = False
    backstab_level = int(attacker.raw_payload.get("backstab_level", 1))
    if backstab and (flanking or flat_footed or bool(defender.raw_payload.get("unaware"))):
        extra_damage = max(0, backstab_level * weapon_base_damage(weapon))
        if extra_damage > 0:
            adjusted_damage += extra_damage
            backstab_applied = True
            events.append({"type": "backstab", "extra_damage": extra_damage})

    if critical_confirmed:
        adjusted_damage *= weapon_crit_multiplier(weapon)

    strike_seed = rng.randint(1, 2_147_483_647) if seed is not None else None
    chosen_strike_resolver = strike_resolver or resolve_strike
    strike_resolution = chosen_strike_resolver(
        attacker,
        defender,
        weapon=weapon,
        seed=strike_seed,
        raw_damage=adjusted_damage,
        hit=True,
        crit=critical_confirmed,
        explicit_hit_part=called_shot,
    )

    pain_state = PainState(
        current_pain=float(defender.body_state.total_pain()),
        base_max_pain=float(defender.raw_payload.get("base_max_pain", 100.0)),
        willpower_modifier=float(defender.raw_payload.get("willpower_modifier", 0.0)),
        toughness_modifier=float(defender.raw_payload.get("toughness_modifier", 0.0)),
    )
    blood_state = BloodState(
        blood_count=int(defender.raw_payload.get("blood_count", 5000)),
        max_blood=int(defender.raw_payload.get("max_blood", 5000)),
    )
    pain_report = tick_pain(defender, pain_state)
    blood_report = tick_blood_loss(defender, blood_state)
    morale_check = None
    if strike_resolution.wound is not None:
        morale_state = MoraleState(
            base_morale=int(defender.raw_payload.get("morale_bonus", ability_modifier(stat_value(defender, "WIS", "INS")))),
            leadership_bonus=int(defender.raw_payload.get("leadership_bonus", 0)),
            trait_bonus=int(defender.raw_payload.get("trait_bonus", 0)),
        )
        morale_check = check_morale(defender, morale_state, "first_wound", d20_roll=int(defender.raw_payload.get("morale_roll", 10)))
        if morale_check["passed"] is False:
            events.append({"type": "morale_failed", "trigger": "first_wound"})

    incapacitation = apply_incapacitation(defender, strike_resolution, pain_state, blood_state, events)
    if pain_report["unconscious"] or pain_report["dead"]:
        events.append({"type": "pain_state", **pain_report})
    if blood_report["unconscious"] or blood_report["dead"]:
        events.append({"type": "blood_state", **blood_report})
    return CombatResult(
        attack_roll=attack_roll,
        defense=defense,
        hit=True,
        critical_threatened=critical_threatened,
        critical_confirmed=critical_confirmed,
        backstab_applied=backstab_applied,
        backstab_multiplier=max(1, backstab_level),
        strike_resolution=strike_resolution,
        pain_state_after=pain_state,
        blood_state_after=blood_state,
        morale_check=morale_check,
        incapacitation=incapacitation,
        events=events,
    )


def resolve_combat_round(
    attacker: ActorRecord,
    defender: ActorRecord,
    *,
    weapon: ItemStack | None = None,
    off_hand_weapon: ItemStack | None = None,
    seed: int | None = None,
    flanking: bool = False,
    backstab_first_only: bool = False,
    flat_footed: bool = False,
    attack_resolver=None,
) -> list[CombatResult]:
    rng = Random(seed) if seed is not None else Random(0)
    schedule = compute_attacks_per_round(
        attacker,
        dual_wield=off_hand_weapon is not None,
        off_hand_light=bool(off_hand_weapon and off_hand_weapon.payload.get("light")),
        haste=bool(attacker.effect_queue and attacker.effect_queue.has_condition("haste")),
    )
    results: list[CombatResult] = []
    chosen_attack_resolver = attack_resolver or resolve_attack
    for index, attack in enumerate(schedule.attacks):
        current_weapon = off_hand_weapon if attack["is_offhand"] else weapon
        result = chosen_attack_resolver(
            attacker,
            defender,
            weapon=current_weapon,
            seed=rng.randint(1, 2_147_483_647),
            flanking=flanking,
            backstab=flanking and (not backstab_first_only or index == 0),
            flat_footed=flat_footed,
            raw_damage=weapon_base_damage(current_weapon),
            bab_override=int(attack["bab_for_attack"]),
        )
        results.append(result)
        if result.incapacitation in {"unconscious", "dead"}:
            break
    return results


def check_morale(
    actor: ActorRecord,
    morale_state: MoraleState,
    trigger: str,
    d20_roll: int | None = None,
    rng: Random | None = None,
) -> dict[str, Any]:
    dc = {"first_wound": 10, "ally_death": 15, "hp_below_50": 15, "outnumbered": 20}.get(trigger, 10)
    roll = rng_or_default(rng).randint(1, 20) if d20_roll is None else max(1, min(20, int(d20_roll)))
    total = roll + morale_state.morale_bonus
    passed = total >= dc
    if not passed:
        morale_state.fleeing = True
        morale_state.checks_failed += 1
    return {"triggered": True, "trigger": trigger, "dc": dc, "roll": roll, "total": total, "passed": passed}


def tick_blood_loss(actor: ActorRecord, blood_state: BloodState) -> dict[str, Any]:
    drained = actor.body_state.blood_loss_rate() if actor.body_state is not None else 0
    blood_state.drain(drained)
    actor.raw_payload["blood_count"] = blood_state.blood_count
    return {
        "drained": drained,
        "new_blood": blood_state.blood_count,
        "dizzy": blood_state.is_dizzy,
        "unconscious": blood_state.is_unconscious,
        "dead": blood_state.is_dead,
    }


def tick_pain(actor: ActorRecord, pain_state: PainState) -> dict[str, Any]:
    total_pain = float(actor.body_state.total_pain() if actor.body_state is not None else 0.0)
    pain_state.current_pain = max(0.0, total_pain)
    return {
        "total_pain": pain_state.current_pain,
        "pain_ratio": pain_state.pain_ratio,
        "stunned": pain_state.is_stunned,
        "unconscious": pain_state.is_unconscious,
        "dead": pain_state.is_dead_from_shock,
    }


def apply_incapacitation(
    defender: ActorRecord,
    strike_resolution: StrikeResolution,
    pain_state: PainState,
    blood_state: BloodState,
    events: list[dict[str, Any]],
) -> str | None:
    outcome = None
    if pain_state.is_dead_from_shock or blood_state.is_dead:
        outcome = "dead"
    elif pain_state.is_unconscious or blood_state.is_unconscious:
        outcome = "unconscious"
    elif pain_state.is_stunned or blood_state.is_dizzy:
        outcome = "stunned"

    if outcome == "stunned":
        defender.raw_payload["can_act"] = False
        defender.raw_payload["movement_multiplier"] = 0.5
        events.append({"type": "stunned"})
    elif outcome == "unconscious":
        defender.raw_payload["prone"] = True
        defender.raw_payload["can_act"] = False
        dropped: list[str] = []
        for slot in ("weapon", "main_hand", "off_hand"):
            items = defender.equipment.slots.get(slot, [])
            if not items:
                continue
            dropped.extend(item.instance_id for item in items)
            defender.equipment.slots[slot] = []
        defender.raw_payload["dropped_items"] = dropped
        events.append({"type": "unconscious"})
    elif outcome == "dead":
        defender.alive = False
        defender.raw_payload["prone"] = True
        defender.raw_payload["can_act"] = False
        events.append({"type": "death"})
    return outcome


__all__ = [
    "apply_incapacitation",
    "check_morale",
    "resolve_attack",
    "resolve_combat_round",
    "resolve_strike",
    "tick_blood_loss",
    "tick_pain",
]

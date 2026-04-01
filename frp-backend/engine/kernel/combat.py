from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Any

from engine.kernel.actor import (
    ActorRecord,
    BodyState,
    EquipmentLoadout,
    ItemStack,
    MaterialDef,
    WoundRecord,
)
from engine.kernel.common import serialize_value
from engine.kernel.effects import compute_effective_stat
from engine.world.materials import MATERIALS


QUALITY_MULTIPLIERS = {
    0: 1.0,
    1: 1.2,
    2: 1.4,
    3: 1.6,
    4: 1.8,
    5: 2.0,
    6: 3.0,
}
EDGE_DAMAGE_TYPES = {"slash", "slashing", "pierce", "piercing", "cut", "stab", "edge"}
BLUNT_DAMAGE_TYPES = {"bludgeoning", "blunt", "impact", "smash", "bash"}


@dataclass
class ArmorInteraction:
    slot: str
    item_instance_id: str
    item_name: str
    engaged: bool
    absorbed: int
    coverage_roll: int
    quality_multiplier: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "item_instance_id": self.item_instance_id,
            "item_name": self.item_name,
            "engaged": self.engaged,
            "absorbed": self.absorbed,
            "coverage_roll": self.coverage_roll,
            "quality_multiplier": self.quality_multiplier,
        }


@dataclass
class EquipmentWearUpdate:
    slot: str
    item_instance_id: str
    wear_delta: int
    new_wear: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "item_instance_id": self.item_instance_id,
            "wear_delta": self.wear_delta,
            "new_wear": self.new_wear,
        }


@dataclass
class StrikeResolution:
    hit: bool
    hit_part_id: str | None = None
    damage_type: str = "bludgeoning"
    attack_force: int = 0
    armor_absorbed: int = 0
    effective_damage: int = 0
    wound: WoundRecord | None = None
    armor_interactions: list[ArmorInteraction] = field(default_factory=list)
    equipment_wear: list[EquipmentWearUpdate] = field(default_factory=list)
    defender_viable: bool = True
    blood_loss_rate: int = 0
    total_pain: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hit": self.hit,
            "hit_part_id": self.hit_part_id,
            "damage_type": self.damage_type,
            "attack_force": self.attack_force,
            "armor_absorbed": self.armor_absorbed,
            "effective_damage": self.effective_damage,
            "wound": self.wound.to_dict() if self.wound is not None else None,
            "armor_interactions": [item.to_dict() for item in self.armor_interactions],
            "equipment_wear": [item.to_dict() for item in self.equipment_wear],
            "defender_viable": self.defender_viable,
            "blood_loss_rate": self.blood_loss_rate,
            "total_pain": self.total_pain,
        }


@dataclass
class AttackRoll:
    d20_natural: int
    bab: int
    ability_mod: int
    proficiency_bonus: int
    effect_bonuses: int
    situational: int
    total: int
    is_natural_one: bool
    is_natural_twenty: bool

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class DefenseProfile:
    base: int = 10
    armor_bonus: int = 0
    shield_bonus: int = 0
    dex_bonus: int = 0
    size_mod: int = 0
    deflection: int = 0
    effect_bonuses: int = 0
    total: int = 10

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class PainState:
    current_pain: float = 0.0
    base_max_pain: float = 100.0
    willpower_modifier: float = 0.0
    toughness_modifier: float = 0.0

    @property
    def max_pain(self) -> float:
        return self.base_max_pain * (1.0 + self.toughness_modifier)

    @property
    def effective_pain(self) -> float:
        return self.current_pain * (1.0 - self.willpower_modifier)

    @property
    def pain_ratio(self) -> float:
        max_pain = self.max_pain
        return self.effective_pain / max_pain if max_pain > 0 else 0.0

    @property
    def is_stunned(self) -> bool:
        return self.pain_ratio >= 0.5

    @property
    def is_unconscious(self) -> bool:
        return self.pain_ratio >= 0.8

    @property
    def is_dead_from_shock(self) -> bool:
        return self.pain_ratio >= 1.2

    def add_pain(self, amount: float) -> None:
        self.current_pain = max(0.0, self.current_pain + max(0.0, amount))

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PainState":
        return cls(**data)


@dataclass
class BloodState:
    blood_count: int = 5000
    max_blood: int = 5000

    @property
    def is_dizzy(self) -> bool:
        return self.blood_count <= self.max_blood * 0.7

    @property
    def is_unconscious(self) -> bool:
        return self.blood_count <= self.max_blood * 0.5

    @property
    def is_dead(self) -> bool:
        return self.blood_count <= 0

    def drain(self, amount: int) -> None:
        self.blood_count = max(0, int(self.blood_count) - max(0, int(amount)))

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BloodState":
        return cls(**data)


@dataclass
class MoraleState:
    base_morale: int = 10
    leadership_bonus: int = 0
    trait_bonus: int = 0
    fleeing: bool = False
    checks_failed: int = 0

    @property
    def morale_bonus(self) -> int:
        return self.base_morale + self.leadership_bonus + self.trait_bonus

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MoraleState":
        return cls(**data)


@dataclass
class RoundAttackSchedule:
    attacks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class CombatResult:
    attack_roll: AttackRoll
    defense: DefenseProfile
    hit: bool
    critical_threatened: bool = False
    critical_confirmed: bool = False
    backstab_applied: bool = False
    backstab_multiplier: int = 1
    strike_resolution: StrikeResolution | None = None
    pain_state_after: PainState | None = None
    blood_state_after: BloodState | None = None
    morale_check: dict[str, Any] | None = None
    incapacitation: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attack_roll": self.attack_roll.to_dict(),
            "defense": self.defense.to_dict(),
            "hit": self.hit,
            "critical_threatened": self.critical_threatened,
            "critical_confirmed": self.critical_confirmed,
            "backstab_applied": self.backstab_applied,
            "backstab_multiplier": self.backstab_multiplier,
            "strike_resolution": self.strike_resolution.to_dict() if self.strike_resolution else None,
            "pain_state_after": self.pain_state_after.to_dict() if self.pain_state_after else None,
            "blood_state_after": self.blood_state_after.to_dict() if self.blood_state_after else None,
            "morale_check": dict(self.morale_check or {}),
            "incapacitation": self.incapacitation,
            "events": [dict(event) for event in self.events],
        }


def material_def_from_legacy_name(material_name: str | None) -> MaterialDef:
    material_id = str(material_name or "iron").lower()
    legacy = MATERIALS.get(material_id, MATERIALS["iron"])
    hardness = max(1.0, float(legacy.hardness))
    density = max(0.25, float(legacy.density))
    return MaterialDef(
        material_id=material_id,
        label=material_id.replace("_", " ").title(),
        category="material",
        density=int(density * 1000),
        impact_yield=int(40 + hardness * 35),
        impact_fracture=int(80 + hardness * 70),
        shear_yield=int(35 + hardness * 30),
        shear_fracture=int(70 + hardness * 60),
        max_edge=int(40 + legacy.damage_mult * 60),
        tags=["legacy_material"],
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
    damage_type = _damage_type_for_weapon(weapon)
    hit_part_id = explicit_hit_part or _choose_hit_part(defender.body_state, rng)
    attack_force = _attack_force(attacker, weapon, raw_damage=raw_damage, crit=crit, damage_type=damage_type)
    remaining_force = attack_force
    armor_interactions, equipment_wear, armor_absorbed = _resolve_armor(
        defender.equipment,
        hit_part_id,
        remaining_force,
        rng,
    )
    remaining_force = max(0, remaining_force - armor_absorbed)
    effective_damage = max(1, int(round(remaining_force / 55.0))) if remaining_force > 0 else 0
    wound = _build_wound(
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
        attack_force=attack_force,
        armor_absorbed=armor_absorbed,
        effective_damage=effective_damage,
        wound=wound,
        armor_interactions=armor_interactions,
        equipment_wear=equipment_wear,
        defender_viable=defender.body_state.is_viable(),
        blood_loss_rate=defender.body_state.blood_loss_rate(),
        total_pain=defender.body_state.total_pain(),
    )


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
    roll = _clamp_d20(d20_roll if d20_roll is not None else _rng(rng).randint(1, 20))
    bab = max(0, int(_actor_bab(attacker) if bab_override is None else bab_override))
    ability_mod = _ability_modifier(_attack_stat(attacker, weapon))
    proficiency_bonus = _weapon_proficiency_bonus(attacker, weapon)
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
            if slot == "armor":
                armor_bonus += int(item.payload.get("armor_bonus", 0))
                item_max_dex = item.payload.get("max_dex")
                if item_max_dex is not None:
                    armor_max_dex = int(item_max_dex) if armor_max_dex is None else min(armor_max_dex, int(item_max_dex))
            if slot == "shield":
                shield_bonus += int(item.payload.get("shield_bonus", 0))
    dex_bonus = 0
    if not flat_footed:
        dex_bonus = _ability_modifier(_defense_dex_stat(defender))
        if armor_max_dex is not None:
            dex_bonus = min(dex_bonus, armor_max_dex)
    size_mod = int(defender.raw_payload.get("size_mod", 0))
    deflection = int(defender.raw_payload.get("deflection_bonus", 0))
    effect_bonuses = int(defender.raw_payload.get("ac_bonus", 0))
    if touch_attack:
        armor_bonus = 0
        shield_bonus = 0
    total = 10 + armor_bonus + shield_bonus + dex_bonus + size_mod + deflection + effect_bonuses
    return DefenseProfile(
        base=10,
        armor_bonus=armor_bonus,
        shield_bonus=shield_bonus,
        dex_bonus=dex_bonus,
        size_mod=size_mod,
        deflection=deflection,
        effect_bonuses=effect_bonuses,
        total=total,
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
    hit = _attack_hits(attack_roll, defense.total)
    events: list[dict[str, Any]] = []
    if not hit:
        return CombatResult(attack_roll=attack_roll, defense=defense, hit=False, events=events)

    critical_threatened = attack_roll.is_natural_twenty or attack_roll.d20_natural >= _weapon_threat_min(weapon)
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
        critical_confirmed = _attack_hits(confirm, defense.total)

    adjusted_damage = max(1, int(raw_damage or _weapon_base_damage(weapon)))
    backstab_applied = False
    backstab_level = int(attacker.raw_payload.get("backstab_level", 1))
    if backstab and (flanking or flat_footed or bool(defender.raw_payload.get("unaware"))):
        extra_damage = max(0, backstab_level * _weapon_base_damage(weapon))
        if extra_damage > 0:
            adjusted_damage += extra_damage
            backstab_applied = True
            events.append({"type": "backstab", "extra_damage": extra_damage})

    if critical_confirmed:
        adjusted_damage *= _weapon_crit_multiplier(weapon)

    strike_seed = rng.randint(1, 2_147_483_647) if seed is not None else None
    strike_resolution = resolve_strike(
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
            base_morale=int(defender.raw_payload.get("morale_bonus", _ability_modifier(_stat_value(defender, "WIS", "INS")))),
            leadership_bonus=int(defender.raw_payload.get("leadership_bonus", 0)),
            trait_bonus=int(defender.raw_payload.get("trait_bonus", 0)),
        )
        morale_check = check_morale(defender, morale_state, "first_wound", d20_roll=int(defender.raw_payload.get("morale_roll", 10)))
        if morale_check["passed"] is False:
            events.append({"type": "morale_failed", "trigger": "first_wound"})

    incapacitation = _apply_incapacitation(defender, strike_resolution, pain_state, blood_state, events)
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


def compute_attacks_per_round(
    attacker: ActorRecord,
    *,
    dual_wield: bool = False,
    off_hand_light: bool = False,
    haste: bool = False,
) -> RoundAttackSchedule:
    bab = _actor_bab(attacker)
    attacks: list[dict[str, Any]] = []
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
) -> list[CombatResult]:
    rng = Random(seed) if seed is not None else Random(0)
    schedule = compute_attacks_per_round(
        attacker,
        dual_wield=off_hand_weapon is not None,
        off_hand_light=bool(off_hand_weapon and off_hand_weapon.payload.get("light")),
        haste=bool(attacker.effect_queue and attacker.effect_queue.has_condition("haste")),
    )
    results: list[CombatResult] = []
    for index, attack in enumerate(schedule.attacks):
        current_weapon = off_hand_weapon if attack["is_offhand"] else weapon
        result = resolve_attack(
            attacker,
            defender,
            weapon=current_weapon,
            seed=rng.randint(1, 2_147_483_647),
            flanking=flanking,
            backstab=flanking and (not backstab_first_only or index == 0),
            flat_footed=flat_footed,
            raw_damage=_weapon_base_damage(current_weapon),
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
    roll = _clamp_d20(d20_roll if d20_roll is not None else _rng(rng).randint(1, 20))
    total = roll + morale_state.morale_bonus
    passed = total >= dc
    if not passed:
        morale_state.fleeing = True
        morale_state.checks_failed += 1
    return {"triggered": True, "trigger": trigger, "dc": dc, "roll": roll, "total": total, "passed": passed}


def tick_blood_loss(
    actor: ActorRecord,
    blood_state: BloodState,
) -> dict[str, Any]:
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


def tick_pain(
    actor: ActorRecord,
    pain_state: PainState,
) -> dict[str, Any]:
    total_pain = float(actor.body_state.total_pain() if actor.body_state is not None else 0.0)
    pain_state.current_pain = max(0.0, total_pain)
    return {
        "total_pain": pain_state.current_pain,
        "pain_ratio": pain_state.pain_ratio,
        "stunned": pain_state.is_stunned,
        "unconscious": pain_state.is_unconscious,
        "dead": pain_state.is_dead_from_shock,
    }


def _choose_hit_part(body_state: BodyState, rng: Random) -> str:
    weighted_parts: list[tuple[str, int]] = []
    for part in body_state.plan.parts:
        weighted_parts.append((part.part_id, max(1, int(part.relative_size))))
    total = sum(weight for _, weight in weighted_parts)
    roll = rng.randint(1, total)
    running = 0
    for part_id, weight in weighted_parts:
        running += weight
        if roll <= running:
            return part_id
    return weighted_parts[0][0]


def _damage_type_for_weapon(weapon: ItemStack | None) -> str:
    if weapon is None:
        return "bludgeoning"
    damage_type = str(weapon.payload.get("damage_type", "")).strip().lower()
    if damage_type:
        return damage_type
    item_id = str(weapon.item_def_id).lower()
    if any(token in item_id for token in ("sword", "knife", "spear", "dagger", "rapier")):
        return "slashing"
    if any(token in item_id for token in ("hammer", "club", "mace", "staff")):
        return "bludgeoning"
    return "bludgeoning"


def _attack_force(
    attacker: ActorRecord,
    weapon: ItemStack | None,
    *,
    raw_damage: int,
    crit: bool,
    damage_type: str,
) -> int:
    base_damage = max(1, int(raw_damage))
    mig = int(attacker.stats.get("MIG", attacker.stats.get("strength", 10)))
    agi = int(attacker.stats.get("AGI", attacker.stats.get("agility", 10)))
    melee_skill = int(attacker.skills.get("melee", attacker.skills.get("sword", attacker.skills.get("axe", 0))))
    stat_bonus = max(0, (mig - 10) // 2)
    velocity = 100 + (agi - 10) * 3 + melee_skill * 4 + (20 if crit else 0)
    size = max(4, int(weapon.payload.get("damage", base_damage)) if weapon is not None else base_damage)
    material = material_def_from_legacy_name(weapon.material_id if weapon is not None else "bone")
    quality = QUALITY_MULTIPLIERS.get(int(weapon.quality), 1.0) if weapon is not None else 1.0
    if damage_type in EDGE_DAMAGE_TYPES:
        sharpness = int((weapon.sharpness if weapon is not None else 80) * material.max_edge / 100)
        return int((base_damage + stat_bonus + melee_skill + size) * quality * max(50, sharpness) * velocity / 850)
    density_bonus = max(1, material.density // 250)
    return int((base_damage + stat_bonus + melee_skill + density_bonus) * quality * velocity / 18)


def _resolve_armor(
    equipment: EquipmentLoadout,
    hit_part_id: str,
    attack_force: int,
    rng: Random,
) -> tuple[list[ArmorInteraction], list[EquipmentWearUpdate], int]:
    interactions: list[ArmorInteraction] = []
    wear_updates: list[EquipmentWearUpdate] = []
    absorbed_total = 0
    remaining_force = attack_force
    for slot, item in equipment.covering_items(hit_part_id):
        coverage = int(item.payload.get("coverage_percentage", 100))
        roll = rng.randint(1, 100)
        engaged = roll <= max(1, coverage)
        quality = QUALITY_MULTIPLIERS.get(int(item.quality), 1.0)
        absorbed = 0
        if engaged:
            material = material_def_from_legacy_name(item.material_id or item.payload.get("material_id"))
            armor_score = max(1, int(round((material.impact_fracture / 22.0) * quality)))
            absorbed = min(max(0, remaining_force // 10), armor_score)
            remaining_force = max(0, remaining_force - absorbed)
            wear_delta = max(0, int(round(max(0, absorbed) / 8.0)))
            if wear_delta > 0:
                item.wear += wear_delta
                wear_updates.append(
                    EquipmentWearUpdate(
                        slot=slot,
                        item_instance_id=item.instance_id,
                        wear_delta=wear_delta,
                        new_wear=item.wear,
                    )
                )
        interactions.append(
            ArmorInteraction(
                slot=slot,
                item_instance_id=item.instance_id,
                item_name=str(item.payload.get("name", item.item_def_id)),
                engaged=engaged,
                absorbed=absorbed,
                coverage_roll=roll,
                quality_multiplier=quality,
            )
        )
        absorbed_total += absorbed
        if remaining_force <= 0:
            break
    return interactions, wear_updates, absorbed_total


def _build_wound(
    body_state: BodyState,
    hit_part_id: str,
    *,
    damage_type: str,
    effective_damage: int,
    attack_force: int,
    source_item_id: str | None,
) -> WoundRecord | None:
    if effective_damage <= 0:
        return None
    part_def = body_state.part_def(hit_part_id)
    remaining_force = attack_force
    layer_hits: list[str] = []
    under_pressure_hit = False
    vital_hit = False
    structural_hit = False
    for layer in part_def.layers:
        threshold = _layer_threshold(layer.material_id, damage_type, layer.relative_thickness)
        if remaining_force < threshold:
            break
        layer_hits.append(layer.layer_id)
        remaining_force = max(0, remaining_force - threshold)
        under_pressure_hit = under_pressure_hit or layer.under_pressure
        vital_hit = vital_hit or layer.vital or (part_def.vital and layer.layer_id in {"brain", "artery", "lungs", "organs"})
        structural_hit = structural_hit or layer.structural
    open_wound = damage_type in EDGE_DAMAGE_TYPES or effective_damage >= 4
    fracture = structural_hit and (damage_type in BLUNT_DAMAGE_TYPES or effective_damage >= max(6, part_def.max_hp // 2))
    crippled = effective_damage >= max(4, part_def.max_hp // 2)
    bleeding = 0
    if open_wound:
        bleeding = max(1, effective_damage // 3)
        if under_pressure_hit:
            bleeding += 2
    pain = max(1, effective_damage * 2)
    if vital_hit:
        pain += 2
    return WoundRecord(
        wound_id=f"wound_{hit_part_id}_{len(body_state.wounds) + 1}",
        body_part_id=hit_part_id,
        damage_type=damage_type,
        damage_amount=effective_damage,
        bleeding=bleeding,
        pain=pain,
        open_wound=open_wound,
        infected=False,
        untreated=open_wound,
        fracture=fracture,
        crippled=crippled,
        vital=part_def.vital or vital_hit,
        attack_force=attack_force,
        source_item_id=source_item_id,
        layer_hits=layer_hits,
        tags=_wound_tags(part_def.part_id, fracture=fracture, vital=vital_hit, open_wound=open_wound),
    )


def _layer_threshold(material_id: str, damage_type: str, thickness: int) -> int:
    material = material_def_from_legacy_name(material_id)
    reference = material.shear_yield if damage_type in EDGE_DAMAGE_TYPES else material.impact_yield
    return max(20, int(reference) * max(1, int(thickness)))


def _wound_tags(part_id: str, *, fracture: bool, vital: bool, open_wound: bool) -> list[str]:
    tags: list[str] = [part_id]
    if fracture:
        tags.append("fracture")
    if vital:
        tags.append("vital")
    if open_wound:
        tags.append("open_wound")
    if "leg" in part_id:
        tags.append("mobility_risk")
    return tags


def _rng(rng: Random | None) -> Random:
    return rng if rng is not None else Random(0)


def _clamp_d20(value: int) -> int:
    return max(1, min(20, int(value)))


def _stat_value(actor: ActorRecord, *names: str) -> int:
    for name in names:
        if name in actor.stats:
            return int(actor.stats[name])
    return 10


def _ability_modifier(value: int) -> int:
    return (int(value) - 10) // 2


def _actor_bab(actor: ActorRecord) -> int:
    return max(
        0,
        int(
            actor.raw_payload.get(
                "bab",
                actor.stats.get("BAB", actor.skills.get("bab", actor.raw_payload.get("level", 0))),
            )
        ),
    )


def _attack_stat(actor: ActorRecord, weapon: ItemStack | None) -> int:
    use_dex = bool(weapon and (weapon.payload.get("finesse") or weapon.payload.get("ranged")))
    stat_name = "DEX" if use_dex else "STR"
    if stat_name in actor.stats:
        return compute_effective_stat(actor, stat_name)
    fallback = ("AGI",) if use_dex else ("MIG",)
    return _stat_value(actor, stat_name, *fallback)


def _defense_dex_stat(actor: ActorRecord) -> int:
    if "DEX" in actor.stats:
        return compute_effective_stat(actor, "DEX")
    return _stat_value(actor, "AGI", "DEX")


def _weapon_proficiency_bonus(attacker: ActorRecord, weapon: ItemStack | None) -> int:
    if "weapon_proficiency_bonus" in attacker.raw_payload:
        return int(attacker.raw_payload["weapon_proficiency_bonus"])
    if weapon is not None:
        item_key = str(weapon.item_def_id).lower()
        if item_key in attacker.skills:
            return int(attacker.skills[item_key])
    return int(attacker.skills.get("weapon_proficiency", 0))


def _attack_hits(attack_roll: AttackRoll, target_ac: int) -> bool:
    if attack_roll.is_natural_one:
        return False
    if attack_roll.is_natural_twenty:
        return True
    return attack_roll.total >= target_ac


def _weapon_threat_min(weapon: ItemStack | None) -> int:
    if weapon is None:
        return 20
    return int(weapon.payload.get("threat_min", 20))


def _weapon_crit_multiplier(weapon: ItemStack | None) -> int:
    if weapon is None:
        return 2
    return max(2, int(weapon.payload.get("crit_multiplier", 2)))


def _weapon_base_damage(weapon: ItemStack | None) -> int:
    if weapon is None:
        return 1
    return max(1, int(weapon.payload.get("damage", 1)))


def _apply_incapacitation(
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

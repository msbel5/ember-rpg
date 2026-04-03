from .combat_math import (
    ability_modifier,
    actor_bab,
    attack_hits,
    attack_stat,
    clamp_d20,
    compute_attack_roll,
    compute_attacks_per_round,
    compute_defense_ac,
    defense_agi_stat,
    rng_or_default,
    stat_value,
    weapon_base_damage,
    weapon_crit_multiplier,
    weapon_proficiency_bonus,
    weapon_threat_min,
)
from .combat_resolution import (
    apply_incapacitation,
    check_morale,
    resolve_attack as _resolve_attack_impl,
    resolve_combat_round as _resolve_combat_round_impl,
    resolve_strike as _resolve_strike_impl,
    tick_blood_loss,
    tick_pain,
)
from .combat_wounds import (
    attack_force,
    build_wound,
    choose_hit_part,
    damage_type_for_weapon,
    layer_threshold,
    resolve_armor,
    wound_tags,
)
from .combat_types import (
    ArmorInteraction,
    AttackRoll,
    BLUNT_DAMAGE_TYPES,
    BloodState,
    CombatResult,
    DefenseProfile,
    EDGE_DAMAGE_TYPES,
    EquipmentWearUpdate,
    MoraleState,
    PainState,
    QUALITY_MULTIPLIERS,
    RoundAttackSchedule,
    StrikeResolution,
    material_def_from_legacy_name,
)

resolve_strike = _resolve_strike_impl


def resolve_attack(*args, **kwargs):
    return _resolve_attack_impl(*args, strike_resolver=resolve_strike, **kwargs)


def resolve_combat_round(*args, **kwargs):
    return _resolve_combat_round_impl(*args, attack_resolver=resolve_attack, **kwargs)

__all__ = [
    "ArmorInteraction",
    "AttackRoll",
    "BLUNT_DAMAGE_TYPES",
    "BloodState",
    "CombatResult",
    "DefenseProfile",
    "EDGE_DAMAGE_TYPES",
    "EquipmentWearUpdate",
    "MoraleState",
    "PainState",
    "QUALITY_MULTIPLIERS",
    "RoundAttackSchedule",
    "StrikeResolution",
    "ability_modifier",
    "actor_bab",
    "apply_incapacitation",
    "attack_force",
    "attack_hits",
    "attack_stat",
    "build_wound",
    "check_morale",
    "choose_hit_part",
    "clamp_d20",
    "compute_attack_roll",
    "compute_attacks_per_round",
    "compute_defense_ac",
    "damage_type_for_weapon",
    "defense_agi_stat",
    "layer_threshold",
    "material_def_from_legacy_name",
    "resolve_armor",
    "resolve_attack",
    "resolve_combat_round",
    "resolve_strike",
    "rng_or_default",
    "stat_value",
    "tick_blood_loss",
    "tick_pain",
    "weapon_base_damage",
    "weapon_crit_multiplier",
    "weapon_proficiency_bonus",
    "weapon_threat_min",
    "wound_tags",
]

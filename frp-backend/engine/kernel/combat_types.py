from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import MaterialDef, WoundRecord
from engine.kernel.common import serialize_value
from engine.kernel.data_loader import load_quality_tiers
from engine.world.materials import MATERIALS

# Loaded from data/quality_tiers.json -- no hardcoded game constants.
QUALITY_MULTIPLIERS: dict[int, float] = load_quality_tiers()
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
    "material_def_from_legacy_name",
]

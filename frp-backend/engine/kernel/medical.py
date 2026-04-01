from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from engine.kernel.actor import ActorRecord, ConditionRecord, WoundRecord
from engine.kernel.common import serialize_value


logger = logging.getLogger(__name__)


class TreatmentStep(IntEnum):
    DIAGNOSIS = 0
    CLEAN = 1
    SUTURE = 2
    DRESS_WOUND = 3
    SET_BONE = 4
    SURGERY = 5


@dataclass
class TreatmentRequirement:
    step: TreatmentStep
    required_skill: str
    min_skill_level: int = 1
    consumed_materials: list[tuple[str, int]] = field(default_factory=list)
    tool_materials: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TreatmentRequirement":
        payload = dict(data)
        payload["step"] = TreatmentStep(payload["step"])
        payload["consumed_materials"] = [
            (str(tag), int(quantity)) for tag, quantity in payload.get("consumed_materials", [])
        ]
        payload["tool_materials"] = [str(tag) for tag in payload.get("tool_materials", [])]
        return cls(**payload)


TREATMENT_REQUIREMENTS: dict[TreatmentStep, TreatmentRequirement] = {
    TreatmentStep.DIAGNOSIS: TreatmentRequirement(TreatmentStep.DIAGNOSIS, "diagnose", 1),
    TreatmentStep.CLEAN: TreatmentRequirement(
        TreatmentStep.CLEAN,
        "",
        0,
        consumed_materials=[("soap", 1), ("water", 1)],
    ),
    TreatmentStep.SUTURE: TreatmentRequirement(
        TreatmentStep.SUTURE,
        "suture",
        1,
        consumed_materials=[("thread", 1)],
    ),
    TreatmentStep.DRESS_WOUND: TreatmentRequirement(
        TreatmentStep.DRESS_WOUND,
        "dress_wound",
        1,
        consumed_materials=[("cloth", 1)],
    ),
    TreatmentStep.SET_BONE: TreatmentRequirement(TreatmentStep.SET_BONE, "set_bone", 1),
    TreatmentStep.SURGERY: TreatmentRequirement(
        TreatmentStep.SURGERY,
        "surgery",
        1,
        tool_materials=["edged_tool"],
    ),
}


@dataclass
class TreatmentRecord:
    wound_id: str
    patient_id: str
    doctor_id: str | None = None
    diagnosed: bool = False
    steps_completed: list[TreatmentStep] = field(default_factory=list)
    steps_remaining: list[TreatmentStep] = field(default_factory=list)
    infection_level: float = 0.0
    infection_rate: float = 1.0
    treatment_quality: float = 0.5
    tick_started: int = 0
    tick_completed: int | None = None

    def is_fully_treated(self) -> bool:
        return len(self.steps_remaining) == 0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TreatmentRecord":
        payload = dict(data)
        payload["steps_completed"] = [TreatmentStep(step) for step in payload.get("steps_completed", [])]
        payload["steps_remaining"] = [TreatmentStep(step) for step in payload.get("steps_remaining", [])]
        return cls(**payload)


@dataclass
class InfectionState:
    wound_id: str
    body_part_id: str
    infection_level: float = 0.0
    cleaned: bool = False
    fever: bool = False
    organ_damage: bool = False
    lethal: bool = False

    def tick_infection(self, ticks_elapsed: int = 1) -> None:
        rate_per_tick = (0.1 if self.cleaned else 1.0) / 100.0
        self.infection_level += rate_per_tick * max(0, int(ticks_elapsed))
        self.fever = self.infection_level >= 50.0
        self.organ_damage = self.infection_level > 80.0
        self.lethal = self.infection_level > 100.0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InfectionState":
        return cls(**data)


@dataclass
class PermanentConsequence:
    consequence_id: str
    kind: str
    body_part_id: str
    description: str
    stat_modifiers: dict[str, int] = field(default_factory=dict)
    mobility_penalty: int = 0
    stress_per_tick: float = 0.0
    permanent: bool = True

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PermanentConsequence":
        payload = dict(data)
        payload["stat_modifiers"] = {
            str(key): int(value) for key, value in payload.get("stat_modifiers", {}).items()
        }
        return cls(**payload)


CONSEQUENCE_TEMPLATES: dict[str, dict[str, Any]] = {
    "motor_nerve_severed": {
        "kind": "motor_nerve_severed",
        "description": "Motor nerve severed. Limb is permanently non-functional.",
        "mobility_penalty": 3,
        "stress_per_tick": 0.5,
    },
    "missing_limb": {
        "kind": "missing_limb",
        "description": "Limb destroyed. Permanent loss.",
        "mobility_penalty": 4,
        "stress_per_tick": 1.0,
    },
    "brain_damage": {
        "kind": "brain_damage",
        "description": "Brain damage. Severe cognitive and social impairment.",
        "stat_modifiers": {"focus": -5, "social": -5},
        "stress_per_tick": 2.0,
    },
    "chronic_pain": {
        "kind": "chronic_pain",
        "description": "Chronic pain from poorly healed wound.",
        "stress_per_tick": 2.0,
    },
}


@dataclass
class RecoveryState:
    body_part_id: str
    current_hp: int
    max_hp: int
    base_rate: float = 1.0
    recuperation_bonus: float = 0.0
    treatment_quality: float = 0.5
    ticks_since_last_heal: int = 0

    def effective_healing_rate(self) -> float:
        return self.base_rate * (1.0 + self.recuperation_bonus) * self.treatment_quality

    def tick_recovery(self, ticks: int = 1) -> int:
        self.ticks_since_last_heal += max(0, int(ticks))
        heal_intervals = self.ticks_since_last_heal // 50
        if heal_intervals <= 0:
            return 0
        self.ticks_since_last_heal %= 50
        hp_restored = int(heal_intervals * self.effective_healing_rate())
        previous_hp = self.current_hp
        self.current_hp = min(int(self.max_hp), int(self.current_hp) + hp_restored)
        return self.current_hp - previous_hp

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecoveryState":
        return cls(**data)


def determine_treatment_plan(wound: WoundRecord) -> list[TreatmentStep]:
    plan = [TreatmentStep.DIAGNOSIS]
    if wound.open_wound:
        plan.extend([TreatmentStep.CLEAN, TreatmentStep.SUTURE])
    if wound.bleeding > 0 or wound.open_wound:
        plan.append(TreatmentStep.DRESS_WOUND)
    if wound.fracture:
        plan.append(TreatmentStep.SET_BONE)
    if "embedded_object" in wound.tags:
        plan.append(TreatmentStep.SURGERY)
    return plan


def can_perform_step(
    doctor: ActorRecord,
    step: TreatmentStep,
    available_materials: dict[str, int],
) -> tuple[bool, list[str]]:
    requirement = TREATMENT_REQUIREMENTS[step]
    missing: list[str] = []
    if requirement.required_skill:
        current_skill = _skill_value(doctor, requirement.required_skill)
        if current_skill < requirement.min_skill_level:
            missing.append(
                f"insufficient skill: {requirement.required_skill} (have {current_skill}, need {requirement.min_skill_level})"
            )
    for material, quantity in requirement.consumed_materials:
        if int(available_materials.get(material, 0)) < quantity:
            missing.append(f"missing: {material}")
    for tool in requirement.tool_materials:
        if int(available_materials.get(tool, 0)) <= 0:
            missing.append(f"missing: {tool}")
    return len(missing) == 0, missing


def perform_treatment_step(
    doctor: ActorRecord,
    patient: ActorRecord,
    wound: WoundRecord,
    treatment: TreatmentRecord,
    step: TreatmentStep,
    available_materials: dict[str, int],
    rng_value: float = 0.0,
) -> tuple[bool, str]:
    if step != TreatmentStep.DIAGNOSIS and not (treatment.diagnosed or bool(getattr(wound, "diagnosed", False))):
        raise ValueError("Diagnosis is required before treatment can continue.")
    if patient.body_state is None or wound.body_part_id not in patient.body_state.parts:
        logger.warning("Skipping medical treatment for missing body part %s", wound.body_part_id)
        return False, "missing body part"
    can_perform, missing = can_perform_step(doctor, step, available_materials)
    if not can_perform:
        return False, ", ".join(missing)
    if step == TreatmentStep.DIAGNOSIS and str(patient.raw_payload.get("zone", "")) != "hospital":
        return False, "patient must be in hospital"

    requirement = TREATMENT_REQUIREMENTS[step]
    for material, quantity in requirement.consumed_materials:
        available_materials[material] = int(available_materials.get(material, 0)) - quantity

    if step == TreatmentStep.DIAGNOSIS:
        treatment.diagnosed = True
        wound.diagnosed = True
        message = "diagnosed"
    elif step == TreatmentStep.CLEAN:
        current_risk = float(getattr(wound, "infection_risk", 1.0))
        wound.infection_risk = current_risk * 0.1
        treatment.infection_rate = 0.1
        treatment.treatment_quality = max(treatment.treatment_quality, 1.0)
        message = "cleaned"
    elif step == TreatmentStep.SUTURE:
        if wound.open_wound:
            wound.open_wound = False
        treatment.treatment_quality = max(treatment.treatment_quality, 1.0)
        message = "sutured"
    elif step == TreatmentStep.DRESS_WOUND:
        wound.bleeding = 0
        wound.untreated = False
        patient.body_state.parts[wound.body_part_id].bleed_rate = 0
        treatment.treatment_quality = max(treatment.treatment_quality, 1.0)
        message = "dressed"
    elif step == TreatmentStep.SET_BONE:
        wound.fracture = False
        patient.body_state.parts[wound.body_part_id].mobility_penalty = max(
            0,
            patient.body_state.parts[wound.body_part_id].mobility_penalty - 1,
        )
        treatment.treatment_quality = max(treatment.treatment_quality, 1.0)
        message = "bone set"
    elif step == TreatmentStep.SURGERY:
        failure_chance = surgery_failure_chance(_skill_value(doctor, "surgery"))
        if float(rng_value) < failure_chance:
            added_damage = max(1, min(10, int(float(rng_value) * 10) + 1))
            wound.damage_amount += added_damage
            part_state = patient.body_state.parts[wound.body_part_id]
            part_state.current_hp = max(0, part_state.current_hp - added_damage)
            wound.destroyed = part_state.current_hp == 0 or wound.destroyed
            _record_step_completion(treatment, doctor, step)
            return False, f"surgery failed: +{added_damage} damage"
        wound.tags = [tag for tag in wound.tags if tag != "embedded_object"]
        treatment.treatment_quality = max(treatment.treatment_quality, 1.0)
        message = "surgery completed"
    else:
        raise ValueError(f"Unsupported treatment step: {step}")

    if treatment.is_fully_treated() or _would_be_fully_treated(treatment, step):
        if str(patient.raw_payload.get("zone", "")) == "hospital":
            treatment.treatment_quality = max(treatment.treatment_quality, 1.5)
    _record_step_completion(treatment, doctor, step)
    return True, message


def tick_infection(infection: InfectionState, ticks: int = 1) -> None:
    infection.tick_infection(ticks)


def tick_recovery(recovery: RecoveryState, ticks: int = 1) -> int:
    return recovery.tick_recovery(ticks)


def apply_permanent_consequence(
    actor: ActorRecord,
    wound: WoundRecord,
    consequence_kind: str,
) -> PermanentConsequence:
    template = CONSEQUENCE_TEMPLATES[consequence_kind]
    consequence = PermanentConsequence(
        consequence_id=f"{consequence_kind}:{actor.identity.actor_id}:{wound.body_part_id}",
        body_part_id=wound.body_part_id,
        **template,
    )
    actor.raw_payload.setdefault("permanent_consequences", []).append(consequence)
    actor.conditions.append(
        ConditionRecord(
            condition_id=consequence.consequence_id,
            name=consequence.kind,
            severity=max(1, consequence.mobility_penalty or int(consequence.stress_per_tick)),
            tags=[wound.body_part_id, "permanent"],
        )
    )
    if actor.body_state is not None and wound.body_part_id in actor.body_state.parts:
        actor.body_state.parts[wound.body_part_id].mobility_penalty = max(
            actor.body_state.parts[wound.body_part_id].mobility_penalty,
            consequence.mobility_penalty,
        )
    for stat_name, modifier in consequence.stat_modifiers.items():
        actor.stats[stat_name] = int(actor.stats.get(stat_name, 0)) + int(modifier)
    if consequence.stress_per_tick > 0:
        current_stress = float(actor.needs.modifiers.get("stress_per_tick", 0.0))
        actor.needs.modifiers["stress_per_tick"] = current_stress + consequence.stress_per_tick
    if consequence.kind == "brain_damage" and wound.body_part_id == "head" and wound.destroyed:
        actor.alive = False
    return consequence


def check_lethal_conditions(actor: ActorRecord) -> tuple[bool, str]:
    if actor.body_state is not None:
        for part in actor.body_state.plan.parts:
            if part.vital and actor.body_state.parts.get(part.part_id) is not None:
                if actor.body_state.parts[part.part_id].current_hp <= 0:
                    return True, "vital_body_part"
        if actor.body_state.blood_loss_rate() >= max(1, sum(part.max_hp for part in actor.body_state.plan.parts) // 2):
            return True, "blood_loss"
    infection_states = actor.raw_payload.get("medical_infections", [])
    for infection in infection_states:
        if isinstance(infection, InfectionState):
            state = infection
        elif isinstance(infection, dict):
            state = InfectionState.from_dict(infection)
        else:
            continue
        tick_infection(state, 0)
        if state.lethal:
            return True, "infection"
    return False, ""


def create_treatment_record(wound: WoundRecord, patient_id: str, current_tick: int) -> TreatmentRecord:
    infection_level = float(getattr(wound, "infection_level", 0.0))
    infection_risk = float(getattr(wound, "infection_risk", 1.0 if wound.open_wound else 0.0))
    return TreatmentRecord(
        wound_id=wound.wound_id,
        patient_id=patient_id,
        diagnosed=bool(getattr(wound, "diagnosed", False)),
        steps_remaining=determine_treatment_plan(wound),
        infection_level=infection_level,
        infection_rate=infection_risk,
        tick_started=int(current_tick),
    )


def surgery_failure_chance(surgery_skill: int) -> float:
    return max(0.05, 0.60 - (max(0, int(surgery_skill)) * 0.05))


def _skill_value(actor: ActorRecord, skill_name: str) -> int:
    return int(actor.skills.get(skill_name, actor.skills.get(f"{skill_name}_skill", 0)))


def _record_step_completion(treatment: TreatmentRecord, doctor: ActorRecord, step: TreatmentStep) -> None:
    treatment.doctor_id = doctor.identity.actor_id
    if step not in treatment.steps_completed:
        treatment.steps_completed.append(step)
    treatment.steps_remaining = [candidate for candidate in treatment.steps_remaining if candidate != step]


def _would_be_fully_treated(treatment: TreatmentRecord, step: TreatmentStep) -> bool:
    return all(candidate == step for candidate in treatment.steps_remaining)


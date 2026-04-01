# PRD: Medical System V1
**Project:** Ember RPG
**Phase:** 3
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose
The Medical System implements wound treatment, infection progression, recovery, and permanent injury consequences for colony actors. It models a DF-inspired (M05 Medical) treatment pipeline where doctors diagnose, clean, suture, dress, set bones, and perform surgery on wounded actors using specific skills and materials. Untreated wounds progress through infection stages that can cause organ damage or death. The system produces deterministic health outcomes from typed wound and treatment records without any LLM dependency.

## 2. Scope
- **In scope:** Treatment pipeline (diagnosis through surgery); infection progression model; recovery formula; permanent consequence system (severed nerves, missing limbs, brain damage, chronic pain); doctor skill requirements; material consumption for treatments; hospital zone integration.
- **Out of scope:** Disease/illness system (non-wound medical conditions); prosthetics and magical healing; psychological trauma (handled by colony simulation morale cascade); UI for medical status display; animal medical treatment.

## 3. Functional Requirements (FR)

FR-01: The medical system must define a typed `TreatmentStep` enum with ordered stages: `DIAGNOSIS`, `CLEAN`, `SUTURE`, `DRESS_WOUND`, `SET_BONE`, `SURGERY`. Each wound progresses through applicable stages in this order.

FR-02: The `DIAGNOSIS` step requires an actor with `diagnose_skill >= 1` and the patient located in a `hospital` zone. Upon completion, `wound.diagnosed` is set to `True`. No treatment step may proceed on an undiagnosed wound.

FR-03: The `CLEAN` step requires `soap` (1 unit, consumed) and `water` (1 unit, consumed). Upon completion, `wound.infection_risk` is multiplied by 0.1 (90% reduction).

FR-04: The `SUTURE` step requires `thread` (1 unit, consumed) and an actor with `suture_skill >= 1`. Upon completion, `wound.open_wound` is set to `False`. Only applies to wounds where `open_wound == True`.

FR-05: The `DRESS_WOUND` step requires `cloth` (1 unit, consumed) and an actor with `dress_wound_skill >= 1`. Upon completion, `wound.bleeding` is set to 0 and `wound.untreated` is set to `False`.

FR-06: The `SET_BONE` step requires an actor with `set_bone_skill >= 1`. Upon completion, `wound.fracture` is set to `False`. Only applies to wounds where `fracture == True`.

FR-07: The `SURGERY` step requires an actor with `surgery_skill >= 1` and an `edged_tool` (1 unit, not consumed). Surgery removes embedded objects from wounds. Surgery has a failure risk: `failure_chance = max(0.05, 0.60 - surgery_skill * 0.05)`. On failure, the wound receives additional damage equal to `rng_int(1, 10)`.

FR-08: Infection must progress on untreated open wounds at a rate of `infection_level += 1` per 100 ticks. Soap treatment (CLEAN step completed) reduces subsequent infection gain rate to `infection_level += 0.1` per 100 ticks.

FR-09: Infection severity thresholds must trigger escalating consequences:
- `infection_level > 50`: actor gains `fever` condition, `pain += 10`
- `infection_level > 80`: actor gains `organ_damage` condition on the affected body part
- `infection_level > 100`: actor dies (wound becomes lethal)

FR-10: Recovery rate must follow the formula: `healing_rate = base_rate * (1 + recuperation_bonus) * treatment_quality` where `base_rate = 1.0` HP per 50 ticks, `recuperation_bonus = actor.stats.get("recuperation", 0) * 0.01`, and `treatment_quality` is 0.5 (untreated), 1.0 (basic treatment), or 1.5 (full treatment in hospital).

FR-11: Permanent consequences must apply for specific injury types:
- `MOTOR_NERVE_SEVERED` on a limb: limb is permanently non-functional (`mobility_penalty = max_penalty`, limb cannot grasp or manipulate).
- Missing limb (body part HP = 0 and `destroyed = True`): permanent, no recovery possible.
- Brain damage (head `vital` layer destroyed): immediate death or permanent personality change (`stats["focus"] -= 5`, `stats["social"] -= 5`).
- Chronic pain (wound with `pain > 20` after full treatment): ongoing `stress += 2` per tick applied to actor's need state.

FR-12: The medical system must define a typed `TreatmentRecord` that tracks which steps have been completed for each wound, the treating doctor's actor_id, and timestamps.

## 4. Data Structures

```python
from enum import IntEnum

class TreatmentStep(IntEnum):
    """Ordered treatment stages. Each wound progresses through applicable steps."""
    DIAGNOSIS    = 0
    CLEAN        = 1
    SUTURE       = 2
    DRESS_WOUND  = 3
    SET_BONE     = 4
    SURGERY      = 5


@dataclass
class TreatmentRequirement:
    """Materials and skills required for a treatment step."""
    step: TreatmentStep
    required_skill: str             # Skill ID the doctor must possess
    min_skill_level: int = 1        # Minimum skill level required
    consumed_materials: list[tuple[str, int]] = field(default_factory=list)
        # List of (material_tag, quantity) consumed
    tool_materials: list[str] = field(default_factory=list)
        # Material tags that must be present but are not consumed

TREATMENT_REQUIREMENTS: dict[TreatmentStep, TreatmentRequirement] = {
    TreatmentStep.DIAGNOSIS: TreatmentRequirement(
        step=TreatmentStep.DIAGNOSIS,
        required_skill="diagnose",
        min_skill_level=1,
        consumed_materials=[],
        tool_materials=[],
    ),
    TreatmentStep.CLEAN: TreatmentRequirement(
        step=TreatmentStep.CLEAN,
        required_skill="",          # No specific skill; any doctor can clean
        min_skill_level=0,
        consumed_materials=[("soap", 1), ("water", 1)],
        tool_materials=[],
    ),
    TreatmentStep.SUTURE: TreatmentRequirement(
        step=TreatmentStep.SUTURE,
        required_skill="suture",
        min_skill_level=1,
        consumed_materials=[("thread", 1)],
        tool_materials=[],
    ),
    TreatmentStep.DRESS_WOUND: TreatmentRequirement(
        step=TreatmentStep.DRESS_WOUND,
        required_skill="dress_wound",
        min_skill_level=1,
        consumed_materials=[("cloth", 1)],
        tool_materials=[],
    ),
    TreatmentStep.SET_BONE: TreatmentRequirement(
        step=TreatmentStep.SET_BONE,
        required_skill="set_bone",
        min_skill_level=1,
        consumed_materials=[],
        tool_materials=[],
    ),
    TreatmentStep.SURGERY: TreatmentRequirement(
        step=TreatmentStep.SURGERY,
        required_skill="surgery",
        min_skill_level=1,
        consumed_materials=[],
        tool_materials=["edged_tool"],
    ),
}


@dataclass
class TreatmentRecord:
    """Tracks treatment progress for a single wound."""
    wound_id: str
    patient_id: str
    doctor_id: str | None = None
    diagnosed: bool = False
    steps_completed: list[TreatmentStep] = field(default_factory=list)
    steps_remaining: list[TreatmentStep] = field(default_factory=list)
    infection_level: float = 0.0
    infection_rate: float = 1.0     # Multiplier: 1.0 = untreated, 0.1 = cleaned
    treatment_quality: float = 0.5  # 0.5 = untreated, 1.0 = basic, 1.5 = hospital
    tick_started: int = 0
    tick_completed: int | None = None

    def is_fully_treated(self) -> bool:
        return len(self.steps_remaining) == 0

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TreatmentRecord": ...


@dataclass
class InfectionState:
    """Tracks infection progression on a wound."""
    wound_id: str
    body_part_id: str
    infection_level: float = 0.0    # 0 = clean, 100+ = lethal
    cleaned: bool = False           # True after CLEAN step
    fever: bool = False             # True when infection_level > 50
    organ_damage: bool = False      # True when infection_level > 80
    lethal: bool = False            # True when infection_level > 100

    def tick_infection(self, ticks_elapsed: int = 1) -> None:
        """Advance infection by ticks_elapsed. Rate: 1.0 per 100 ticks (uncleaned) or 0.1 per 100 ticks (cleaned)."""
        rate_per_tick = (0.1 if self.cleaned else 1.0) / 100.0
        self.infection_level += rate_per_tick * ticks_elapsed
        self.fever = self.infection_level > 50
        self.organ_damage = self.infection_level > 80
        self.lethal = self.infection_level > 100

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InfectionState": ...


@dataclass
class PermanentConsequence:
    """A permanent injury effect applied to an actor."""
    consequence_id: str
    kind: str                       # "motor_nerve_severed" | "missing_limb" | "brain_damage" | "chronic_pain"
    body_part_id: str
    description: str
    stat_modifiers: dict[str, int] = field(default_factory=dict)
        # e.g. {"focus": -5, "social": -5} for brain damage
    mobility_penalty: int = 0       # Additional mobility penalty
    stress_per_tick: float = 0.0    # Ongoing stress from chronic pain
    permanent: bool = True          # Cannot be healed naturally

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PermanentConsequence": ...


# Consequence templates
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
    """Tracks healing progress for a body part."""
    body_part_id: str
    current_hp: int
    max_hp: int
    base_rate: float = 1.0          # HP restored per 50 ticks
    recuperation_bonus: float = 0.0 # From actor stats
    treatment_quality: float = 0.5  # 0.5 untreated, 1.0 basic, 1.5 hospital
    ticks_since_last_heal: int = 0

    def effective_healing_rate(self) -> float:
        return self.base_rate * (1.0 + self.recuperation_bonus) * self.treatment_quality

    def tick_recovery(self, ticks: int = 1) -> int:
        """Advance recovery. Returns HP restored this call."""
        self.ticks_since_last_heal += ticks
        heal_intervals = self.ticks_since_last_heal // 50
        if heal_intervals <= 0:
            return 0
        self.ticks_since_last_heal %= 50
        hp_restored = int(heal_intervals * self.effective_healing_rate())
        old_hp = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + hp_restored)
        return self.current_hp - old_hp

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecoveryState": ...
```

### Surgery Failure Formula

```python
def surgery_failure_chance(surgery_skill: int) -> float:
    """Chance of surgery failure. Minimum 5%, decreases with skill."""
    return max(0.05, 0.60 - surgery_skill * 0.05)

# Examples:
# skill 0: 60% failure
# skill 1: 55% failure
# skill 5: 35% failure
# skill 10: 10% failure
# skill 11+: 5% failure (floor)
```

### Infection Progression Timeline (untreated open wound)

```
Tick      0: infection_level = 0.0
Tick   5000: infection_level = 50.0  -> fever, +10 pain
Tick   8000: infection_level = 80.0  -> organ damage begins
Tick  10000: infection_level = 100.0 -> death
```

### Infection Progression Timeline (cleaned wound)

```
Tick      0: infection_level = 0.0, cleaned = True
Tick  50000: infection_level = 50.0  -> fever (10x slower)
Tick  80000: infection_level = 80.0  -> organ damage
Tick 100000: infection_level = 100.0 -> death (effectively negligible in normal gameplay)
```

## 5. Public API

```python
def determine_treatment_plan(wound: WoundRecord) -> list[TreatmentStep]:
    """
    Determine which treatment steps are needed for a wound.
    Preconditions: wound is a valid WoundRecord.
    Postconditions: returns ordered list of applicable TreatmentStep values.
    Returns: list[TreatmentStep]. Always starts with DIAGNOSIS.
    Rules:
    - DIAGNOSIS: always required.
    - CLEAN: required if wound.open_wound == True.
    - SUTURE: required if wound.open_wound == True.
    - DRESS_WOUND: required if wound.bleeding > 0 or wound.open_wound == True.
    - SET_BONE: required if wound.fracture == True.
    - SURGERY: required if "embedded_object" in wound.tags.
    """

def can_perform_step(
    doctor: ActorRecord,
    step: TreatmentStep,
    available_materials: dict[str, int],
) -> tuple[bool, list[str]]:
    """
    Check if a doctor can perform a treatment step given available materials.
    Preconditions: step is a valid TreatmentStep.
    Returns: (can_perform, list_of_missing_requirements).
    """

def perform_treatment_step(
    doctor: ActorRecord,
    patient: ActorRecord,
    wound: WoundRecord,
    treatment: TreatmentRecord,
    step: TreatmentStep,
    available_materials: dict[str, int],
    rng_value: float = 0.0,
) -> tuple[bool, str]:
    """
    Execute a single treatment step on a wound.
    Preconditions: wound.diagnosed == True (except for DIAGNOSIS step itself).
                   can_perform_step returns True.
    Postconditions: wound state updated, materials consumed, step added to treatment.steps_completed.
    Returns: (success, result_message). For SURGERY, success may be False on failure.
    Raises: ValueError if wound is not diagnosed and step != DIAGNOSIS.
    """

def tick_infection(infection: InfectionState, ticks: int = 1) -> None:
    """
    Advance infection progression for a wound.
    Preconditions: infection is a valid InfectionState.
    Postconditions: infection_level updated, threshold flags set.
    """

def tick_recovery(recovery: RecoveryState, ticks: int = 1) -> int:
    """
    Advance healing for a body part.
    Preconditions: recovery is a valid RecoveryState.
    Returns: HP restored during this tick batch.
    """

def apply_permanent_consequence(
    actor: ActorRecord,
    wound: WoundRecord,
    consequence_kind: str,
) -> PermanentConsequence:
    """
    Apply a permanent injury consequence to an actor.
    Preconditions: consequence_kind is a key in CONSEQUENCE_TEMPLATES.
    Postconditions: actor.conditions updated, stats modified if applicable.
    Returns: the created PermanentConsequence.
    Raises: KeyError if consequence_kind is unknown.
    """

def check_lethal_conditions(actor: ActorRecord) -> tuple[bool, str]:
    """
    Check if an actor has any condition that should cause death.
    Checks: vital body part destroyed, infection > 100, blood loss exceeding threshold.
    Returns: (is_lethal, cause_of_death_string).
    """

def create_treatment_record(wound: WoundRecord, patient_id: str, current_tick: int) -> TreatmentRecord:
    """
    Initialize a treatment record for a wound.
    Preconditions: wound is a valid WoundRecord.
    Returns: TreatmentRecord with steps_remaining populated by determine_treatment_plan.
    """
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-01, FR-02]: Given a wound with `open_wound = True`, `fracture = True`, `bleeding = 5`, and tags containing `"embedded_object"`, when `determine_treatment_plan` is called, then the result is `[DIAGNOSIS, CLEAN, SUTURE, DRESS_WOUND, SET_BONE, SURGERY]` in that order.

AC-02 [FR-02]: Given a wound that is not diagnosed, when `perform_treatment_step` is called with step `SUTURE`, then a `ValueError` is raised.

AC-03 [FR-03]: Given a wound with `infection_risk = 1.0` and available materials including soap and water, when the `CLEAN` step is performed, then `wound.infection_risk` becomes 0.1 and 1 soap + 1 water are consumed from available_materials.

AC-04 [FR-04]: Given a diagnosed open wound and a doctor with `suture_skill = 3`, when the `SUTURE` step is performed, then `wound.open_wound` becomes `False` and 1 thread is consumed.

AC-05 [FR-05]: Given a diagnosed wound with `bleeding = 8`, when the `DRESS_WOUND` step is performed, then `wound.bleeding` becomes 0 and `wound.untreated` becomes `False`.

AC-06 [FR-06]: Given a diagnosed wound with `fracture = True` and a doctor with `set_bone_skill = 2`, when the `SET_BONE` step is performed, then `wound.fracture` becomes `False`.

AC-07 [FR-07]: Given a doctor with `surgery_skill = 5` (failure_chance = 0.35) and `rng_value = 0.30`, when the `SURGERY` step is performed, then surgery succeeds (0.30 < 0.35 is failure, so 0.30 >= 0.35 is False, meaning rng_value < failure_chance triggers failure). Correction: Given `rng_value = 0.40` (>= 0.35), surgery succeeds and the embedded object is removed.

AC-08 [FR-07]: Given a doctor with `surgery_skill = 1` (failure_chance = 0.55) and `rng_value = 0.30`, when the `SURGERY` step is performed, then surgery fails (0.30 < 0.55) and additional damage is applied to the wound.

AC-09 [FR-08]: Given an untreated open wound with `infection_level = 0.0`, when `tick_infection` is called for 5000 ticks, then `infection_level = 50.0` and `fever = True`.

AC-10 [FR-08]: Given a cleaned wound with `infection_level = 0.0`, when `tick_infection` is called for 5000 ticks, then `infection_level = 5.0` and `fever = False`.

AC-11 [FR-09]: Given a wound with `infection_level = 85.0`, when infection state is checked, then `organ_damage = True` and `lethal = False`.

AC-12 [FR-09]: Given a wound with `infection_level = 101.0`, when `check_lethal_conditions` is evaluated, then result is `(True, "infection")`.

AC-13 [FR-10]: Given a body part with `max_hp = 100`, `current_hp = 50`, `recuperation_bonus = 0.1`, `treatment_quality = 1.5`, when `tick_recovery` is called for 100 ticks, then HP restored = int(2 * 1.0 * 1.1 * 1.5) = int(3.3) = 3, and `current_hp` becomes 53.

AC-14 [FR-11]: Given a wound on `left_leg` where the body part is destroyed (`current_hp = 0`, `destroyed = True`), when `apply_permanent_consequence("missing_limb")` is called, then the actor receives a `PermanentConsequence` with `mobility_penalty = 4` and `stress_per_tick = 1.0`.

AC-15 [FR-11]: Given a wound tagged `"motor_nerve_severed"` on `right_arm`, when `apply_permanent_consequence("motor_nerve_severed")` is called, then the actor receives a consequence with `mobility_penalty = 3`.

AC-16 [FR-12]: Given a `TreatmentRecord`, when `to_dict()` is called followed by `from_dict()`, then all fields including `steps_completed` and `infection_level` round-trip without data loss.

## 7. Performance Requirements
- `determine_treatment_plan` must complete in < 0.1 ms per wound.
- `tick_infection` must complete in < 0.01 ms per wound per tick.
- `tick_recovery` must complete in < 0.01 ms per body part per tick.
- `perform_treatment_step` must complete in < 0.5 ms per step.
- All calculations must be deterministic given the same `rng_value` input.

## 8. Error Handling
- If `perform_treatment_step` is called on an undiagnosed wound (except DIAGNOSIS itself), raise `ValueError` with message indicating diagnosis is required.
- If `can_perform_step` detects missing materials, return `(False, ["missing: soap"])` with specific missing items listed.
- If `can_perform_step` detects insufficient doctor skill, return `(False, ["insufficient skill: surgery (have 0, need 1)"])`.
- If `apply_permanent_consequence` receives an unknown `consequence_kind`, raise `KeyError`.
- If `tick_recovery` would heal beyond `max_hp`, clamp to `max_hp`.
- If `infection_level` exceeds 100 during `tick_infection`, set `lethal = True` but do not clamp (actual death is handled by `check_lethal_conditions`).
- If a body part referenced by a wound does not exist in the actor's `body_state`, log a warning and skip treatment.

## 9. Integration Points
- **Actor Kernel** (`engine.kernel.actor`): `WoundRecord` and `BodyState` on `ActorRecord` provide wound data. `ActorRecord.stats["recuperation"]` feeds recovery formula. `ActorRecord.skills` provides doctor skill levels.
- **Body/Injury System**: `BodyPartState`, `WoundRecord`, and `ConditionRecord` from `actor.py` are the primary input data. The medical system reads and mutates these records.
- **Colony Simulation Kernel**: Chronic pain consequences feed `stress_per_tick` into the actor's `NeedState`, affecting colony morale. Hospital zone requirements integrate with room/zone validation.
- **Job/Reaction Kernel**: Treatment steps are modeled as medical jobs. Doctor assignment uses the labor assignment algorithm with medical skills. Material consumption uses the same stockpile system.
- **Inventory System**: Material requirements (soap, thread, cloth, edged_tool) are checked against and consumed from colony stockpile/inventory.

## 10. Test Coverage Target
- Minimum 95% line coverage for the medical system module.
- All 6 treatment steps must have success-path tests.
- Surgery must have both success and failure tests at multiple skill levels.
- Infection progression: test at 0, 50, 80, and 100+ thresholds for both cleaned and uncleaned wounds.
- Recovery formula: test with varying `recuperation_bonus` and `treatment_quality` values.
- All 4 permanent consequence types must have dedicated tests.
- Lethal condition checks: test vital part destruction, infection death, and blood loss death.
- Round-trip serialization for `TreatmentRecord`, `InfectionState`, `PermanentConsequence`, `RecoveryState`.
- Edge case: wound on a body part that has already been destroyed.

---

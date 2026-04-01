from __future__ import annotations

from engine.kernel.actor import (
    ActorIdentity,
    ActorPosition,
    ActorRecord,
    BodyPartDef,
    BodyPartState,
    BodyPlanDef,
    BodyState,
    WoundRecord,
)
from engine.kernel.medical import (
    InfectionState,
    RecoveryState,
    TreatmentRecord,
    TreatmentStep,
    apply_permanent_consequence,
    check_lethal_conditions,
    create_treatment_record,
    determine_treatment_plan,
    perform_treatment_step,
    tick_infection,
    tick_recovery,
)


def _body_state() -> BodyState:
    plan = BodyPlanDef(
        plan_id="humanoid",
        label="Humanoid",
        parts=[
            BodyPartDef(part_id="head", label="Head", max_hp=30, vital=True),
            BodyPartDef(part_id="torso", label="Torso", max_hp=50, vital=True),
            BodyPartDef(part_id="left_leg", label="Left Leg", max_hp=25),
            BodyPartDef(part_id="right_arm", label="Right Arm", max_hp=20),
        ],
    )
    return BodyState(
        plan=plan,
        parts={
            "head": BodyPartState(part_id="head", current_hp=30, max_hp=30),
            "torso": BodyPartState(part_id="torso", current_hp=50, max_hp=50),
            "left_leg": BodyPartState(part_id="left_leg", current_hp=25, max_hp=25),
            "right_arm": BodyPartState(part_id="right_arm", current_hp=20, max_hp=20),
        },
    )


def _actor(actor_id: str, *, zone: str = "hospital", skills: dict[str, int] | None = None) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc", faction_id="settlement"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"hp": 20, "max_hp": 20, "recuperation": 10, "focus": 10, "social": 10},
        skills=skills or {},
        body_state=_body_state(),
        raw_payload={"zone": zone, "medical_infections": []},
    )


def _wound() -> WoundRecord:
    wound = WoundRecord(
        wound_id="wound_1",
        body_part_id="left_leg",
        damage_type="slash",
        damage_amount=8,
        bleeding=5,
        pain=12,
        open_wound=True,
        fracture=True,
        tags=["embedded_object"],
    )
    wound.infection_risk = 1.0
    wound.diagnosed = False
    return wound


def test_ac01_determine_treatment_plan_orders_all_applicable_steps():
    plan = determine_treatment_plan(_wound())

    assert plan == [
        TreatmentStep.DIAGNOSIS,
        TreatmentStep.CLEAN,
        TreatmentStep.SUTURE,
        TreatmentStep.DRESS_WOUND,
        TreatmentStep.SET_BONE,
        TreatmentStep.SURGERY,
    ]


def test_ac02_non_diagnosis_step_requires_diagnosis():
    doctor = _actor("doctor", skills={"suture": 3})
    patient = _actor("patient")
    wound = _wound()
    treatment = create_treatment_record(wound, patient.identity.actor_id, current_tick=0)

    try:
        perform_treatment_step(
            doctor,
            patient,
            wound,
            treatment,
            TreatmentStep.SUTURE,
            {"thread": 1},
        )
    except ValueError as exc:
        assert "diagnosis" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError for undiagnosed wound")


def test_ac03_clean_reduces_infection_risk_and_consumes_materials():
    doctor = _actor("doctor", skills={"diagnose": 1})
    patient = _actor("patient")
    wound = _wound()
    materials = {"soap": 1, "water": 1}
    treatment = create_treatment_record(wound, patient.identity.actor_id, current_tick=0)

    perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.DIAGNOSIS, materials)
    success, _ = perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.CLEAN, materials)

    assert success is True
    assert wound.infection_risk == 0.1
    assert materials == {"soap": 0, "water": 0}


def test_ac04_suture_closes_open_wound_and_consumes_thread():
    doctor = _actor("doctor", skills={"diagnose": 1, "suture": 3})
    patient = _actor("patient")
    wound = _wound()
    treatment = create_treatment_record(wound, patient.identity.actor_id, current_tick=0)
    materials = {"thread": 1}

    perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.DIAGNOSIS, materials)
    success, _ = perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.SUTURE, materials)

    assert success is True
    assert wound.open_wound is False
    assert materials["thread"] == 0


def test_ac05_dress_wound_stops_bleeding_and_marks_treated():
    doctor = _actor("doctor", skills={"diagnose": 1, "dress_wound": 2})
    patient = _actor("patient")
    wound = _wound()
    treatment = create_treatment_record(wound, patient.identity.actor_id, current_tick=0)
    materials = {"cloth": 1}

    perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.DIAGNOSIS, materials)
    success, _ = perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.DRESS_WOUND, materials)

    assert success is True
    assert wound.bleeding == 0
    assert wound.untreated is False


def test_ac06_set_bone_clears_fracture():
    doctor = _actor("doctor", skills={"diagnose": 1, "set_bone": 2})
    patient = _actor("patient")
    wound = _wound()
    treatment = create_treatment_record(wound, patient.identity.actor_id, current_tick=0)

    perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.DIAGNOSIS, {})
    success, _ = perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.SET_BONE, {})

    assert success is True
    assert wound.fracture is False


def test_ac07_surgery_success_removes_embedded_object():
    doctor = _actor("doctor", skills={"diagnose": 1, "surgery": 5})
    patient = _actor("patient")
    wound = _wound()
    treatment = create_treatment_record(wound, patient.identity.actor_id, current_tick=0)
    materials = {"edged_tool": 1}

    perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.DIAGNOSIS, materials)
    success, _ = perform_treatment_step(
        doctor,
        patient,
        wound,
        treatment,
        TreatmentStep.SURGERY,
        materials,
        rng_value=0.40,
    )

    assert success is True
    assert "embedded_object" not in wound.tags
    assert materials["edged_tool"] == 1


def test_ac08_surgery_failure_adds_damage():
    doctor = _actor("doctor", skills={"diagnose": 1, "surgery": 1})
    patient = _actor("patient")
    wound = _wound()
    treatment = create_treatment_record(wound, patient.identity.actor_id, current_tick=0)
    materials = {"edged_tool": 1}

    perform_treatment_step(doctor, patient, wound, treatment, TreatmentStep.DIAGNOSIS, materials)
    original_damage = wound.damage_amount
    success, _ = perform_treatment_step(
        doctor,
        patient,
        wound,
        treatment,
        TreatmentStep.SURGERY,
        materials,
        rng_value=0.30,
    )

    assert success is False
    assert wound.damage_amount > original_damage


def test_ac09_infection_progression_reaches_fever_threshold_for_untreated_wound():
    infection = InfectionState(wound_id="wound_1", body_part_id="left_leg")

    tick_infection(infection, 5000)

    assert infection.infection_level == 50.0
    assert infection.fever is True


def test_ac10_cleaned_infection_progresses_ten_times_slower():
    infection = InfectionState(wound_id="wound_1", body_part_id="left_leg", cleaned=True)

    tick_infection(infection, 5000)

    assert infection.infection_level == 5.0
    assert infection.fever is False


def test_ac11_infection_above_80_triggers_organ_damage_without_lethality():
    infection = InfectionState(wound_id="wound_1", body_part_id="left_leg", infection_level=85.0)
    tick_infection(infection, 0)

    assert infection.organ_damage is True
    assert infection.lethal is False


def test_ac12_lethal_conditions_report_infection_death():
    actor = _actor("patient")
    actor.raw_payload["medical_infections"] = [
        InfectionState(wound_id="wound_1", body_part_id="left_leg", infection_level=101.0)
    ]

    assert check_lethal_conditions(actor) == (True, "infection")


def test_ac13_recovery_formula_restores_expected_hp():
    recovery = RecoveryState(
        body_part_id="left_leg",
        current_hp=50,
        max_hp=100,
        recuperation_bonus=0.1,
        treatment_quality=1.5,
    )

    restored = tick_recovery(recovery, 100)

    assert restored == 3
    assert recovery.current_hp == 53


def test_ac14_missing_limb_consequence_applies_mobility_and_stress():
    actor = _actor("patient")
    actor.body_state.parts["left_leg"].current_hp = 0
    wound = _wound()
    wound.destroyed = True

    consequence = apply_permanent_consequence(actor, wound, "missing_limb")

    assert consequence.mobility_penalty == 4
    assert consequence.stress_per_tick == 1.0


def test_ac15_motor_nerve_severed_consequence_has_expected_penalty():
    actor = _actor("patient")
    wound = WoundRecord(
        wound_id="wound_arm",
        body_part_id="right_arm",
        damage_type="pierce",
        damage_amount=5,
        tags=["motor_nerve_severed"],
    )

    consequence = apply_permanent_consequence(actor, wound, "motor_nerve_severed")

    assert consequence.mobility_penalty == 3


def test_ac16_treatment_record_round_trip_preserves_fields():
    record = TreatmentRecord(
        wound_id="wound_1",
        patient_id="patient",
        doctor_id="doctor",
        diagnosed=True,
        steps_completed=[TreatmentStep.DIAGNOSIS, TreatmentStep.CLEAN],
        steps_remaining=[TreatmentStep.SUTURE],
        infection_level=12.5,
        infection_rate=0.1,
        treatment_quality=1.5,
        tick_started=10,
        tick_completed=40,
    )

    restored = TreatmentRecord.from_dict(record.to_dict())

    assert restored == record

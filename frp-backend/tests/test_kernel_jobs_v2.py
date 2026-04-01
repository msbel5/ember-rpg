from __future__ import annotations

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.jobs import (
    JobRecord,
    MaterialRequirement,
    ProductOutput,
    ReactionDef,
    SkillRecord,
    WorksiteRecord,
    assign_labor,
    cancel_job,
    complete_job,
    job_records_from_settlement,
    level_from_xp,
    tick_skill_rust,
    validate_room_zone,
    weighted_random_quality,
)


def _actor(actor_id: str, *, x: int, skill_level: int) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc", faction_id="settlement"),
        position=ActorPosition(x=x, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"focus": 10},
        skills={"smithing": skill_level},
        raw_payload={"input_materials": {"ore": "iron"}},
    )


def test_ac01_job_records_from_settlement_returns_three_typed_jobs():
    records = job_records_from_settlement(
        {
            "jobs": [
                {"id": "job_1", "kind": "forge", "priority": 2, "status": "queued"},
                {"id": "job_2", "kind": "haul", "priority": 4, "status": "assigned"},
            ],
            "construction_queue": [{"id": "build_1", "kind": "construct", "priority": 3}],
        }
    )

    assert len(records) == 3
    assert [record.kind for record in records] == ["forge", "haul", "construct"]
    assert records[0].priority == 2
    assert records[1].status == "assigned"
    assert records[0].skill_id == "smithing"


def test_ac02_job_record_enforces_valid_state_transitions():
    job = JobRecord(job_id="job_1", kind="forge", priority=2, status="queued")

    job.transition_to("assigned")
    job.transition_to("active")
    job.transition_to("completed")

    assert job.status == "completed"


def test_ac03_cancel_job_marks_cancelled_and_returns_refundable_tags():
    job = JobRecord(
        job_id="job_1",
        kind="forge",
        priority=2,
        status="active",
        input_tags=["ore", "fuel"],
    )

    refunded = cancel_job(job)

    assert job.status == "cancelled"
    assert refunded == ["ore", "fuel"]


def test_ac04_reaction_def_preserves_non_consumed_requirement():
    reaction = ReactionDef(
        reaction_id="forge_sword",
        label="Forge Sword",
        worksite_kind="forge",
        input_materials=[
            MaterialRequirement("ore", 2, True),
            MaterialRequirement("anvil", 1, False),
        ],
    )

    assert reaction.input_materials[1].consumed is False


def test_ac05_complete_job_inherits_material_from_inputs():
    actor = _actor("smith", x=1, skill_level=8)
    job = JobRecord(
        job_id="job_1",
        kind="forge",
        priority=2,
        status="active",
        skill_id="smithing",
        input_tags=["ore"],
        elapsed_ticks=100,
        completion_ticks=100,
    )
    reaction = ReactionDef(
        reaction_id="forge_sword",
        label="Forge Sword",
        worksite_kind="forge",
        input_materials=[MaterialRequirement("ore", 2, True)],
        output_products=[ProductOutput("iron_sword", "inherit", 1)],
        required_skill="smithing",
        base_duration_ticks=100,
    )

    _, _, outputs = complete_job(job, actor, reaction, rng_value=0.2)

    assert outputs[0]["material_id"] == "iron"


def test_ac06_assign_labor_prefers_closest_and_highest_skill_tie_breaker():
    job = JobRecord(job_id="job_1", kind="forge", priority=2, status="queued", skill_id="smithing", worksite_id="forge_1")
    worksites = [WorksiteRecord(worksite_id="forge_1", label="Forge", kind="forge", position=(0, 0))]
    candidates = [
        _actor("actor_a", x=3, skill_level=5),
        _actor("actor_b", x=1, skill_level=8),
        _actor("actor_c", x=1, skill_level=3),
    ]

    selected = assign_labor(job, candidates, worksites)

    assert selected == "actor_b"


def test_ac07_complete_job_awards_expected_xp_from_focus_bonus():
    actor = _actor("smith", x=0, skill_level=4)
    job = JobRecord(job_id="job_1", kind="forge", priority=2, status="active", skill_id="smithing", elapsed_ticks=100, completion_ticks=100)
    reaction = ReactionDef(reaction_id="forge", label="Forge", worksite_kind="forge", required_skill="smithing", base_duration_ticks=100)

    xp_gained, _, _ = complete_job(job, actor, reaction, rng_value=0.1)

    assert xp_gained == 110


def test_ac08_level_from_xp_uses_documented_thresholds():
    assert level_from_xp(1100) == 2
    assert level_from_xp(1099) == 1


def test_ac09_skill_rust_applies_when_unused_counter_exceeds_threshold():
    skill = SkillRecord(skill_id="smithing", xp=3500, level=5, unused_counter=200)

    tick_skill_rust(skill, used_this_tick=False)

    assert skill.rusty_level == 1
    assert skill.unused_counter == 0


def test_ac10_legendary_skills_rust_more_slowly():
    skill = SkillRecord(skill_id="smithing", xp=20000, level=15, unused_counter=499)

    tick_skill_rust(skill, used_this_tick=False)

    assert skill.rusty_level == 0
    assert skill.unused_counter == 500


def test_ac11_weighted_random_quality_matches_low_skill_distribution_edges():
    assert weighted_random_quality(0, 0.95) == 1
    assert weighted_random_quality(0, 0.50) == 0


def test_ac12_validate_room_zone_reports_missing_chair_for_dining():
    valid, missing = validate_room_zone("dining", ["bed", "table"])

    assert valid is False
    assert missing == ["chair"]


def test_ac13_validate_room_zone_accepts_bedroom_with_bed():
    valid, missing = validate_room_zone("bedroom", ["bed"])

    assert valid is True
    assert missing == []


def test_ac14_job_record_round_trip_preserves_progress_fields():
    job = JobRecord(
        job_id="job_1",
        kind="forge",
        priority=2,
        status="active",
        completion_ticks=120,
        elapsed_ticks=40,
    )

    restored = JobRecord.from_dict(job.to_dict())

    assert restored == job

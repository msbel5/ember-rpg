from __future__ import annotations

import logging
from typing import Any

from engine.kernel.actor import ActorRecord
from engine.kernel.jobs_types import (
    JobRecord,
    MaterialRequirement,
    ProductOutput,
    QUALITY_LEVELS,
    ROOM_ZONE_DEFS,
    ReactionDef,
    SKILL_XP_THRESHOLDS,
    SkillRecord,
    WorksiteRecord,
)


logger = logging.getLogger(__name__)


def job_records_from_settlement(settlement_state: dict[str, Any]) -> list[JobRecord]:
    records: list[JobRecord] = []
    for job in settlement_state.get("jobs", []):
        kind = str(job.get("kind", "unknown"))
        records.append(
            JobRecord(
                job_id=str(job.get("id", "")),
                kind=kind,
                priority=int(job.get("priority", 3)),
                status=str(job.get("status", "queued")),
                assignee_id=job.get("assignee_id"),
                skill_id=_skill_for_job_kind(kind),
                worksite_id=job.get("worksite_id"),
                room_id=job.get("room_id"),
                input_tags=[str(item) for item in job.get("input_tags", [])],
                output_tags=[str(item) for item in job.get("output_tags", [])],
                completion_ticks=int(job.get("completion_ticks", 100)),
                elapsed_ticks=int(job.get("elapsed_ticks", 0)),
                tags=[str(item) for item in job.get("tags", [])],
            )
        )
    for index, build in enumerate(settlement_state.get("construction_queue", [])):
        records.append(
            JobRecord(
                job_id=str(build.get("id", f"construction_{index}")),
                kind=str(build.get("kind", "construction")),
                priority=int(build.get("priority", 4)),
                status=str(build.get("status", "queued")),
                skill_id="construction",
                room_id=build.get("room_id"),
                completion_ticks=int(build.get("completion_ticks", 100)),
                elapsed_ticks=int(build.get("elapsed_ticks", 0)),
                tags=["construction"],
            )
        )
    return records


def reaction_defs_from_settlement(settlement_state: dict[str, Any]) -> list[ReactionDef]:
    worksites = worksite_records_from_settlement(settlement_state)
    supported_worksite_kinds = {worksite.kind for worksite in worksites}
    reactions: list[ReactionDef] = []
    seen: set[str] = set()
    for room in settlement_state.get("rooms", []):
        for workstation in room.get("workstations", []):
            worksite_kind = str(workstation)
            if worksite_kind not in supported_worksite_kinds:
                logger.warning("Skipping reaction for unknown worksite kind %s", worksite_kind)
                continue
            reaction_id = f"{worksite_kind}_reaction"
            if reaction_id in seen:
                continue
            seen.add(reaction_id)
            input_tags = _input_tags_for_worksite(worksite_kind)
            output_tags = _output_tags_for_worksite(worksite_kind)
            reactions.append(
                ReactionDef(
                    reaction_id=reaction_id,
                    label=worksite_kind.replace("_", " ").title(),
                    worksite_kind=worksite_kind,
                    input_materials=[
                        MaterialRequirement(tag=tag, quantity=1, consumed=tag != "anvil")
                        for tag in input_tags
                    ],
                    output_products=[
                        ProductOutput(item_def_id=f"{worksite_kind}_output", material_id="inherit", quantity=1)
                    ],
                    required_skill=_skill_for_job_kind(worksite_kind),
                    base_duration_ticks=100,
                    input_tags=input_tags,
                    output_tags=output_tags,
                )
            )
    return reactions


def worksite_records_from_settlement(settlement_state: dict[str, Any]) -> list[WorksiteRecord]:
    worksites: list[WorksiteRecord] = []
    for room_index, room in enumerate(settlement_state.get("rooms", [])):
        workstations = [str(item) for item in room.get("workstations", [])]
        if not workstations:
            worksites.append(
                WorksiteRecord(
                    worksite_id=str(room.get("id", f"room_{room_index}")),
                    label=str(room.get("label", room.get("kind", "Room"))),
                    kind=str(room.get("kind", "room")),
                    room_id=str(room.get("id", f"room_{room_index}")),
                    supported_jobs=[],
                    reaction_ids=[],
                    position=_room_position(room),
                )
            )
            continue
        for workstation in workstations:
            worksites.append(
                WorksiteRecord(
                    worksite_id=f"{room.get('id', f'room_{room_index}')}_{workstation}",
                    label=str(workstation).replace("_", " ").title(),
                    kind=workstation,
                    room_id=str(room.get("id", f"room_{room_index}")),
                    supported_jobs=[workstation],
                    reaction_ids=[f"{workstation}_reaction"],
                    position=_room_position(room),
                )
            )
    return worksites


def assign_labor(
    job: JobRecord,
    candidates: list[ActorRecord],
    worksites: list[WorksiteRecord],
) -> str | None:
    if not candidates:
        return None
    worksite = next((site for site in worksites if site.worksite_id == job.worksite_id), None)
    if worksite is None and worksites:
        worksite = worksites[0]
    target_pos = worksite.position if worksite is not None and worksite.position is not None else (0, 0)
    eligible = [
        actor
        for actor in candidates
        if job.skill_id is None or int(actor.skills.get(job.skill_id, 0)) > 0
    ]
    if not eligible:
        return None
    eligible.sort(
        key=lambda actor: (
            _manhattan((actor.position.x, actor.position.y), target_pos),
            -int(actor.skills.get(job.skill_id or "", 0)),
            actor.identity.actor_id,
        )
    )
    return eligible[0].identity.actor_id


def tick_job(job: JobRecord, actor: ActorRecord, work_speed_mult: float = 1.0) -> bool:
    if job.status != "active":
        raise ValueError("tick_job requires an active job")
    increment = max(1, int(round(max(0.1, float(work_speed_mult)))))
    job.elapsed_ticks += increment
    return job.is_complete()


def complete_job(
    job: JobRecord,
    actor: ActorRecord,
    reaction: ReactionDef,
    rng_value: float,
) -> tuple[int, int, list[dict[str, Any]]]:
    if not job.is_complete():
        raise ValueError("Job is not complete")
    if job.status == "assigned":
        job.transition_to("active")
    if job.status == "active":
        job.transition_to("completed")
    elif job.status != "completed":
        job.status = "completed"
    xp_gained = int(reaction.base_duration_ticks * (1.0 + (float(actor.stats.get("focus", 0)) * 0.01)))
    quality_level = weighted_random_quality(
        int(actor.skills.get(reaction.required_skill or (job.skill_id or ""), 0)),
        rng_value,
    )
    _award_skill_progress(actor, reaction.required_skill or (job.skill_id or ""), xp_gained)
    outputs: list[dict[str, Any]] = []
    input_materials = actor.raw_payload.get("job_input_materials", {}).get(job.job_id)
    if input_materials is None:
        input_materials = actor.raw_payload.get("input_materials", {})
    for product in reaction.output_products:
        material_id = product.material_id
        if material_id == "inherit":
            material_id = _inherited_material(reaction, input_materials)
        outputs.append(
            {
                "item_def_id": product.item_def_id,
                "material_id": material_id,
                "quantity": product.quantity,
                "quality": quality_level,
                "quality_label": QUALITY_LEVELS.get(quality_level, "ordinary"),
            }
        )
    return xp_gained, quality_level, outputs


def cancel_job(job: JobRecord) -> list[str]:
    if job.status in {"completed", "cancelled"}:
        raise ValueError("Cannot cancel completed or cancelled job")
    refundable = list(job.input_tags)
    if job.status in {"queued", "assigned", "active"}:
        job.transition_to("cancelled")
    return refundable


def tick_skill_rust(skill: SkillRecord, used_this_tick: bool) -> None:
    if used_this_tick:
        skill.unused_counter = 0
        skill.rusty_level = max(0, skill.rusty_level - 1)
        return
    skill.unused_counter += 1
    if skill.unused_counter > skill.rust_threshold():
        skill.rusty_level += 1
        skill.unused_counter = 0


def level_from_xp(xp: int) -> int:
    if xp < 0:
        return 0
    for level in range(len(SKILL_XP_THRESHOLDS) - 1, -1, -1):
        if xp >= SKILL_XP_THRESHOLDS[level]:
            if level == len(SKILL_XP_THRESHOLDS) - 1 and xp > SKILL_XP_THRESHOLDS[level]:
                return level + ((xp - SKILL_XP_THRESHOLDS[level]) // 2000)
            return level
    return 0


def weighted_random_quality(effective_skill: int, rng_value: float) -> int:
    rng_value = min(0.999999, max(0.0, float(rng_value)))
    tables = [
        (2, [(0, 0.90), (1, 1.00)]),
        (5, [(0, 0.50), (1, 0.85), (2, 1.00)]),
        (8, [(0, 0.20), (1, 0.50), (2, 0.80), (3, 0.95), (4, 1.00)]),
        (11, [(0, 0.05), (1, 0.20), (2, 0.50), (3, 0.80), (4, 0.95), (5, 1.00)]),
        (14, [(1, 0.05), (2, 0.20), (3, 0.50), (4, 0.80), (5, 1.00)]),
        (9999, [(2, 0.05), (3, 0.20), (4, 0.50), (5, 1.00)]),
    ]
    for max_skill, table in tables:
        if effective_skill <= max_skill:
            for quality, cutoff in table:
                if rng_value < cutoff:
                    return quality
    return 0


def validate_room_zone(zone_type: str, furniture_tags: list[str]) -> tuple[bool, list[str]]:
    definition = ROOM_ZONE_DEFS[str(zone_type)]
    tags = {str(tag) for tag in furniture_tags}
    missing = [tag for tag in definition.required_furniture if tag not in tags]
    return len(missing) == 0, missing


def _skill_for_job_kind(kind: str) -> str:
    mapping = {
        "forge": "smithing",
        "smithing": "smithing",
        "haul": "hauling",
        "hauling": "hauling",
        "construct": "construction",
        "construction": "construction",
        "brew": "brewing",
        "cook": "cooking",
        "loom": "weaving",
        "bar_counter": "trade",
        "altar": "divine_magic",
        "bed": "healing",
    }
    return mapping.get(kind, kind)


def _input_tags_for_worksite(kind: str) -> list[str]:
    mapping = {
        "forge": ["ore", "anvil"],
        "bar_counter": ["drink", "trade_goods"],
        "bed": ["cloth"],
        "altar": ["offerings"],
        "loom": ["fiber"],
    }
    return mapping.get(kind, [kind])


def _output_tags_for_worksite(kind: str) -> list[str]:
    mapping = {
        "forge": ["weapons", "armor", "tools"],
        "bar_counter": ["morale", "commerce"],
        "bed": ["recovery"],
        "altar": ["faith", "stability"],
        "loom": ["cloth"],
    }
    return mapping.get(kind, [kind])


def _room_position(room: dict[str, Any]) -> tuple[int, int] | None:
    position = room.get("position")
    if isinstance(position, (list, tuple)) and len(position) >= 2:
        return int(position[0]), int(position[1])
    return None


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))


def _award_skill_progress(actor: ActorRecord, skill_id: str, xp_gained: int) -> None:
    if not skill_id:
        return
    skill_records = actor.raw_payload.setdefault("skill_records", {})
    current = skill_records.get(skill_id)
    if isinstance(current, SkillRecord):
        record = current
    elif isinstance(current, dict):
        record = SkillRecord.from_dict(current)
    else:
        record = SkillRecord(skill_id=skill_id, level=int(actor.skills.get(skill_id, 0)))
    record.xp += int(xp_gained)
    record.level = level_from_xp(record.xp)
    record.unused_counter = 0
    record.rusty_level = max(0, record.rusty_level - 1)
    skill_records[skill_id] = record
    actor.skills[skill_id] = record.level


def _inherited_material(reaction: ReactionDef, input_materials: Any) -> str:
    if isinstance(input_materials, dict):
        for requirement in reaction.input_materials:
            candidate = input_materials.get(requirement.tag)
            if candidate:
                return str(candidate)
        for candidate in input_materials.values():
            return str(candidate)
    if isinstance(input_materials, list):
        for candidate in input_materials:
            if isinstance(candidate, dict) and candidate.get("material_id"):
                return str(candidate["material_id"])
    return "generic"


__all__ = [
    "assign_labor",
    "cancel_job",
    "complete_job",
    "job_records_from_settlement",
    "level_from_xp",
    "reaction_defs_from_settlement",
    "tick_job",
    "tick_skill_rust",
    "validate_room_zone",
    "weighted_random_quality",
    "worksite_records_from_settlement",
]

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord
from engine.kernel.common import serialize_value


logger = logging.getLogger(__name__)


SKILL_XP_THRESHOLDS: list[int] = [
    0,
    500,
    1100,
    1800,
    2600,
    3500,
    4500,
    5600,
    6800,
    8100,
    9500,
    11000,
    12600,
    14300,
    16100,
]

SKILL_LEVEL_NAMES: dict[int, str] = {
    0: "Dabbling",
    1: "Novice",
    2: "Adequate",
    3: "Competent",
    4: "Skilled",
    5: "Proficient",
    6: "Talented",
    7: "Adept",
    8: "Expert",
    9: "Professional",
    10: "Accomplished",
    11: "Great",
    12: "Master",
    13: "High Master",
    14: "Grand Master",
}

QUALITY_LEVELS: dict[int, str] = {
    0: "ordinary",
    1: "well-crafted",
    2: "finely-crafted",
    3: "superior",
    4: "exceptional",
    5: "masterwork",
}


@dataclass
class MaterialRequirement:
    tag: str
    quantity: int
    consumed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialRequirement":
        return cls(**data)


@dataclass
class ProductOutput:
    item_def_id: str
    material_id: str
    quantity: int = 1

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductOutput":
        return cls(**data)


@dataclass
class JobRecord:
    job_id: str
    kind: str
    priority: int
    status: str
    assignee_id: str | None = None
    skill_id: str | None = None
    worksite_id: str | None = None
    room_id: str | None = None
    input_tags: list[str] = field(default_factory=list)
    output_tags: list[str] = field(default_factory=list)
    completion_ticks: int = 100
    elapsed_ticks: int = 0
    tags: list[str] = field(default_factory=list)

    def is_complete(self) -> bool:
        return self.elapsed_ticks >= self.completion_ticks

    def progress_fraction(self) -> float:
        if self.completion_ticks <= 0:
            return 1.0
        return min(1.0, self.elapsed_ticks / self.completion_ticks)

    def transition_to(self, next_status: str) -> None:
        allowed = {
            "queued": {"assigned", "cancelled"},
            "assigned": {"active", "cancelled"},
            "active": {"completed", "cancelled"},
            "completed": set(),
            "cancelled": set(),
        }
        if next_status not in allowed.get(self.status, set()):
            raise ValueError(f"Invalid job transition: {self.status} -> {next_status}")
        self.status = str(next_status)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobRecord":
        payload = dict(data)
        payload["input_tags"] = [str(item) for item in payload.get("input_tags", [])]
        payload["output_tags"] = [str(item) for item in payload.get("output_tags", [])]
        payload["tags"] = [str(item) for item in payload.get("tags", [])]
        return cls(**payload)


@dataclass
class ReactionDef:
    reaction_id: str
    label: str
    worksite_kind: str
    input_materials: list[MaterialRequirement] = field(default_factory=list)
    output_products: list[ProductOutput] = field(default_factory=list)
    required_skill: str = ""
    base_duration_ticks: int = 100
    quality_formula: str = "weighted_random"
    input_tags: list[str] = field(default_factory=list)
    output_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReactionDef":
        payload = dict(data)
        payload["input_materials"] = [
            item if isinstance(item, MaterialRequirement) else MaterialRequirement.from_dict(dict(item))
            for item in payload.get("input_materials", [])
        ]
        payload["output_products"] = [
            item if isinstance(item, ProductOutput) else ProductOutput.from_dict(dict(item))
            for item in payload.get("output_products", [])
        ]
        payload["input_tags"] = [str(item) for item in payload.get("input_tags", [])]
        payload["output_tags"] = [str(item) for item in payload.get("output_tags", [])]
        return cls(**payload)


@dataclass
class WorksiteRecord:
    worksite_id: str
    label: str
    kind: str
    room_id: str | None = None
    supported_jobs: list[str] = field(default_factory=list)
    reaction_ids: list[str] = field(default_factory=list)
    position: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorksiteRecord":
        payload = dict(data)
        position = payload.get("position")
        payload["supported_jobs"] = [str(item) for item in payload.get("supported_jobs", [])]
        payload["reaction_ids"] = [str(item) for item in payload.get("reaction_ids", [])]
        payload["position"] = tuple(position) if position is not None else None
        return cls(**payload)


@dataclass
class SkillRecord:
    skill_id: str
    xp: int = 0
    level: int = 0
    rusty_level: int = 0
    unused_counter: int = 0

    def effective_level(self) -> int:
        return max(0, self.level - self.rusty_level)

    def rust_threshold(self) -> int:
        return 500 if self.level >= 15 else 200

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillRecord":
        return cls(**data)


@dataclass
class RoomZoneDef:
    zone_type: str
    required_furniture: list[str]
    optional_furniture: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomZoneDef":
        payload = dict(data)
        payload["required_furniture"] = [str(item) for item in payload.get("required_furniture", [])]
        payload["optional_furniture"] = [str(item) for item in payload.get("optional_furniture", [])]
        return cls(**payload)


ROOM_ZONE_DEFS: dict[str, RoomZoneDef] = {
    "bedroom": RoomZoneDef("bedroom", required_furniture=["bed"]),
    "dining": RoomZoneDef("dining", required_furniture=["table", "chair"]),
    "workshop": RoomZoneDef("workshop", required_furniture=["worksite"]),
    "hospital": RoomZoneDef("hospital", required_furniture=["bed", "table"]),
    "temple": RoomZoneDef("temple", required_furniture=["altar"]),
}


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
                    input_materials=[MaterialRequirement(tag=tag, quantity=1, consumed=tag != "anvil") for tag in input_tags],
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
    if job.status == "queued":
        job.transition_to("cancelled")
    elif job.status == "assigned":
        job.transition_to("cancelled")
    elif job.status == "active":
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

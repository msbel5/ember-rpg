from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord, NeedState
from engine.kernel.common import serialize_value


@dataclass
class NeedDef:
    need_id: str
    label: str
    decay_rate: float
    fulfillment_base: float
    desperate_threshold: float = 10.0
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NeedDef":
        return cls(**data)


NEED_DEFS: dict[str, NeedDef] = {
    "eat": NeedDef("eat", "Hunger", decay_rate=0.8, fulfillment_base=60.0, desperate_threshold=10.0, weight=1.5),
    "drink": NeedDef("drink", "Thirst", decay_rate=1.0, fulfillment_base=70.0, desperate_threshold=10.0, weight=1.5),
    "sleep": NeedDef("sleep", "Rest", decay_rate=0.4, fulfillment_base=80.0, desperate_threshold=15.0, weight=1.2),
    "pray": NeedDef("pray", "Spirituality", decay_rate=0.2, fulfillment_base=40.0, desperate_threshold=5.0, weight=0.6),
    "socialize": NeedDef("socialize", "Social", decay_rate=0.3, fulfillment_base=35.0, desperate_threshold=10.0, weight=0.8),
    "craft": NeedDef("craft", "Industry", decay_rate=0.15, fulfillment_base=30.0, desperate_threshold=5.0, weight=0.5),
    "train": NeedDef("train", "Training", decay_rate=0.15, fulfillment_base=30.0, desperate_threshold=5.0, weight=0.5),
    "admire_art": NeedDef("admire_art", "Aesthetics", decay_rate=0.1, fulfillment_base=25.0, desperate_threshold=5.0, weight=0.4),
}


@dataclass
class QuestSeed:
    quest_id: str
    kind: str
    title: str
    priority: int = 3
    source_pressure: str = ""

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuestSeed":
        return cls(**data)


@dataclass
class MoraleCascade:
    tier: str
    unrest_min: int
    unrest_max: int
    work_speed_mult: float
    social_hostility: bool
    task_refusal: bool
    tantrum_risk: float

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MoraleCascade":
        return cls(**data)


MORALE_CASCADE_TIERS: list[MoraleCascade] = [
    MoraleCascade("content", 0, 25, work_speed_mult=1.0, social_hostility=False, task_refusal=False, tantrum_risk=0.0),
    MoraleCascade("unhappy", 25, 50, work_speed_mult=0.8, social_hostility=False, task_refusal=False, tantrum_risk=0.0),
    MoraleCascade("miserable", 50, 75, work_speed_mult=0.5, social_hostility=True, task_refusal=True, tantrum_risk=0.02),
    MoraleCascade("breakdown", 75, 101, work_speed_mult=0.2, social_hostility=True, task_refusal=True, tantrum_risk=0.10),
]


SHORTAGE_QUEST_MAP: dict[str, dict[str, Any]] = {
    "food": {"kind": "food", "title": "Address Food Pressure", "priority": 1},
    "materials": {"kind": "materials", "title": "Address Materials Pressure", "priority": 2},
    "security": {"kind": "security", "title": "Address Security Pressure", "priority": 1},
}


@dataclass
class JobRecord:
    job_id: str
    kind: str
    priority: int
    status: str
    assignee_id: str | None = None
    room_id: str | None = None
    skill_id: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobRecord":
        return cls(**data)


@dataclass
class ReactionDef:
    reaction_id: str
    label: str
    worksite_kind: str
    input_tags: list[str] = field(default_factory=list)
    output_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReactionDef":
        return cls(**data)


@dataclass
class WorksiteRecord:
    worksite_id: str
    label: str
    kind: str
    room_id: str | None = None
    supported_jobs: list[str] = field(default_factory=list)
    reaction_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorksiteRecord":
        return cls(**data)


@dataclass
class ProductionLedger:
    economy: dict[str, Any] = field(default_factory=dict)
    shortages: list[str] = field(default_factory=list)
    surpluses: list[str] = field(default_factory=list)
    quest_seeds: list[QuestSeed] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionLedger":
        return cls(
            economy=dict(data.get("economy", {})),
            shortages=[str(item) for item in data.get("shortages", [])],
            surpluses=[str(item) for item in data.get("surpluses", [])],
            quest_seeds=[
                item if isinstance(item, QuestSeed) else QuestSeed.from_dict(dict(item))
                for item in data.get("quest_seeds", [])
            ],
        )


@dataclass
class ColonyPressureState:
    food: int
    safety: int
    morale: int
    supply: int
    housing: int
    unrest: int
    shortages: list[str] = field(default_factory=list)
    pressure_tags: list[str] = field(default_factory=list)
    quest_seeds: list[QuestSeed] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColonyPressureState":
        return cls(
            food=int(data.get("food", 0)),
            safety=int(data.get("safety", 0)),
            morale=int(data.get("morale", 0)),
            supply=int(data.get("supply", 0)),
            housing=int(data.get("housing", 0)),
            unrest=int(data.get("unrest", 0)),
            shortages=[str(item) for item in data.get("shortages", [])],
            pressure_tags=[str(item) for item in data.get("pressure_tags", [])],
            quest_seeds=[
                item if isinstance(item, QuestSeed) else QuestSeed.from_dict(dict(item))
                for item in data.get("quest_seeds", [])
            ],
        )


def decay_needs(actor: ActorRecord, tick_count: int = 1) -> NeedState:
    for need_id, need_def in NEED_DEFS.items():
        current = float(actor.needs.values.get(need_id, 100.0))
        actor.needs.values[need_id] = max(0.0, current - (need_def.decay_rate * max(0, int(tick_count))))
    mood, modifiers = compute_mood(actor.needs)
    actor.needs.mood = mood
    actor.needs.modifiers = dict(modifiers)
    return actor.needs


def fulfill_need(actor: ActorRecord, need_id: str, facility_quality: int = 0) -> float:
    if need_id not in NEED_DEFS:
        raise KeyError(need_id)
    need_def = NEED_DEFS[need_id]
    amount = need_def.fulfillment_base * (1.0 + (int(facility_quality) * 0.1))
    old_value = float(actor.needs.values.get(need_id, 0.0))
    actor.needs.values[need_id] = min(100.0, old_value + amount)
    mood, modifiers = compute_mood(actor.needs)
    actor.needs.mood = mood
    actor.needs.modifiers = dict(modifiers)
    return actor.needs.values[need_id] - old_value


def compute_mood(needs: NeedState) -> tuple[str, dict[str, Any]]:
    total_weight = sum(need_def.weight for need_def in NEED_DEFS.values())
    if total_weight <= 0:
        return "steady", {}
    weighted = 0.0
    for need_id, need_def in NEED_DEFS.items():
        weighted += float(needs.values.get(need_id, 100.0)) * need_def.weight
    average = weighted / total_weight
    if average >= 75.0:
        return "content", {"work_speed_mult": 1.0}
    if average >= 50.0:
        return "unhappy", {"work_speed_mult": 0.8}
    if average >= 25.0:
        return "miserable", {
            "work_speed_mult": 0.5,
            "social_hostility": True,
            "task_refusal": True,
            "tantrum_risk": 0.02,
        }
    return "breakdown", {
        "work_speed_mult": 0.2,
        "social_hostility": True,
        "task_refusal": True,
        "tantrum_risk": 0.10,
    }


def apply_morale_cascade(actors: list[ActorRecord], unrest: int) -> None:
    tier = next(
        candidate
        for candidate in MORALE_CASCADE_TIERS
        if candidate.unrest_min <= int(unrest) < candidate.unrest_max
    )
    modifiers = {
        "work_speed_mult": tier.work_speed_mult,
        "social_hostility": tier.social_hostility,
        "task_refusal": tier.task_refusal,
        "tantrum_risk": tier.tantrum_risk,
    }
    for actor in actors:
        actor.needs.mood = tier.tier
        actor.needs.modifiers = dict(modifiers)


def quest_seeds_from_shortages(shortages: list[str]) -> list[QuestSeed]:
    seeds: list[QuestSeed] = []
    for shortage in shortages:
        template = SHORTAGE_QUEST_MAP.get(
            shortage,
            {"kind": shortage, "title": f"Address {shortage.title()} Pressure", "priority": 3},
        )
        seeds.append(
            QuestSeed(
                quest_id=f"pressure_{shortage}",
                kind=str(template["kind"]),
                title=str(template["title"]),
                priority=int(template["priority"]),
                source_pressure=str(shortage),
            )
        )
    return seeds


def pressure_tags_from_metrics(
    *,
    food: int,
    safety: int,
    morale: int,
    supply: int,
    housing: int,
    unrest: int,
) -> list[str]:
    pressure_tags: list[str] = []
    if int(food) < 55:
        pressure_tags.append("food_insecure")
    if int(safety) < 55:
        pressure_tags.append("unsafe")
    if int(supply) < 55:
        pressure_tags.append("resource_strain")
    if int(housing) < 55:
        pressure_tags.append("housing_strain")
    if int(unrest) >= 50:
        pressure_tags.append("unrest")
    if int(housing) > 80 and int(morale) > 70 and int(food) > 60:
        pressure_tags.append("migration_candidate")
    return pressure_tags


def room_morale_bonus(rooms: list[dict[str, Any]]) -> int:
    bonus = 0
    for room in rooms:
        if _room_has_required_furniture(room):
            bonus += 2
    return bonus


def job_records_from_settlement(settlement_state: dict[str, Any]) -> list[JobRecord]:
    records: list[JobRecord] = []
    for job in settlement_state.get("jobs", []):
        records.append(
            JobRecord(
                job_id=str(job.get("id", "")),
                kind=str(job.get("kind", "unknown")),
                priority=int(job.get("priority", 3)),
                status=str(job.get("status", "idle")),
                assignee_id=job.get("assignee_id"),
                room_id=job.get("room_id"),
                skill_id=_skill_for_job_kind(str(job.get("kind", "unknown"))),
                tags=list(job.get("tags", [])),
            )
        )
    for queue_index, build in enumerate(settlement_state.get("construction_queue", [])):
        records.append(
            JobRecord(
                job_id=str(build.get("id", f"construction_{queue_index}")),
                kind=str(build.get("kind", "construction")),
                priority=int(build.get("priority", 4)),
                status=str(build.get("status", "queued")),
                room_id=build.get("room_id"),
                skill_id="construction",
                tags=["construction"],
            )
        )
    return records


def reaction_defs_from_settlement(settlement_state: dict[str, Any]) -> list[ReactionDef]:
    reactions: list[ReactionDef] = []
    seen: set[str] = set()
    for room in settlement_state.get("rooms", []):
        for workstation in room.get("workstations", []):
            reaction_id = f"{workstation}_reaction"
            if reaction_id in seen:
                continue
            seen.add(reaction_id)
            reactions.append(
                ReactionDef(
                    reaction_id=reaction_id,
                    label=str(workstation).replace("_", " ").title(),
                    worksite_kind=str(workstation),
                    input_tags=_input_tags_for_worksite(str(workstation)),
                    output_tags=_output_tags_for_worksite(str(workstation)),
                )
            )
    return reactions


def worksite_records_from_settlement(settlement_state: dict[str, Any]) -> list[WorksiteRecord]:
    reactions = reaction_defs_from_settlement(settlement_state)
    reaction_lookup = {reaction.worksite_kind: reaction.reaction_id for reaction in reactions}
    worksites: list[WorksiteRecord] = []
    for room in settlement_state.get("rooms", []):
        supported_jobs = [
            str(workstation)
            for workstation in room.get("workstations", [])
        ]
        worksites.append(
            WorksiteRecord(
                worksite_id=str(room.get("id", "")),
                label=str(room.get("label", room.get("kind", "Room"))),
                kind=str(room.get("kind", "room")),
                room_id=str(room.get("id", "")),
                supported_jobs=supported_jobs,
                reaction_ids=[
                    reaction_lookup[workstation]
                    for workstation in supported_jobs
                    if workstation in reaction_lookup
                ],
            )
        )
    return worksites


def production_ledger_from_settlement(settlement_state: dict[str, Any]) -> ProductionLedger:
    needs = dict(settlement_state.get("needs", {}))
    economy = dict(settlement_state.get("economy", {}))
    shortages: list[str] = []
    surpluses: list[str] = []
    if int(needs.get("food", 0)) >= 3:
        shortages.append("food")
    else:
        surpluses.append("food")
    if int(needs.get("materials", 0)) >= 3:
        shortages.append("materials")
    else:
        surpluses.append("materials")
    if int(needs.get("security", 0)) >= 3:
        shortages.append("security")
    else:
        surpluses.append("security")
    if float(economy.get("trade_balance", 0)) > 0:
        surpluses.append("trade")
    quest_seeds = quest_seeds_from_shortages(shortages)
    return ProductionLedger(
        economy=economy,
        shortages=shortages,
        surpluses=surpluses,
        quest_seeds=quest_seeds,
    )


def colony_pressure_from_settlement(settlement_state: dict[str, Any]) -> ColonyPressureState:
    needs = dict(settlement_state.get("needs", {}))
    alerts = list(settlement_state.get("alerts", []))
    residents = list(settlement_state.get("residents", []))
    rooms = list(settlement_state.get("rooms", []))
    drafted = sum(1 for resident in residents if resident.get("drafted"))
    beds = sum(int(room.get("beds", 0)) for room in rooms)
    historical_pressure = list(settlement_state.get("faction_pressure", []))
    ledger = production_ledger_from_settlement(settlement_state)
    active_farms = _active_farm_plot_count(list(settlement_state.get("farm_plots", [])))
    effective_food_need = max(0, int(needs.get("food", 0)) - active_farms)
    room_bonus = room_morale_bonus(rooms)

    food = max(0, 100 - effective_food_need * 15)
    safety = max(0, 100 - len(alerts) * 12 - int(needs.get("security", 0)) * 10 + drafted * 5)
    morale = max(0, 100 - len(alerts) * 8 - len(ledger.shortages) * 10 + room_bonus)
    supply = max(0, 100 - int(needs.get("materials", 0)) * 15 - len(settlement_state.get("construction_queue", [])) * 6)
    housing_gap = max(0, len(residents) - max(1, beds))
    housing = max(0, 100 - housing_gap * 20)
    unrest = min(100, len(alerts) * 14 + len(ledger.shortages) * 12 + len(historical_pressure) * 6)

    pressure_tags = pressure_tags_from_metrics(
        food=food,
        safety=safety,
        morale=morale,
        supply=supply,
        housing=housing,
        unrest=unrest,
    )

    return ColonyPressureState(
        food=food,
        safety=safety,
        morale=morale,
        supply=supply,
        housing=housing,
        unrest=unrest,
        shortages=ledger.shortages,
        pressure_tags=pressure_tags,
        quest_seeds=ledger.quest_seeds,
    )


def _room_has_required_furniture(room: dict[str, Any]) -> bool:
    if room.get("required_furniture_present") is False:
        return False
    if room.get("furnished") is False:
        return False
    if int(room.get("beds", 0)) > 0:
        return True
    if room.get("kind") in {"bedroom", "dormitory"}:
        return False
    return True


def _active_farm_plot_count(farm_plots: list[dict[str, Any]]) -> int:
    return sum(
        1
        for plot in farm_plots
        if bool(plot.get("active"))
        and str(plot.get("status", "active")) not in {"fallow", "unharvested"}
    )


def _skill_for_job_kind(kind: str) -> str:
    mapping = {
        "forge": "smithing",
        "hauling": "duty",
        "construction": "construction",
        "bar_counter": "trade",
        "altar": "divine_magic",
        "bed": "healing",
    }
    return mapping.get(kind, kind)


def _input_tags_for_worksite(kind: str) -> list[str]:
    mapping = {
        "forge": ["ore", "fuel"],
        "bar_counter": ["drink", "trade_goods"],
        "bookshelf": ["books", "records"],
        "bed": ["cloth", "rest"],
        "altar": ["relics", "offerings"],
    }
    return mapping.get(kind, [kind])


def _output_tags_for_worksite(kind: str) -> list[str]:
    mapping = {
        "forge": ["weapons", "armor", "tools"],
        "bar_counter": ["morale", "commerce"],
        "bookshelf": ["knowledge"],
        "bed": ["recovery"],
        "altar": ["faith", "stability"],
    }
    return mapping.get(kind, [kind])


def _quest_seeds_from_shortages(shortages: list[str]) -> list[dict[str, Any]]:
    return [seed.to_dict() for seed in quest_seeds_from_shortages(shortages)]

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value


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
    quest_seeds: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionLedger":
        return cls(
            economy=dict(data.get("economy", {})),
            shortages=[str(item) for item in data.get("shortages", [])],
            surpluses=[str(item) for item in data.get("surpluses", [])],
            quest_seeds=[dict(item) for item in data.get("quest_seeds", [])],
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
    quest_seeds: list[dict[str, Any]] = field(default_factory=list)

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
            quest_seeds=[dict(item) for item in data.get("quest_seeds", [])],
        )


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
    quest_seeds = _quest_seeds_from_shortages(shortages)
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

    food = max(0, 100 - int(needs.get("food", 0)) * 15)
    safety = max(0, 100 - len(alerts) * 12 - int(needs.get("security", 0)) * 10 + drafted * 5)
    morale = max(0, 100 - len(alerts) * 8 - len(ledger.shortages) * 10 + len(rooms) * 2)
    supply = max(0, 100 - int(needs.get("materials", 0)) * 15 - len(settlement_state.get("construction_queue", [])) * 6)
    housing_gap = max(0, len(residents) - max(1, beds))
    housing = max(0, 100 - housing_gap * 20)
    unrest = min(100, len(alerts) * 14 + len(ledger.shortages) * 12 + len(historical_pressure) * 6)

    pressure_tags: list[str] = []
    if food < 55:
        pressure_tags.append("food_insecure")
    if safety < 55:
        pressure_tags.append("unsafe")
    if supply < 55:
        pressure_tags.append("resource_strain")
    if housing < 55:
        pressure_tags.append("housing_strain")
    if unrest >= 50:
        pressure_tags.append("unrest")

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
    seeds: list[dict[str, Any]] = []
    for shortage in shortages:
        seeds.append(
            {
                "quest_id": f"pressure_{shortage}",
                "kind": shortage,
                "title": f"Address {shortage.title()} Pressure",
            }
        )
    return seeds

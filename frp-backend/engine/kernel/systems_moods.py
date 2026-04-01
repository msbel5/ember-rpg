from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord, ConditionRecord, ItemStack
from engine.kernel.colony import ColonyPressureState
from engine.kernel.common import serialize_value


@dataclass
class MaterialDemand:
    material_tag: str
    satisfied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialDemand":
        return cls(**data)


@dataclass
class StrangeMoodIncident:
    incident_id: str
    state: str
    trigger_reason: str
    mood_type: str = ""
    actor_id: str = ""
    claimed_worksite_id: str = ""
    material_demands: list[MaterialDemand] = field(default_factory=list)
    timeout_ticks: int = 500
    elapsed_ticks: int = 0
    artifact_item_id: str | None = None
    candidate_actor_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrangeMoodIncident":
        payload = dict(data)
        payload["material_demands"] = [
            item if isinstance(item, MaterialDemand) else MaterialDemand.from_dict(dict(item))
            for item in payload.get("material_demands", [])
        ]
        payload["candidate_actor_ids"] = [str(item) for item in payload.get("candidate_actor_ids", [])]
        return cls(**payload)


def tick_strange_mood(
    incident: StrangeMoodIncident,
    settlement: dict,
    actors: list[ActorRecord],
    seed: int,
) -> StrangeMoodIncident:
    actor_map = {actor.identity.actor_id: actor for actor in actors}
    if incident.state == "triggered":
        chosen = next(
            (actor for actor in actors if actor.identity.actor_id in incident.candidate_actor_ids and moodable(actor)),
            None,
        )
        if chosen is None:
            return incident
        incident.actor_id = chosen.identity.actor_id
        incident.mood_type = choose_mood_type(chosen)
        worksites = settlement.get("worksites", [])
        incident.claimed_worksite_id = str(worksites[0]["id"]) if worksites else ""
        if not incident.material_demands:
            incident.material_demands = [MaterialDemand("metal_bar")]
        incident.state = "demanding_materials"
        return incident

    if incident.state == "demanding_materials":
        incident.elapsed_ticks += 1
        available = {str(item) for item in settlement.get("available_materials", [])}
        all_satisfied = True
        for demand in incident.material_demands:
            if demand.material_tag in available:
                demand.satisfied = True
            all_satisfied = all_satisfied and demand.satisfied
        if all_satisfied:
            incident.state = "working"
            return incident
        if incident.elapsed_ticks >= incident.timeout_ticks:
            incident.state = "failed"
            apply_mood_failure(actor_map.get(incident.actor_id), incident.mood_type)
        return incident

    if incident.state == "working" and incident.artifact_item_id is None:
        actor = actor_map.get(incident.actor_id)
        if actor is None:
            return incident
        artifact = create_artifact(incident, actor, seed)
        incident.artifact_item_id = artifact.instance_id
        incident.state = "completed"
        return incident

    if incident.state == "failed":
        apply_mood_failure(actor_map.get(incident.actor_id), incident.mood_type)
    return incident


def create_artifact(incident: StrangeMoodIncident, actor: ActorRecord, seed: int) -> ItemStack:
    suffix = abs(int(seed)) % 100000
    actor.skills["crafting"] = 20
    actor.raw_payload["morale_bonus"] = int(actor.raw_payload.get("morale_bonus", 0)) + 25
    return ItemStack(
        instance_id=f"artifact_{incident.incident_id}_{suffix}",
        item_def_id="artifact_item",
        quantity=1,
        quality=6,
        tags=["artifact"],
        payload={"value_multiplier": 120, "combat_multiplier": 3},
    )


def strange_mood_incident_from_settlement(
    settlement_state: dict[str, Any],
    colony_pressure: ColonyPressureState,
) -> StrangeMoodIncident | None:
    if not settlement_state.get("jobs"):
        return None
    if colony_pressure.morale > 75 and colony_pressure.unrest < 35:
        return None
    candidates = [
        str(resident.get("id"))
        for resident in settlement_state.get("residents", [])
        if str(resident.get("role")) not in {"commander", "guard"}
    ]
    return StrangeMoodIncident(
        incident_id="creative_pressure_event",
        state="triggered",
        trigger_reason="morale_pressure" if colony_pressure.morale < 70 else "unrest_pressure",
        candidate_actor_ids=candidates[:3],
    )


def moodable(actor: ActorRecord) -> bool:
    return any(int(value) > 0 for value in actor.skills.values())


def choose_mood_type(actor: ActorRecord) -> str:
    personality = str(actor.raw_payload.get("personality", "calm")).lower()
    if personality in {"violent", "cruel"}:
        return "fell"
    if personality in {"grim", "dark"}:
        return "macabre"
    if personality in {"obsessive", "secretive"}:
        return "secretive"
    if personality in {"creative", "artistic"}:
        return "fey_crafter"
    return "possessed"


def apply_mood_failure(actor: ActorRecord | None, mood_type: str) -> None:
    if actor is None:
        return
    outcome = "melancholy" if mood_type in {"fey_crafter", "secretive"} else "insane"
    if outcome == "insane" and mood_type == "fell":
        outcome = "insane"
    actor.conditions.append(ConditionRecord(condition_id=f"mood_{outcome}", name=outcome, severity=10))


__all__ = [
    "MaterialDemand",
    "StrangeMoodIncident",
    "create_artifact",
    "strange_mood_incident_from_settlement",
    "tick_strange_mood",
]

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord
from engine.kernel.common import serialize_value
from engine.kernel.colony import ColonyPressureState
from engine.worldgen.models import RegionSnapshot


@dataclass
class SyndromeEffect:
    effect_id: str
    effect_type: str
    severity: int
    target: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class SyndromeDef:
    syndrome_id: str
    name: str
    delivery: str
    effects: list[SyndromeEffect] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class PowerNodeState:
    node_id: str
    kind: str
    role: str
    power_delta: int

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class PowerNetworkState:
    nodes: list[PowerNodeState] = field(default_factory=list)
    total_available: int = 0
    total_required: int = 0
    active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class TrapState:
    trap_id: str
    trap_type: str
    armed: bool
    trigger: str

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class FluidState:
    fluid_counts: dict[str, int] = field(default_factory=dict)
    pressure_enabled: bool = False
    muddy_floor_risk: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class TemperatureState:
    ambient_band: str
    hazardous: bool = False
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class StrangeMoodIncident:
    incident_id: str
    state: str
    trigger_reason: str
    candidate_actor_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


def syndrome_registry_from_actors(actors: list[ActorRecord]) -> list[SyndromeDef]:
    registry: list[SyndromeDef] = []
    seen: set[str] = set()
    for actor in actors:
        for condition in actor.conditions:
            syndrome_id = f"condition::{condition.condition_id}"
            if syndrome_id in seen:
                continue
            seen.add(syndrome_id)
            registry.append(
                SyndromeDef(
                    syndrome_id=syndrome_id,
                    name=condition.name,
                    delivery="contact",
                    effects=[
                        SyndromeEffect(
                            effect_id=f"{condition.condition_id}::severity",
                            effect_type=condition.name,
                            severity=int(condition.severity),
                            target="actor",
                        )
                    ],
                )
            )
        if actor.body_state is None:
            continue
        for condition in actor.body_state.conditions:
            syndrome_id = f"body_condition::{condition.condition_id}"
            if syndrome_id in seen:
                continue
            seen.add(syndrome_id)
            registry.append(
                SyndromeDef(
                    syndrome_id=syndrome_id,
                    name=condition.name,
                    delivery="body_state",
                    effects=[
                        SyndromeEffect(
                            effect_id=f"{condition.condition_id}::severity",
                            effect_type=condition.name,
                            severity=int(condition.severity),
                            target="body",
                        )
                    ],
                )
            )
    return registry


def power_network_from_settlement(settlement_state: dict[str, Any]) -> PowerNetworkState:
    nodes: list[PowerNodeState] = []
    for room in settlement_state.get("rooms", []):
        for workstation in room.get("workstations", []):
            workstation_id = f"{room.get('id', 'room')}::{workstation}"
            if workstation in {"well", "windmill", "waterwheel"}:
                nodes.append(PowerNodeState(node_id=workstation_id, kind=str(workstation), role="source", power_delta=20))
            elif workstation in {"forge", "loom", "press", "bar_counter"}:
                nodes.append(PowerNodeState(node_id=workstation_id, kind=str(workstation), role="consumer", power_delta=-10))
    total_available = sum(node.power_delta for node in nodes if node.power_delta > 0)
    total_required = abs(sum(node.power_delta for node in nodes if node.power_delta < 0))
    return PowerNetworkState(
        nodes=nodes,
        total_available=total_available,
        total_required=total_required,
        active=total_available >= total_required if total_required > 0 else total_available > 0,
    )


def trap_state_from_settlement(settlement_state: dict[str, Any]) -> list[TrapState]:
    defense_posture = str(settlement_state.get("defense_posture", "normal"))
    if defense_posture != "fortified":
        return []
    return [
        TrapState(trap_id="gate_spikes", trap_type="upright_spike", armed=True, trigger="pressure_plate"),
        TrapState(trap_id="courtyard_alarm", trap_type="lever_alarm", armed=True, trigger="lever"),
    ]


def fluid_state_from_region(region_snapshot: RegionSnapshot) -> FluidState:
    counts: dict[str, int] = {"water": 0, "magma": 0}
    for row in region_snapshot.typed_tiles:
        for tile in row:
            terrain = str(tile.get("terrain", ""))
            if terrain == "water":
                counts["water"] += 1
            if terrain in {"lava", "magma"}:
                counts["magma"] += 1
    return FluidState(
        fluid_counts=counts,
        pressure_enabled=counts["water"] > 8,
        muddy_floor_risk=counts["water"] > 0 and any(str(tile.get("terrain", "")) == "floor" for row in region_snapshot.typed_tiles for tile in row),
    )


def temperature_state_from_region(region_snapshot: RegionSnapshot) -> TemperatureState:
    biome = str(region_snapshot.biome_id).lower()
    if "arctic" in biome or "ice" in biome or "tundra" in biome:
        return TemperatureState(ambient_band="cold", hazardous=False, tags=["freezing_risk"])
    if "desert" in biome or "volcanic" in biome or "lava" in biome:
        return TemperatureState(ambient_band="hot", hazardous=True, tags=["burn_risk"])
    return TemperatureState(ambient_band="temperate", hazardous=False, tags=[])


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
        state="brewing",
        trigger_reason="morale_pressure" if colony_pressure.morale < 70 else "unrest_pressure",
        candidate_actor_ids=candidates[:3],
    )

from __future__ import annotations

import copy
from typing import Any

from engine.kernel import (
    FluidState,
    PowerNetworkState,
    StrangeMoodIncident,
    SyndromeDef,
    TemperatureState,
    TrapState,
    WoundRecord,
    check_drowning,
    check_magma_damage,
    check_trap_triggers,
    colony_pressure_from_settlement,
    compute_power_network,
    fluid_state_from_region,
    power_network_from_settlement,
    resolve_trap_damage,
    strange_mood_incident_from_settlement,
    syndrome_registry_from_actors,
    temperature_state_from_region,
    tick_fluids,
    tick_strange_mood,
    tick_temperature,
    trap_state_from_settlement,
)

from .runtime_common import saved_or


def systems_events(context, runtime: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    systems = runtime["systems"]
    actors = list(runtime["actors"].values())
    terrain = copy.deepcopy(context.region_snapshot.typed_tiles)
    if not systems["traps"]:
        systems["traps"] = trap_state_from_settlement(context.settlement_state)
    systems["power_network"] = compute_power_network(context.settlement_state)
    systems["fluid_state"] = tick_fluids(systems["fluid_state"], terrain)
    events: list[dict[str, Any]] = []
    for actor in actors:
        if check_drowning(actor, systems["fluid_state"]):
            events.append({"event_type": "drowning", "summary": f"{actor.identity.display_name} drowned."})
        magma_wound = check_magma_damage(actor, systems["fluid_state"])
        if magma_wound is not None:
            events.append({"event_type": "magma", "summary": f"{actor.identity.display_name} was burned by magma."})
    for temp_event in tick_temperature(systems["temperature_state"], actors):
        actor = runtime["actors"].get(temp_event.get("actor_id"))
        if actor is not None and actor.body_state is not None and temp_event["type"] in {"frostbite", "heat"}:
            actor.body_state.apply_wound(
                WoundRecord.from_dict(
                    {
                        "wound_id": f"{temp_event['type']}:{temp_event['actor_id']}:{len(actor.body_state.wounds)}",
                        "body_part_id": "torso",
                        "damage_type": "cold" if temp_event["type"] == "frostbite" else "fire",
                        "damage_amount": 6,
                        "bleeding": 0,
                        "pain": 6,
                        "open_wound": temp_event["type"] == "heat",
                        "untreated": True,
                    }
                )
            )
        events.append({"event_type": temp_event["type"], "summary": str(temp_event)})
    trap_positions = {str(key): tuple(value) for key, value in dict(context.settlement_state.get("trap_positions", {})).items()}
    unit_positions = {
        actor.identity.actor_id: {"position": [actor.position.x, actor.position.y], "tags": list(actor.identity.tags)}
        for actor in actors
    }
    for event in check_trap_triggers(systems["traps"], unit_positions, trap_positions):
        target = runtime["actors"].get(event["target_actor_id"])
        trap = next((item for item in systems["traps"] if item.trap_id == event["trap_id"]), None)
        if target is None or trap is None:
            continue
        resolve_trap_damage(trap, target, seed)
        events.append({"event_type": "trap_triggered", "summary": f"{target.identity.display_name} triggered {trap.trap_id}."})
    incident = systems.get("strange_mood_incident")
    if incident is None:
        incident = strange_mood_incident_from_settlement(context.settlement_state, runtime["colony_pressure"])
    if incident is not None:
        context.settlement_state["worksites"] = [worksite.to_dict() for worksite in runtime["worksites"]]
        systems["strange_mood_incident"] = tick_strange_mood(incident, context.settlement_state, actors, seed)
    systems["syndrome_registry"] = syndrome_registry_from_actors(actors)
    return events


def load_systems(saved_payload: Any, context) -> dict[str, Any]:
    if isinstance(saved_payload, dict):
        return {
            "syndrome_registry": [
                item if isinstance(item, SyndromeDef) else SyndromeDef.from_dict(dict(item))
                for item in saved_payload.get("syndrome_registry", [])
            ],
            "power_network": saved_or(
                saved_payload.get("power_network"),
                PowerNetworkState,
                lambda: power_network_from_settlement(context.settlement_state),
            ),
            "traps": [
                item if isinstance(item, TrapState) else TrapState.from_dict(dict(item))
                for item in saved_payload.get("traps", [])
            ],
            "fluid_state": saved_or(
                saved_payload.get("fluid_state"),
                FluidState,
                lambda: fluid_state_from_region(context.region_snapshot),
            ),
            "temperature_state": saved_or(
                saved_payload.get("temperature_state"),
                TemperatureState,
                lambda: temperature_state_from_region(context.region_snapshot),
            ),
            "strange_mood_incident": saved_or(
                saved_payload.get("strange_mood_incident"),
                StrangeMoodIncident,
                lambda: None,
            ),
        }
    colony_pressure = colony_pressure_from_settlement(context.settlement_state)
    return {
        "syndrome_registry": [],
        "power_network": power_network_from_settlement(context.settlement_state),
        "traps": trap_state_from_settlement(context.settlement_state),
        "fluid_state": fluid_state_from_region(context.region_snapshot),
        "temperature_state": temperature_state_from_region(context.region_snapshot),
        "strange_mood_incident": strange_mood_incident_from_settlement(context.settlement_state, colony_pressure),
    }


__all__ = ["load_systems", "systems_events"]

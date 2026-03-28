"""Always-on deterministic world runtime tickers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .economy import initialize_region_economy, tick_region_economy
from .models import GlobalTickResult, SimulationSnapshot, WorldBlueprint
from .npc_generator import runtime_npc_state
from .quest_generator import generate_quest_offers
from .settlement_generator import generate_settlement_layout
from .world_seed import stable_seed_from_parts


def _season_for_day(day: int) -> str:
    seasons = ["spring", "summer", "autumn", "winter"]
    return seasons[((max(day, 1) - 1) // 30) % len(seasons)]


def _weather_for(seed: int, biome_id: str, day: int) -> dict[str, Any]:
    roll = stable_seed_from_parts(seed, "weather", biome_id, day) % 100
    if biome_id == "desert":
        kind = "dry_wind" if roll < 70 else "dust_storm"
        rainfall = 0.02
    elif biome_id == "coast":
        kind = "sea_mist" if roll < 45 else "rain"
        rainfall = 0.55 if kind == "rain" else 0.22
    elif biome_id == "swamp":
        kind = "fog" if roll < 55 else "rain"
        rainfall = 0.62
    elif biome_id == "mountain":
        kind = "cold_clear" if roll < 60 else "storm"
        rainfall = 0.25 if kind == "cold_clear" else 0.48
    else:
        kind = "clear" if roll < 45 else "rain"
        rainfall = 0.18 if kind == "clear" else 0.44
    return {"kind": kind, "rainfall": round(rainfall, 2), "severe": kind in {"dust_storm", "storm"}}


def _build_region_state(world: WorldBlueprint, region: dict[str, Any], active_region_id: str) -> dict[str, Any]:
    settlement = next((item for item in world.settlements if item.region_id == region["id"]), None)
    population = sum(item.population for item in world.settlements if item.region_id == region["id"])
    state = {
        "population": population,
        "resources": list(region.get("resources", [])),
        "stability": round(0.5 + region["settlement_score"] * 0.3, 3),
        "prosperity": round(50 + region["settlement_score"] * 25, 3),
        "resolution": "fine" if region["id"] == active_region_id else "coarse",
        "day": 1,
        "season": "spring",
        "weather": _weather_for(world.seed, str(region["biome_id"]), 1),
        "alerts": [],
        "active_quests": [],
        "quest_offers": [],
        "npcs": [],
        "economy": {"resources": {"food": 0, "ore": 0, "wood": 0, "gold": 0}, "prices": {}, "trade_routes": [], "scarcity": {}},
    }
    if settlement is None:
        return state

    layout = generate_settlement_layout(world, region["id"])
    state["npcs"] = runtime_npc_state(layout.npc_spawns, 0)
    state["economy"] = initialize_region_economy(region, settlement)
    settlement_state = {
        "name": settlement.center_name,
        "needs": {
            "food": max(1, settlement.population // 30),
            "security": max(1, len(state["npcs"]) // 4),
            "materials": max(1, len(layout.furniture) // 5),
        },
        "economy": deepcopy(state["economy"]),
        "alerts": [],
    }
    state["quest_offers"] = generate_quest_offers(
        world_seed=world.seed,
        region=region,
        settlement_state=settlement_state,
        npcs=state["npcs"],
        day=1,
        limit=6,
    )
    return state


def initialize_simulation(world: WorldBlueprint, start_region_id: str | None = None) -> WorldBlueprint:
    active_region_id = start_region_id
    if active_region_id is None:
        active_region_id = world.settlements[0].region_id if world.settlements else world.regions[0]["id"]
    region_states = {
        region["id"]: _build_region_state(world, region, active_region_id)
        for region in world.regions
    }
    faction_states = {
        faction.id: {
            "culture_id": faction.culture_id,
            "influence": faction.traits.get("influence", 0.5),
            "cohesion": faction.traits.get("cohesion", 0.5),
        }
        for faction in world.factions
    }
    world.simulation_snapshot = SimulationSnapshot(
        current_year=world.history_end_year,
        current_hour=0,
        current_day=1,
        season="spring",
        active_region_id=active_region_id,
        region_states=region_states,
        faction_states=faction_states,
        pending_events=[],
    )
    return world


def _tick_region(world: WorldBlueprint, region: dict[str, Any], state: dict[str, Any], current_hour: int, current_day: int, is_active: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    settlement = next((item for item in world.settlements if item.region_id == region["id"]), None)
    next_state = deepcopy(state)
    events: list[dict[str, Any]] = []
    next_state["resolution"] = "fine" if is_active else "coarse"
    next_state["day"] = current_day
    next_state["season"] = _season_for_day(current_day)
    weather = _weather_for(world.seed, str(region["biome_id"]), current_day)
    next_state["weather"] = weather
    next_state["prosperity"] = round(float(next_state.get("prosperity", 50.0)) + (0.08 if is_active else 0.03) * max(current_hour, 1), 3)

    if settlement is None:
        return next_state, events

    next_state["npcs"] = runtime_npc_state(list(next_state.get("npcs", [])), current_hour)
    next_state["economy"] = tick_region_economy(
        next_state.get("economy", {}),
        max(current_hour, 1),
        weather,
        int(settlement.population),
    )
    alerts: list[str] = []
    economy = next_state["economy"]
    resources = economy.get("resources", {})
    needs = {
        "food": max(1, settlement.population // 30),
        "security": max(1, len(next_state["npcs"]) // 4),
        "materials": max(1, len(region.get("resources", [])) // 2 or 1),
    }
    if int(resources.get("food", 0)) < 24:
        alerts.append("famine_risk")
        events.append({"event_type": "famine_risk", "region_id": region["id"], "summary": f"Food stores in {settlement.center_name} are running low."})
    if not any(npc.get("role") in {"healer", "priest", "alchemist"} for npc in next_state["npcs"]):
        alerts.append("plague_risk")
        events.append({"event_type": "plague_risk", "region_id": region["id"], "summary": f"{settlement.center_name} lacks a reliable healer."})
    if sum(1 for npc in next_state["npcs"] if npc.get("role") in {"guard", "warden"}) < 2:
        alerts.append("bandit_raid")
        events.append({"event_type": "bandit_raid", "region_id": region["id"], "summary": f"Raiders are probing the outskirts of {settlement.center_name}."})
    next_state["alerts"] = alerts[:4]
    settlement_state = {
        "name": settlement.center_name,
        "needs": needs,
        "economy": deepcopy(economy),
        "alerts": list(next_state["alerts"]),
    }
    next_state["quest_offers"] = generate_quest_offers(
        world_seed=world.seed,
        region=region,
        settlement_state=settlement_state,
        npcs=next_state["npcs"],
        day=current_day,
        limit=6,
    )
    return next_state, events


def tick_global(world: WorldBlueprint, hours: int) -> GlobalTickResult:
    if hours < 0:
        raise ValueError("hours must be >= 0")
    if world.simulation_snapshot is None:
        initialize_simulation(world)
    assert world.simulation_snapshot is not None
    snapshot = SimulationSnapshot.from_dict(world.simulation_snapshot.to_dict())
    snapshot.current_hour += hours
    snapshot.current_day = snapshot.current_hour // 24 + 1
    snapshot.season = _season_for_day(snapshot.current_day)
    current_hour_of_day = snapshot.current_hour % 24

    updated_regions: list[str] = []
    generated_events: list[dict[str, Any]] = []
    active_region_id = snapshot.active_region_id
    for region in world.regions:
        region_id = str(region["id"])
        updated_regions.append(region_id)
        next_state, events = _tick_region(
            world,
            region,
            snapshot.region_states.get(region_id, {}),
            current_hour_of_day,
            snapshot.current_day,
            region_id == active_region_id,
        )
        snapshot.region_states[region_id] = next_state
        generated_events.extend(events)
    if active_region_id is not None:
        generated_events.insert(
            0,
            {
                "event_type": "active_region_update",
                "region_id": active_region_id,
                "hours": hours,
                "severity": "info",
                "summary": f"{active_region_id} advanced by {hours}h.",
            },
        )
    inactive_region_id = next(
        (region_id for region_id in updated_regions if region_id != active_region_id),
        None,
    )
    if inactive_region_id is not None:
        generated_events.append(
            {
                "event_type": "inactive_region_shift",
                "region_id": inactive_region_id,
                "hours": hours,
                "severity": "info",
                "summary": f"{inactive_region_id} progressed off-screen by {hours}h.",
            }
        )
    snapshot.pending_events.extend(generated_events)
    world.simulation_snapshot = snapshot
    active_region_snapshot = (
        {"region_id": active_region_id, "state": deepcopy(snapshot.region_states[active_region_id])}
        if active_region_id is not None
        else None
    )
    return GlobalTickResult(hours, updated_regions, generated_events, snapshot, active_region_snapshot)

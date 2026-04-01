"""Historical event simulation for deterministic worldgen."""
from __future__ import annotations

import random

from .models import HistoricalEvent, WorldBlueprint


def simulate_history(world: WorldBlueprint, end_year: int | None = None) -> WorldBlueprint:
    target_year = end_year or world.history_end_year
    rng = random.Random(world.seed + target_year)
    events: list[HistoricalEvent] = []
    for index, faction in enumerate(world.factions):
        settlement = next((item for item in world.settlements if item.faction_id == faction.id), None)
        anchor_region_id = settlement.region_id if settlement is not None else faction.origin_region_id
        if index % 2 == 0:
            event_type = "migration"
            summary = f"{faction.id} pushed settlers beyond {anchor_region_id}."
            consequences = {"new_frontier": anchor_region_id, "pressure": round(rng.uniform(0.2, 0.6), 3)}
        else:
            event_type = "trade_route"
            summary = f"{faction.id} established a trade route through {anchor_region_id}."
            consequences = {"trade_value": round(rng.uniform(0.3, 0.9), 3)}
        events.append(
            HistoricalEvent(
                year=target_year - 180 + index * 21,
                event_type=event_type,
                factions=[faction.id],
                regions=[anchor_region_id],
                summary=summary,
                consequences=consequences,
            )
        )
    if len(world.factions) >= 2:
        first, second = world.factions[:2]
        events.append(
            HistoricalEvent(
                year=target_year - 62,
                event_type="war",
                factions=[first.id, second.id],
                regions=[first.origin_region_id, second.origin_region_id],
                summary=f"{first.id} and {second.id} fought over contested uplands.",
                consequences={"winner": first.id, "loser": second.id, "casualties": "moderate"},
            )
        )
        first.traits["influence"] = round(first.traits["influence"] + 0.08, 3)
        second.traits["influence"] = round(max(0.1, second.traits["influence"] - 0.05), 3)
    if world.settlements:
        settlement = world.settlements[0]
        events.append(
            HistoricalEvent(
                year=target_year - 19,
                event_type="disaster",
                factions=[settlement.faction_id],
                regions=[settlement.region_id],
                summary=f"Flooding reshaped the approaches to {settlement.center_name}.",
                consequences={"infrastructure_loss": 0.2, "rebuild_pressure": 0.4},
            )
        )
        settlement.population = max(120, settlement.population - 20)
    events.sort(key=lambda event: (event.year, event.event_type, ",".join(event.factions)))
    world.historical_events = events
    world.history_end_year = target_year
    return world


__all__ = ["simulate_history"]

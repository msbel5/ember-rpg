"""Historical event simulation for deterministic worldgen."""
from __future__ import annotations

import random

from .models import HistoricalEvent, WorldBlueprint


def _history_years(target_year: int, count: int) -> list[int]:
    event_count = max(8, count)
    if event_count == 1:
        return [1]
    segment = max(42, target_year // max(event_count - 1, 1))
    years: list[int] = [1]
    for index in range(1, event_count - 1):
        anchor = max(1, index * segment)
        years.append(anchor)
    years.append(target_year)
    return years


def simulate_history(world: WorldBlueprint, end_year: int | None = None) -> WorldBlueprint:
    target_year = end_year or world.history_end_year
    rng = random.Random(world.seed + target_year)
    events: list[HistoricalEvent] = []
    factions = list(world.factions)
    settlements = list(world.settlements)
    years = _history_years(target_year, len(factions) + len(settlements) + 4)

    if not factions and not settlements:
        world.historical_events = []
        world.history_end_year = target_year
        return world

    for index, year in enumerate(years):
        faction = factions[index % len(factions)] if factions else None
        other_faction = factions[(index + 1) % len(factions)] if len(factions) > 1 else faction
        settlement = settlements[index % len(settlements)] if settlements else None
        region_id = (
            settlement.region_id
            if settlement is not None
            else (faction.origin_region_id if faction is not None else "region_000")
        )
        stage = index % 6
        if stage == 0:
            center_name = settlement.center_name if settlement is not None else region_id
            summary = f"The first charter of {center_name} is recorded in the frontier rolls."
            event = HistoricalEvent(
                year=year,
                event_type="founding",
                factions=[faction.id] if faction is not None else [],
                regions=[region_id],
                summary=summary,
                consequences={"settlement": center_name, "stability": round(rng.uniform(0.25, 0.55), 3)},
            )
        elif stage == 1:
            summary = f"{faction.id if faction is not None else 'frontier caravans'} push new migration trails through {region_id}."
            event = HistoricalEvent(
                year=year,
                event_type="migration",
                factions=[faction.id] if faction is not None else [],
                regions=[region_id],
                summary=summary,
                consequences={"new_frontier": region_id, "pressure": round(rng.uniform(0.2, 0.7), 3)},
            )
        elif stage == 2:
            summary = f"Merchants bind {region_id} to distant markets with guarded trade pacts."
            event = HistoricalEvent(
                year=year,
                event_type="trade_route",
                factions=[faction.id] if faction is not None else [],
                regions=[region_id],
                summary=summary,
                consequences={"trade_value": round(rng.uniform(0.35, 0.95), 3)},
            )
        elif stage == 3 and faction is not None and other_faction is not None:
            summary = f"{faction.id} and {other_faction.id} fight a bitter campaign over {region_id}."
            event = HistoricalEvent(
                year=year,
                event_type="war",
                factions=[faction.id, other_faction.id],
                regions=[region_id],
                summary=summary,
                consequences={
                    "winner": faction.id if rng.random() >= 0.45 else other_faction.id,
                    "casualties": "severe",
                },
            )
            faction.traits["influence"] = round(faction.traits.get("influence", 0.25) + 0.04, 3)
            if other_faction is not None:
                other_faction.traits["influence"] = round(max(0.1, other_faction.traits.get("influence", 0.25) - 0.03), 3)
        elif stage == 4:
            center_name = settlement.center_name if settlement is not None else region_id
            summary = f"Storms and crop blight break the old roads leading into {center_name}."
            event = HistoricalEvent(
                year=year,
                event_type="calamity",
                factions=[faction.id] if faction is not None else [],
                regions=[region_id],
                summary=summary,
                consequences={"infrastructure_loss": round(rng.uniform(0.15, 0.35), 3)},
            )
            if settlement is not None:
                settlement.population = max(120, settlement.population - rng.randint(15, 45))
        else:
            center_name = settlement.center_name if settlement is not None else region_id
            summary = f"Rebuilders turn {center_name} into the anchor for a new regional order."
            event = HistoricalEvent(
                year=year,
                event_type="rebuild",
                factions=[faction.id] if faction is not None else [],
                regions=[region_id],
                summary=summary,
                consequences={"recovery": round(rng.uniform(0.2, 0.6), 3)},
            )
            if settlement is not None:
                settlement.population += rng.randint(10, 35)
        events.append(event)

    events.sort(key=lambda event: (event.year, event.event_type, ",".join(event.factions)))
    world.historical_events = events
    world.history_end_year = target_year
    return world


__all__ = ["simulate_history"]

"""Compatibility facade for the deterministic world simulation pipeline."""

from .world_macro import generate_world
from .world_regions import (
    generate_settlement_layout,
    load_world_snapshot,
    realize_region,
    snapshot_world,
    validate_region_snapshot,
)
from .world_history import simulate_history
from .world_society import adapt_species, seed_civilizations, seed_species
from .world_tick import initialize_simulation as initialize_simulation_v2
from .world_tick import tick_global as tick_global_v2


def initialize_simulation(world, start_region_id: str | None = None):
    return initialize_simulation_v2(world, start_region_id)


def tick_global(world, hours: int):
    return tick_global_v2(world, hours)


__all__ = [
    "adapt_species",
    "generate_settlement_layout",
    "generate_world",
    "initialize_simulation",
    "load_world_snapshot",
    "realize_region",
    "seed_civilizations",
    "seed_species",
    "simulate_history",
    "snapshot_world",
    "tick_global",
    "validate_region_snapshot",
]

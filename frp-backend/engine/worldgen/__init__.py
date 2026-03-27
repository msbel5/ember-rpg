"""Public API for the world simulation kernel."""

from .models import GlobalTickResult, RegionSnapshot, WorldBlueprint, WorldProfile
from .pipeline import (
    adapt_species,
    generate_settlement_layout,
    generate_world,
    initialize_simulation,
    load_world_snapshot,
    realize_region,
    seed_civilizations,
    seed_species,
    simulate_history,
    snapshot_world,
    tick_global,
    validate_region_snapshot,
)
from .registries import (
    load_adapter_pack,
    load_building_templates,
    load_culture_templates,
    load_furniture_templates,
    load_species_templates,
    load_world_biomes,
    load_world_profiles,
    validate_world_registries,
)

__all__ = [
    "GlobalTickResult",
    "RegionSnapshot",
    "WorldBlueprint",
    "WorldProfile",
    "adapt_species",
    "generate_settlement_layout",
    "generate_world",
    "initialize_simulation",
    "load_adapter_pack",
    "load_building_templates",
    "load_culture_templates",
    "load_furniture_templates",
    "load_species_templates",
    "load_world_biomes",
    "load_world_profiles",
    "load_world_snapshot",
    "realize_region",
    "seed_civilizations",
    "seed_species",
    "simulate_history",
    "snapshot_world",
    "tick_global",
    "validate_region_snapshot",
    "validate_world_registries",
]

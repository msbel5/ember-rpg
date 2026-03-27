"""Targeted tests for always-global runtime ticking."""

from engine.worldgen import (
    generate_world,
    initialize_simulation,
    seed_civilizations,
    seed_species,
    simulate_history,
    tick_global,
)


def _runtime_world():
    world = simulate_history(seed_civilizations(seed_species(generate_world(42, "standard"))))
    return initialize_simulation(world, world.settlements[0].region_id)


def test_tick_global_updates_active_and_inactive_regions():
    world = _runtime_world()
    active_region = world.simulation_snapshot.active_region_id
    result = tick_global(world, 24)
    assert active_region in result.updated_regions
    assert len(result.updated_regions) >= 2
    assert result.new_snapshot.current_hour >= 24
    assert result.generated_events

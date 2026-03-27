"""Targeted tests for world snapshot round-trips."""

from engine.worldgen import (
    generate_world,
    initialize_simulation,
    load_world_snapshot,
    seed_civilizations,
    seed_species,
    simulate_history,
    snapshot_world,
)


def test_world_snapshot_round_trip_preserves_identity_and_runtime_focus():
    world = initialize_simulation(
        simulate_history(seed_civilizations(seed_species(generate_world(42, "standard"))))
    )
    payload = snapshot_world(world)
    restored = load_world_snapshot(payload)
    assert restored.seed == world.seed
    assert restored.profile_id == world.profile_id
    assert restored.simulation_snapshot.active_region_id == world.simulation_snapshot.active_region_id
    assert [faction.id for faction in restored.factions] == [faction.id for faction in world.factions]

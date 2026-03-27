"""Targeted tests for region realization snapshots."""

from engine.worldgen import (
    generate_world,
    realize_region,
    seed_civilizations,
    seed_species,
    simulate_history,
)


def _world_and_region():
    world = simulate_history(seed_civilizations(seed_species(generate_world(42, "standard"))))
    return world, world.settlements[0].region_id


def test_realize_region_returns_80x60_snapshot_with_center_feature():
    world, region_id = _world_and_region()
    snapshot = realize_region(world, region_id, "settlement")
    assert snapshot.width == 80
    assert snapshot.height == 60
    assert snapshot.layout.center_feature["kind"] in {"well", "fountain"}
    assert snapshot.typed_tiles


def test_realized_snapshot_is_deterministic():
    world, region_id = _world_and_region()
    first = realize_region(world, region_id, "settlement").to_dict()
    second = realize_region(world, region_id, "settlement").to_dict()
    assert first == second

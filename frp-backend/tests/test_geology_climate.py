"""Targeted tests for macro geology and climate generation."""

from engine.worldgen import generate_world


def test_generate_world_is_deterministic_for_seed_and_profile():
    world_a = generate_world(42, "standard")
    world_b = generate_world(42, "standard")
    assert world_a.to_dict() == world_b.to_dict()


def test_generated_world_has_tectonics_elevation_and_explainable_regions():
    world = generate_world(42, "standard")
    elevations = [value for row in world.elevation for value in row]
    assert world.tectonic_plates
    assert max(elevations) > min(elevations)
    assert world.river_paths
    assert all(region["explainability"]["terrain_driver"] for region in world.regions)
    assert all(region["explainability"]["climate_driver"] for region in world.regions)


def test_temperature_varies_by_latitude():
    world = generate_world(42, "standard")
    top_avg = sum(world.temperature[0]) / len(world.temperature[0])
    mid_row = world.temperature[len(world.temperature) // 2]
    mid_avg = sum(mid_row) / len(mid_row)
    assert mid_avg > top_avg


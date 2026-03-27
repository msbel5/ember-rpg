"""Targeted tests for local settlement layout guarantees."""

from engine.worldgen import (
    generate_world,
    generate_settlement_layout,
    seed_civilizations,
    seed_species,
    simulate_history,
    validate_region_snapshot,
    realize_region,
)


def _settlement_inputs():
    world = simulate_history(seed_civilizations(seed_species(generate_world(42, "standard"))))
    return world, world.settlements[0].region_id


def test_buildings_have_road_connected_doors_and_required_furniture():
    world, region_id = _settlement_inputs()
    layout = generate_settlement_layout(world, region_id)
    road_tiles = set(layout.road_tiles)
    for building in layout.buildings:
        assert building["doors"]
        assert any(any(neighbor in road_tiles for neighbor in door["adjacent"]) for door in building["doors"])
        required = set(building["required_furniture"])
        placed = {item["kind"] for item in layout.furniture if item["building_id"] == building["id"]}
        assert required <= placed


def test_snapshot_validator_accepts_generated_settlement():
    world, region_id = _settlement_inputs()
    snapshot = realize_region(world, region_id, "settlement")
    assert validate_region_snapshot(snapshot) == []

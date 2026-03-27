"""Targeted tests for civilization seeding."""

from engine.worldgen import generate_world, seed_civilizations, seed_species


def _seeded_world(seed: int = 42):
    return seed_civilizations(seed_species(generate_world(seed, "standard")))


def test_civilization_seed_creates_factions_with_valid_regions():
    world = _seeded_world()
    region_ids = {region["id"] for region in world.regions}
    assert world.factions
    assert world.settlements
    assert all(faction.origin_region_id in region_ids for faction in world.factions)
    assert all(settlement.region_id in region_ids for settlement in world.settlements)


def test_faction_ids_change_with_world_seed():
    world_a = _seeded_world(42)
    world_b = _seeded_world(99)
    ids_a = {faction.id for faction in world_a.factions}
    ids_b = {faction.id for faction in world_b.factions}
    assert ids_a != ids_b

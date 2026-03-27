"""Targeted tests for biome and ecology distribution."""

from engine.worldgen import generate_world, seed_species
from engine.worldgen.registries import load_world_biomes


def test_generated_world_uses_registered_biomes():
    world = generate_world(42, "standard")
    registry_ids = set(load_world_biomes().keys())
    generated_ids = {biome for row in world.biomes for biome in row}
    assert generated_ids <= registry_ids
    assert len(generated_ids) >= 2


def test_seed_species_creates_domestication_pools_and_wildlife_regions():
    world = seed_species(generate_world(42, "standard"))
    assert world.species_lineages
    assert "mount" in world.domestication_pools
    assert "livestock" in world.domestication_pools
    assert any(lineage.home_regions for lineage in world.species_lineages)


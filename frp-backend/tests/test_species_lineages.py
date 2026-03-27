"""Targeted tests for species lineages and content adapters."""

from engine.worldgen import adapt_species, generate_world, seed_species


def test_seed_species_produces_sapient_and_non_sapient_lineages():
    world = seed_species(generate_world(42, "standard"))
    assert any(lineage.sapient for lineage in world.species_lineages)
    assert any(not lineage.sapient for lineage in world.species_lineages)


def test_fantasy_adapter_maps_core_species_labels_without_mutating_ids():
    world = seed_species(generate_world(42, "standard"))
    adapted = adapt_species(world, "fantasy_ember")
    labels = {lineage.adapter_payload["display_name"] for lineage in adapted.species_lineages}
    ids = {lineage.species_id for lineage in adapted.species_lineages}
    assert {"Human", "Dwarf", "Elf", "Dragon"} <= labels
    assert {"human", "dwarf", "elf", "dragon"} <= ids

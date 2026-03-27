"""Targeted tests for the sci-fi frontier adapter pack."""

from engine.worldgen import adapt_species, generate_world, seed_species
from engine.worldgen.registries import load_adapter_pack, validate_world_registries


def test_scifi_frontier_adapter_registry_is_valid():
    validate_world_registries()
    adapter = load_adapter_pack("scifi_frontier")
    assert adapter["id"] == "scifi_frontier"
    assert {"human", "synthetic", "auran", "mycoid"} <= set(adapter["allowed_species"])


def test_scifi_frontier_adapter_maps_live_species_labels():
    world = seed_species(generate_world(42, "standard"))
    adapted = adapt_species(world, "scifi_frontier")
    labels = {lineage.adapter_payload["display_name"] for lineage in adapted.species_lineages}
    assert {"Settler", "Synth", "Auran", "Mycoid"} <= labels

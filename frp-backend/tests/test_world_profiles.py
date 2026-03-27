"""Targeted tests for world simulation registries and profiles."""

from engine.worldgen import (
    load_adapter_pack,
    load_world_biomes,
    load_world_profiles,
    validate_world_registries,
)


def test_standard_profile_exists_and_has_positive_dimensions():
    profiles = load_world_profiles()
    assert "standard" in profiles
    assert profiles["standard"]["world_width"] > 0
    assert profiles["standard"]["world_height"] > 0


def test_world_registries_validate_and_load_core_packs():
    validate_world_registries()
    biomes = load_world_biomes()
    adapter = load_adapter_pack("fantasy_ember")
    assert {"plains", "temperate_forest", "mountain"} <= set(biomes.keys())
    assert {"human", "dwarf", "elf", "dragon"} <= set(adapter["species_labels"].keys())


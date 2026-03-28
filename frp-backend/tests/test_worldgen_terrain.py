from engine.worldgen import load_world_biomes, load_world_profiles
from engine.worldgen.models import WorldProfile
from engine.worldgen.terrain_generator import generate_world_blueprint


def test_generate_world_blueprint_is_deterministic_and_region_rich():
    profile = WorldProfile.from_dict(load_world_profiles()["standard"])
    biomes = load_world_biomes()

    first = generate_world_blueprint(42, profile, biomes)
    second = generate_world_blueprint(42, profile, biomes)

    assert first.to_dict() == second.to_dict()
    assert first.width == profile.world_width
    assert first.height == profile.world_height
    assert len(first.regions) >= 4
    assert {region["biome_id"] for region in first.regions} <= set(biomes)
    assert any(region["river_present"] for region in first.regions)
    assert all("settlement_suitability" in region for region in first.regions)


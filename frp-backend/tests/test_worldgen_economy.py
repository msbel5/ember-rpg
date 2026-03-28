from engine.worldgen import generate_world, seed_civilizations, seed_species, simulate_history
from engine.worldgen.economy import initialize_region_economy, tick_region_economy


def _economy_fixture(seed: int = 42):
    world = simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard"))))
    settlement = world.settlements[0]
    region = next(region for region in world.regions if region["id"] == settlement.region_id)
    return region, settlement


def test_region_economy_reprices_under_consumption_and_weather():
    region, settlement = _economy_fixture()
    initial = initialize_region_economy(region, settlement)
    storm = {"kind": "storm", "rainfall": 0.12, "severe": True}

    evolved = tick_region_economy(initial, 12, storm, settlement.population)

    assert evolved is not initial
    assert evolved["resources"]["food"] < initial["resources"]["food"]
    assert evolved["prices"]["food"] >= initial["prices"]["food"]
    assert evolved["scarcity"]["food"] >= initial["scarcity"]["food"]
    assert evolved["trade_routes"]


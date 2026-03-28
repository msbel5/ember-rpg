from engine.worldgen import generate_world, initialize_simulation, seed_civilizations, seed_species, simulate_history


def _quest_world(seed: int = 42):
    world = simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard"))))
    return initialize_simulation(world, world.settlements[0].region_id)


def test_region_initialization_exposes_real_quest_offers():
    world = _quest_world()
    region_id = world.simulation_snapshot.active_region_id
    offers = world.simulation_snapshot.region_states[region_id]["quest_offers"]

    assert len(offers) >= 5
    assert {offer["kind"] for offer in offers} >= {"fetch", "kill", "deliver", "investigate", "defend"}
    assert all(offer["giver_name"] for offer in offers)
    assert all(offer["reward_gold"] > 0 for offer in offers)
    assert all(offer["reward_xp"] > 0 for offer in offers)


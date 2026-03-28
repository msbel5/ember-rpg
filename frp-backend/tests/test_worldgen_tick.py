from engine.worldgen import generate_world, initialize_simulation, seed_civilizations, seed_species, simulate_history, tick_global


def _runtime_world(seed: int = 42):
    world = simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard"))))
    return initialize_simulation(world, world.settlements[0].region_id)


def test_world_tick_advances_runtime_state_and_emits_events():
    world = _runtime_world()
    region_id = world.simulation_snapshot.active_region_id
    before = world.simulation_snapshot.region_states[region_id]

    result = tick_global(world, 14)
    after = result.new_snapshot.region_states[region_id]

    assert result.new_snapshot.current_hour == 14
    assert result.new_snapshot.current_day == 1
    assert any(event["event_type"] == "active_region_update" for event in result.generated_events)
    assert after["weather"]
    assert after["economy"]["prices"]
    assert after["quest_offers"]
    assert any(
        (left["x"], left["y"], left["activity"]) != (right["x"], right["y"], right["activity"])
        for left, right in zip(before["npcs"], after["npcs"])
    )


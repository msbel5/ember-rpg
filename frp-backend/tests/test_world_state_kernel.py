from engine.kernel import WorldState, world_state_from_blueprint
from engine.worldgen import (
    generate_world,
    initialize_simulation,
    seed_civilizations,
    seed_species,
    simulate_history,
)


def _macro_world(seed: int = 42):
    return initialize_simulation(simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard")))))


def test_world_state_adapter_promotes_blueprint_to_typed_records():
    world = _macro_world(42)
    state = world_state_from_blueprint(world)

    assert len(state.regions) == len(world.regions)
    assert len(state.settlements) == len(world.settlement_nodes)
    assert len(state.sites) == len(world.settlement_nodes)
    assert len(state.travel_edges) == len(world.travel_edges)
    assert state.active_region_id == world.simulation_snapshot.active_region_id


def test_world_state_round_trip_preserves_regions_edges_and_settlements():
    state = world_state_from_blueprint(_macro_world(42))
    restored = WorldState.from_dict(state.to_dict())

    assert restored.active_region_id == state.active_region_id
    assert sorted(restored.regions) == sorted(state.regions)
    assert [edge.to_dict() for edge in restored.travel_edges] == [edge.to_dict() for edge in state.travel_edges]
    assert sorted(restored.settlements) == sorted(state.settlements)


def test_world_state_adapter_is_deterministic_for_same_seed():
    state_a = world_state_from_blueprint(_macro_world(42))
    state_b = world_state_from_blueprint(_macro_world(42))

    assert state_a.to_dict() == state_b.to_dict()

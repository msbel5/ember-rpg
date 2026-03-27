"""Targeted tests for simulated history."""

from engine.worldgen import generate_world, seed_civilizations, seed_species, simulate_history


def _historical_world(seed: int = 42):
    return simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard"))))


def test_history_generation_is_deterministic():
    world_a = _historical_world(42)
    world_b = _historical_world(42)
    assert [event.to_dict() for event in world_a.historical_events] == [
        event.to_dict() for event in world_b.historical_events
    ]


def test_history_contains_trade_or_migration_and_conflict_or_disaster():
    world = _historical_world()
    event_types = {event.event_type for event in world.historical_events}
    assert event_types & {"migration", "trade_route"}
    assert event_types & {"war", "disaster"}

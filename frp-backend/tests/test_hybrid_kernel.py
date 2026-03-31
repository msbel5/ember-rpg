from engine.kernel import (
    MilitaryState,
    PathAuthorityState,
    local_map_state_from_region,
    military_state_from_settlement,
    path_authority_from_world,
)
from engine.worldgen import (
    generate_world,
    initialize_simulation,
    realize_region,
    seed_civilizations,
    seed_species,
    simulate_history,
)


def _world(seed: int = 42):
    return initialize_simulation(simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard")))))


def test_path_authority_and_local_map_state_follow_active_region():
    world = _world(42)
    region_id = world.simulation_snapshot.active_region_id
    region_snapshot = realize_region(world, region_id)

    authority = path_authority_from_world(world, region_snapshot)
    local_map = local_map_state_from_region(region_snapshot)

    assert isinstance(authority, PathAuthorityState)
    assert authority.active_region_id == region_id
    assert local_map.region_id == region_id
    assert local_map.width == region_snapshot.width


def test_military_state_reflects_defense_posture_and_members():
    settlement_state = {
        "defense_posture": "fortified",
        "residents": [
            {"id": "player_commander", "name": "Commander", "role": "commander", "assignment": "command", "drafted": False},
            {"id": "guard_1", "name": "Guard", "role": "guard", "assignment": "patrol", "drafted": True},
        ],
    }

    military = military_state_from_settlement(settlement_state)

    assert isinstance(military, MilitaryState)
    assert military.defense_posture == "fortified"
    assert military.squads[0].members
    assert "guard_gate" in military.squads[0].orders

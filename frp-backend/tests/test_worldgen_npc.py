from engine.worldgen import generate_settlement_layout, generate_world, seed_civilizations, seed_species, simulate_history
from engine.worldgen.npc_generator import runtime_npc_state


def _npc_world(seed: int = 42):
    return simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard"))))


def test_generated_npcs_have_roles_homes_schedules_and_runtime_motion():
    world = _npc_world()
    layout = generate_settlement_layout(world, world.settlements[0].region_id)

    assert len(layout.npc_spawns) >= 10
    assert len({npc["role"] for npc in layout.npc_spawns}) >= 5
    assert all(npc["home_building_id"] for npc in layout.npc_spawns)
    assert all(npc["work_building_id"] for npc in layout.npc_spawns)
    assert all(len(npc["schedule"]) >= 5 for npc in layout.npc_spawns)

    morning = runtime_npc_state(layout.npc_spawns, 8)
    night = runtime_npc_state(layout.npc_spawns, 21)
    assert any(
        (left["x"], left["y"], left["activity"]) != (right["x"], right["y"], right["activity"])
        for left, right in zip(morning, night)
    )


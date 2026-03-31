from engine.api.campaign_runtime import CampaignRuntime
from engine.worldgen import generate_world, load_world_snapshot, seed_civilizations, seed_species, simulate_history, snapshot_world


def _macro_world(seed: int = 42):
    return simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard"))))


def test_standard_profile_now_realizes_48_regions_with_spread_settlements():
    world = _macro_world(42)

    unique_settlement_regions = {node["region_id"] for node in world.settlement_nodes}

    assert len(world.regions) == 48
    assert 12 <= len(world.settlement_nodes) <= 20
    assert 6 <= len(world.factions) <= 10
    assert len(unique_settlement_regions) == len(world.settlement_nodes)
    assert len(unique_settlement_regions) >= 12


def test_world_graph_is_deterministic_and_connected():
    world_a = _macro_world(42)
    world_b = _macro_world(42)

    assert world_a.settlement_nodes == world_b.settlement_nodes
    assert world_a.travel_edges == world_b.travel_edges
    assert len(world_a.travel_edges) >= len(world_a.settlement_nodes) - 1


def test_campaign_travel_uses_region_ids_and_swaps_active_region():
    runtime = CampaignRuntime(llm=lambda _prompt: "stub")
    context = runtime.create_campaign("GraphTester", adapter_id="fantasy_ember", seed=42)
    snapshot = runtime.snapshot(context.campaign_id)
    travel_options = snapshot["campaign"]["travel_options"]

    assert travel_options

    chosen = travel_options[0]
    previous_region_id = snapshot["campaign"]["world"]["active_region_id"]
    traveled = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="travel",
        args={
            "destination_region_id": chosen["destination_region_id"],
            "destination_settlement_id": chosen["destination_settlement_id"],
        },
    )

    assert traveled["command_type"] == "travel"
    assert traveled["campaign"]["world"]["active_region_id"] == chosen["destination_region_id"]
    assert traveled["campaign"]["region"]["region_id"] == chosen["destination_region_id"]
    assert traveled["campaign"]["world"]["active_region_id"] != previous_region_id


def test_world_snapshot_round_trip_preserves_world_graph():
    world = _macro_world(42)
    payload = snapshot_world(world)
    restored = load_world_snapshot(payload)

    assert restored.settlement_nodes == world.settlement_nodes
    assert restored.travel_edges == world.travel_edges

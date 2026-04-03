from __future__ import annotations

from engine.kernel import (
    ActorIdentity,
    ActorPosition,
    ActorRecord,
    ColonyPressureState,
    FactionRecord,
    RegionRecord,
    SettlementRecord,
    SiteRecord,
    TravelEdge,
    TravelState,
    WorldState,
    advance_local_action,
    apply_squad_orders,
    complete_travel,
    hydrate_local_map,
    initiate_travel,
    macro_state_from_world,
    military_state_from_settlement,
    tick_travel,
)


def _world() -> WorldState:
    edge = TravelEdge(
        edge_id="edge_a_b",
        source_region_id="region_a",
        destination_region_id="region_b",
        source_settlement_id="settlement_a",
        destination_settlement_id="settlement_b",
        travel_hours=3,
    )
    edge.danger_level = 2
    return WorldState(
        seed=77,
        profile_id="hybrid_test",
        width=2,
        height=1,
        active_region_id="region_a",
        regions={
            "region_a": RegionRecord(
                region_id="region_a",
                biome_id="forest",
                x=0,
                y=0,
                width=80,
                height=60,
                controller_faction_id="faction_a",
                settlement_ids=["settlement_a"],
                site_ids=["site_a"],
                faction_ids=["faction_a"],
                economy={"food": 4},
                alerts=[],
                metadata={"terrain_tags": ["forest", "road"]},
            ),
            "region_b": RegionRecord(
                region_id="region_b",
                biome_id="hills",
                x=1,
                y=0,
                width=64,
                height=48,
                controller_faction_id="faction_a",
                settlement_ids=["settlement_b"],
                site_ids=["site_b"],
                faction_ids=["faction_a"],
                economy={"food": 2},
                alerts=["bandits"],
                metadata={"terrain_tags": ["hill", "watchtower"], "spawn_point": [5, 9]},
            ),
        },
        settlements={
            "settlement_a": SettlementRecord(
                settlement_id="settlement_a",
                region_id="region_a",
                faction_id="faction_a",
                name="A",
                settlement_type="outpost",
                population=12,
            ),
            "settlement_b": SettlementRecord(
                settlement_id="settlement_b",
                region_id="region_b",
                faction_id="faction_a",
                name="B",
                settlement_type="fort",
                population=18,
            ),
        },
        sites={
            "site_a": SiteRecord(
                site_id="site_a",
                region_id="region_a",
                settlement_id="settlement_a",
                site_type="outpost",
                name="A Site",
                owner_faction_id="faction_a",
                population=12,
            ),
            "site_b": SiteRecord(
                site_id="site_b",
                region_id="region_b",
                settlement_id="settlement_b",
                site_type="fort",
                name="B Site",
                owner_faction_id="faction_a",
                population=18,
                tags=["primary_site"],
            ),
        },
        factions={
            "faction_a": FactionRecord(
                faction_id="faction_a",
                culture_id="culture_a",
                species_id="human",
                origin_region_id="region_a",
                traits={"order": 0.7},
            )
        },
        travel_edges=[edge],
    )


def _actor() -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(
            actor_id="commander",
            display_name="Commander",
            actor_type="player",
            faction_id="faction_a",
            site_id="site_a",
            species_id="human",
        ),
        position=ActorPosition(x=10, y=7, region_id="region_a", site_id="site_a"),
        action_points=5,
        max_action_points=5,
        alive=True,
        stats={"MIG": 12},
    )


def test_ac01_macro_state_query_returns_typed_records_and_options():
    world = _world()

    macro_state = macro_state_from_world(world, "region_a")

    assert macro_state.region.region_id == "region_a"
    assert macro_state.factions[0].faction_id == "faction_a"
    assert macro_state.travel_options[0].edge_id == "edge_a_b"


def test_ac02_initiate_travel_enters_preparing_with_edge_hours():
    world = _world()

    travel = initiate_travel(world, "region_a", "region_b", seed=11)

    assert isinstance(travel, TravelState)
    assert travel.status == "preparing"
    assert travel.origin_region_id == "region_a"
    assert travel.destination_region_id == "region_b"
    assert travel.travel_hours_total == 3
    assert travel.travel_hours_remaining == 3


def test_ac03_tick_travel_decrements_remaining_and_reaches_arrived():
    world = _world()
    travel = initiate_travel(world, "region_a", "region_b", seed=11)

    travel = tick_travel(travel, seed=11)
    assert travel.status == "traveling"
    assert travel.travel_hours_remaining == 3

    travel = tick_travel(travel, seed=11)
    assert travel.travel_hours_remaining == 2

    travel = tick_travel(travel, seed=11)
    assert travel.travel_hours_remaining == 1

    travel = tick_travel(travel, seed=11)
    assert travel.status == "arriving"
    assert travel.travel_hours_remaining == 0

    travel = tick_travel(travel, seed=11)
    assert travel.status == "arrived"


def test_ac04_tick_travel_uses_danger_probability_and_can_trigger_encounter():
    world = _world()
    travel = initiate_travel(world, "region_a", "region_b", seed=1)

    travel = tick_travel(travel, seed=1)
    travel = tick_travel(travel, seed=1)

    assert travel.encounter_checked is True
    assert travel.encounter_triggered is True
    assert 0.0 <= travel.encounter_roll <= 1.0


def test_ac05_complete_travel_updates_world_and_path_authority():
    world = _world()
    travel = TravelState(
        status="arrived",
        origin_region_id="region_a",
        destination_region_id="region_b",
        travel_hours_remaining=0,
        travel_hours_total=3,
    )

    authority = complete_travel(travel, world)

    assert world.active_region_id == "region_b"
    assert authority.active_region_id == "region_b"
    assert authority.active_site_id == "site_b"
    assert authority.local_map_loaded is True


def test_ac06_local_action_consumes_ap_and_advances_tick():
    actor = _actor()
    pressure = ColonyPressureState(food=80, safety=70, morale=75, supply=70, housing=80, unrest=20)

    result = advance_local_action(actor, pressure, action_id="move", ap_cost=2, hours=1)

    assert actor.action_points == 3
    assert result.hours_advanced == 1
    assert result.action_id == "move"


def test_ac07_local_action_updates_colony_pressure_on_same_tick():
    actor = _actor()
    pressure = ColonyPressureState(food=45, safety=48, morale=52, supply=70, housing=80, unrest=40)

    result = advance_local_action(actor, pressure, action_id="craft", ap_cost=1, hours=1)

    assert result.colony_pressure.food < 45
    assert result.colony_pressure.morale < 52
    assert result.colony_pressure.safety < 48


def test_ac08_military_state_from_fortified_settlement_sets_alert_level_and_orders():
    settlement_state = {
        "defense_posture": "fortified",
        "residents": [
            {"id": "leader", "name": "Leader", "role": "commander", "assignment": "command", "drafted": False},
            {"id": "guard_1", "name": "Guard One", "role": "guard", "assignment": "patrol", "drafted": True},
        ],
    }

    military = military_state_from_settlement(settlement_state)

    assert military.defense_posture == "fortified"
    assert military.alert_level == 3
    assert "guard_gate" in military.squads[0].orders
    assert "patrol_market" in military.squads[0].orders


def test_ac09_apply_squad_orders_reduces_safety_pressure_and_unrest():
    settlement_state = {
        "defense_posture": "fortified",
        "residents": [
            {"id": "leader", "name": "Leader", "role": "commander", "assignment": "command", "drafted": False},
            {"id": "guard_1", "name": "Guard One", "role": "guard", "assignment": "patrol", "drafted": True},
            {"id": "guard_2", "name": "Guard Two", "role": "guard", "assignment": "guard_gate", "drafted": True},
        ],
    }
    military = military_state_from_settlement(settlement_state)
    pressure = ColonyPressureState(food=70, safety=40, morale=65, supply=70, housing=70, unrest=30)

    updated = apply_squad_orders(military, pressure)

    assert updated.safety == 50
    assert updated.unrest < 30


def test_ac10_core_loop_runs_without_ai_adapters():
    world = _world()
    actor = _actor()
    pressure = ColonyPressureState(food=70, safety=60, morale=60, supply=70, housing=70, unrest=20)
    military = military_state_from_settlement({"defense_posture": "normal", "residents": []})

    travel = initiate_travel(world, "region_a", "region_b", seed=99)
    travel = tick_travel(travel, seed=99)
    pressure = apply_squad_orders(military, pressure)
    result = advance_local_action(actor, pressure, action_id="inspect", ap_cost=1, hours=1)
    local_map = hydrate_local_map(world, "region_a")

    assert travel.status == "traveling"
    assert result.colony_pressure.safety >= pressure.safety
    assert local_map.region_id == "region_a"

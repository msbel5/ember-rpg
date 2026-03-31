from engine.kernel import (
    ActorIdentity,
    ActorPosition,
    ActorRecord,
    BodyPlanDef,
    BodyState,
    ColonyPressureState,
    ConditionRecord,
    FluidState,
    PowerNetworkState,
    StrangeMoodIncident,
    TemperatureState,
    fluid_state_from_region,
    power_network_from_settlement,
    strange_mood_incident_from_settlement,
    syndrome_registry_from_actors,
    temperature_state_from_region,
    trap_state_from_settlement,
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
    return initialize_simulation(
        simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard"))))
    )


def _actor_with_conditions() -> ActorRecord:
    body_state = BodyState(
        plan=BodyPlanDef(plan_id="test_plan", label="Test Plan", parts=[]),
        conditions=[
            ConditionRecord(
                condition_id="body_poison",
                name="poisoned",
                severity=2,
                tags=["torso"],
            )
        ],
    )
    return ActorRecord(
        identity=ActorIdentity(
            actor_id="actor_1",
            display_name="Actor One",
            actor_type="npc",
            faction_id="settlement_watch",
        ),
        position=ActorPosition(x=10, y=12, region_id="region_1", site_id="site_1"),
        action_points=2,
        max_action_points=2,
        alive=True,
        body_state=body_state,
        conditions=[
            ConditionRecord(
                condition_id="battle_fever",
                name="battle_fever",
                severity=3,
                tags=["mind"],
            )
        ],
    )


def _fortified_settlement() -> dict:
    return {
        "defense_posture": "fortified",
        "rooms": [
            {"id": "room_1", "kind": "mill", "workstations": ["windmill"]},
            {"id": "room_2", "kind": "forge", "workstations": ["forge"]},
        ],
        "jobs": [{"id": "job_1", "kind": "forge"}],
        "residents": [
            {"id": "commander", "role": "commander"},
            {"id": "artisan", "role": "smith"},
        ],
        "alerts": ["Raid risk"],
        "needs": {"food": 4, "security": 3, "materials": 2},
        "faction_pressure": [{"event_type": "war"}],
    }


def test_syndrome_registry_collects_actor_and_body_conditions():
    registry = syndrome_registry_from_actors([_actor_with_conditions()])

    names = {entry.name for entry in registry}
    assert "battle_fever" in names
    assert "poisoned" in names


def test_system_states_derive_from_settlement_and_region():
    world = _world(42)
    region_snapshot = realize_region(world, world.simulation_snapshot.active_region_id)
    settlement_state = _fortified_settlement()
    colony_pressure = ColonyPressureState(
        food=40,
        safety=35,
        morale=60,
        supply=55,
        housing=70,
        unrest=58,
        shortages=["food"],
    )

    power_network = power_network_from_settlement(settlement_state)
    traps = trap_state_from_settlement(settlement_state)
    fluid_state = fluid_state_from_region(region_snapshot)
    temperature_state = temperature_state_from_region(region_snapshot)
    incident = strange_mood_incident_from_settlement(settlement_state, colony_pressure)

    assert isinstance(power_network, PowerNetworkState)
    assert power_network.nodes
    assert traps
    assert isinstance(fluid_state, FluidState)
    assert set(fluid_state.fluid_counts) == {"water", "magma"}
    assert isinstance(temperature_state, TemperatureState)
    assert temperature_state.ambient_band in {"cold", "temperate", "hot"}
    assert isinstance(incident, StrangeMoodIncident)
    assert incident.candidate_actor_ids

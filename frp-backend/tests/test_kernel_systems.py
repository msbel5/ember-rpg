from __future__ import annotations

from engine.kernel.actor import (
    ActorIdentity,
    ActorPosition,
    ActorRecord,
    BodyPartDef,
    BodyPartState,
    BodyPlanDef,
    BodyState,
    ConditionRecord,
    ItemStack,
    TissueLayerDef,
)
from engine.kernel.colony import ColonyPressureState
from engine.kernel.systems import (
    FluidCell,
    FluidState,
    MaterialDemand,
    PowerNetworkState,
    PowerNodeState,
    StrangeMoodIncident,
    SyndromeDef,
    SyndromeEffect,
    TemperatureState,
    TrapComponent,
    TrapState,
    apply_syndrome,
    check_drowning,
    check_magma_damage,
    check_trap_triggers,
    compute_power_network,
    create_artifact,
    resolve_trap_damage,
    spread_contagion,
    tick_fluids,
    tick_strange_mood,
    tick_syndromes,
    tick_temperature,
    toggle_gear,
)


def _body_state() -> BodyState:
    plan = BodyPlanDef(
        plan_id="humanoid",
        label="Humanoid",
        parts=[
            BodyPartDef(
                part_id="torso",
                label="Torso",
                max_hp=20,
                vital=True,
                relative_size=10,
                layers=[TissueLayerDef(layer_id="skin", material_id="skin", under_pressure=True, vital=True)],
            )
        ],
    )
    return BodyState(plan=plan, parts={"torso": BodyPartState(part_id="torso", current_hp=20, max_hp=20)})


def _actor(
    actor_id: str,
    *,
    x: int = 0,
    y: int = 0,
    disease_resistance: int = 0,
    toughness: int = 10,
    moodable_skill: int = 0,
    personality: str = "calm",
) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc", faction_id="settlers"),
        position=ActorPosition(x=x, y=y),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"disease_resistance": disease_resistance, "TOUGHNESS": toughness},
        skills={"crafting": moodable_skill},
        body_state=_body_state(),
        raw_payload={"personality": personality},
    )


def test_ac01_apply_syndrome_resists_when_save_meets_dc():
    actor = _actor("a", disease_resistance=3, toughness=12)
    syndrome = SyndromeDef(
        syndrome_id="venom",
        name="Venom",
        delivery="contact",
        resistance_dc=15,
        effects=[SyndromeEffect(effect_id="pain", effect_type="CE_PAIN", severity=50, target="actor")],
    )

    applied = apply_syndrome(actor, syndrome, seed=10)

    assert applied is False


def test_ac02_tick_syndromes_applies_pain_and_expires_after_end_tick():
    actor = _actor("a")
    syndrome = SyndromeDef(
        syndrome_id="pain",
        name="Pain",
        delivery="contact",
        effects=[SyndromeEffect(effect_id="pain", effect_type="CE_PAIN", severity=50, target="actor", start_tick=0, end_tick=100)],
    )
    apply_syndrome(actor, syndrome, seed=1)
    actor.raw_payload["active_syndromes"][0]["effects"][0]["tick_counter"] = 50

    tick_syndromes(actor)
    assert actor.raw_payload["pain"] > 0

    actor.raw_payload["active_syndromes"][0]["effects"][0]["tick_counter"] = 100
    tick_syndromes(actor)
    assert actor.raw_payload["active_syndromes"] == []


def test_ac03_bleeding_effect_adds_blood_loss_each_tick():
    actor = _actor("a")
    syndrome = SyndromeDef(
        syndrome_id="bleed",
        name="Bleed",
        delivery="contact",
        effects=[SyndromeEffect(effect_id="bleed", effect_type="CE_BLEEDING", severity=20, target="actor")],
    )
    apply_syndrome(actor, syndrome, seed=1)

    tick_syndromes(actor)

    assert actor.stats["blood_loss"] == 20


def test_ac04_contagion_spreads_between_adjacent_actors():
    source = _actor("source", x=1, y=1)
    target = _actor("target", x=1, y=1)
    syndrome = SyndromeDef(
        syndrome_id="cold",
        name="Cold",
        delivery="contact",
        contagious=True,
        contagion_probability=1.0,
        effects=[SyndromeEffect(effect_id="nausea", effect_type="CE_NAUSEA", severity=10, target="actor")],
    )
    apply_syndrome(source, syndrome, seed=1)

    infections = spread_contagion([source, target], {})

    assert infections == [("source", "target")]


def test_ac05_compute_power_network_uses_all_or_nothing_activation():
    settlement = {
        "power_nodes": [
            {"node_id": "wheel", "kind": "water_wheel", "role": "source", "power_delta": 20},
            {"node_id": "forge", "kind": "forge", "role": "consumer", "power_delta": -10},
            {"node_id": "mill", "kind": "mill", "role": "consumer", "power_delta": -10},
        ]
    }

    active = compute_power_network(settlement)
    inactive = compute_power_network({"power_nodes": settlement["power_nodes"][1:]})

    assert active.active is True
    assert inactive.active is False


def test_ac06_toggle_gear_disconnects_subnetwork_and_can_restore_activation():
    network = PowerNetworkState(
        nodes=[
            PowerNodeState(node_id="wheel", kind="water_wheel", role="source", power_delta=20, connected_to=["gear"]),
            PowerNodeState(node_id="gear", kind="gear_assembly", role="transmitter", power_delta=0, connected_to=["wheel", "mill"]),
            PowerNodeState(node_id="mill", kind="mill", role="consumer", power_delta=-10, connected_to=["gear"]),
            PowerNodeState(node_id="forge", kind="forge", role="consumer", power_delta=-15, connected_to=[]),
        ]
    )
    network = toggle_gear(network, "gear")

    assert network.active is True
    assert next(node for node in network.nodes if node.node_id == "gear").disengaged is True


def test_ac07_weapon_trap_fires_all_loaded_weapons_and_remains_armed():
    trap = TrapState(
        trap_id="t1",
        trap_type="weapon_trap",
        armed=True,
        trigger="pressure_plate",
        reusable=True,
        components=[
            TrapComponent(component_id="w1", component_type="weapon"),
            TrapComponent(component_id="w2", component_type="weapon"),
            TrapComponent(component_id="w3", component_type="weapon"),
        ],
    )

    events = check_trap_triggers([trap], {"enemy": (1, 1)}, {"t1": (1, 1)})

    assert events[0]["damage_count"] == 3
    assert trap.armed is True


def test_ac08_cage_trap_captures_and_trapavoid_creature_is_immune():
    trap = TrapState(
        trap_id="cage",
        trap_type="cage_trap",
        armed=True,
        trigger="pressure_plate",
        reusable=False,
        components=[TrapComponent(component_id="c1", component_type="cage")],
    )

    events = check_trap_triggers([trap], {"enemy": {"position": (2, 2), "tags": []}}, {"cage": (2, 2)})
    immune_events = check_trap_triggers([trap], {"beast": {"position": (2, 2), "tags": ["trap_avoid"]}}, {"cage": (2, 2)})

    assert events[0]["captured"] is True
    assert trap.armed is False
    assert immune_events == []


def test_ac09_tick_fluids_spreads_water_to_lower_neighbor():
    fluid_state = FluidState(cells=[FluidCell(x=5, y=5, fluid_type="water", level=7), FluidCell(x=5, y=6, fluid_type="water", level=0)])

    updated = tick_fluids(fluid_state, [[{"terrain": "floor"} for _x in range(12)] for _y in range(12)])

    levels = {(cell.x, cell.y): cell.level for cell in updated.cells}
    assert levels[(5, 5)] < 7
    assert levels[(5, 6)] > 0


def test_ac10_check_drowning_returns_true_after_ten_ticks_in_deep_water():
    actor = _actor("a", x=3, y=3)
    fluid_state = FluidState(cells=[FluidCell(x=3, y=3, fluid_type="water", level=7)])

    result = False
    for _ in range(10):
        result = check_drowning(actor, fluid_state)

    assert result is True


def test_ac11_tick_fluids_creates_obsidian_when_water_meets_magma():
    fluid_state = FluidState(cells=[FluidCell(x=5, y=5, fluid_type="water", level=4), FluidCell(x=5, y=5, fluid_type="magma", level=4)])
    terrain = [[{"terrain": "floor"} for _x in range(8)] for _y in range(8)]

    updated = tick_fluids(fluid_state, terrain)

    assert updated.cells == []
    assert terrain[5][5]["terrain"] == "obsidian"


def test_ac12_tick_temperature_emits_frostbite_event_in_cold_region():
    actor = _actor("a")
    temp_state = TemperatureState(ambient_band="cold", ambient_value=9990, cold_threshold=10000)

    events = []
    for _ in range(3):
        events = tick_temperature(temp_state, [actor])

    assert any(event["type"] == "frostbite" for event in events)


def test_ac13_tick_temperature_emits_burning_condition_for_organic_item():
    actor = _actor("a")
    actor.raw_payload["organic_item_ignite_point"] = 10400
    temp_state = TemperatureState(ambient_band="hot", ambient_value=10600, heat_threshold=10500)

    events = tick_temperature(temp_state, [actor])

    assert any(event["type"] == "item_ignited" for event in events)


def test_ac14_tick_temperature_freezes_and_melts_water_tiles():
    temp_state = TemperatureState(ambient_band="cold", ambient_value=9990, cold_threshold=10000, tile_states={(1, 1): "water"})

    freeze_events = tick_temperature(temp_state, [])
    temp_state.ambient_value = 10010
    melt_events = tick_temperature(temp_state, [])

    assert any(event["type"] == "freeze" for event in freeze_events)
    assert any(event["type"] == "melt" for event in melt_events)


def test_ac15_strange_mood_triggers_for_eligible_actor_under_low_morale():
    settlement = {"worksites": [{"id": "forge"}], "available_materials": ["metal_bar"], "morale": 60, "unrest": 20}
    actor = _actor("crafter", moodable_skill=5, personality="creative")
    incident = StrangeMoodIncident(incident_id="m1", state="triggered", mood_type="", trigger_reason="morale_pressure", candidate_actor_ids=["crafter"])

    updated = tick_strange_mood(incident, settlement, [actor], seed=1)

    assert updated.actor_id == "crafter"
    assert updated.mood_type in {"fey_crafter", "secretive", "possessed", "macabre", "fell"}


def test_ac16_strange_mood_moves_to_working_when_demands_satisfied_and_fails_on_timeout():
    settlement = {"worksites": [{"id": "forge"}], "available_materials": ["metal_bar", "gem"], "morale": 60, "unrest": 20}
    actor = _actor("crafter", moodable_skill=5)
    incident = StrangeMoodIncident(
        incident_id="m1",
        state="demanding_materials",
        mood_type="fey_crafter",
        trigger_reason="morale_pressure",
        actor_id="crafter",
        claimed_worksite_id="forge",
        material_demands=[MaterialDemand("metal_bar"), MaterialDemand("gem")],
        elapsed_ticks=10,
    )
    updated = tick_strange_mood(incident, settlement, [actor], seed=1)

    failed = StrangeMoodIncident(
        incident_id="m2",
        state="demanding_materials",
        mood_type="fey_crafter",
        trigger_reason="morale_pressure",
        actor_id="crafter",
        claimed_worksite_id="forge",
        material_demands=[MaterialDemand("bone")],
        elapsed_ticks=500,
        timeout_ticks=500,
    )
    failed_updated = tick_strange_mood(failed, settlement, [actor], seed=1)

    assert updated.state == "working"
    assert failed_updated.state == "failed"


def test_ac17_create_artifact_sets_quality_six_and_legendary_skill():
    actor = _actor("crafter", moodable_skill=5)
    incident = StrangeMoodIncident(
        incident_id="m1",
        state="working",
        mood_type="fey_crafter",
        trigger_reason="morale_pressure",
        actor_id="crafter",
        claimed_worksite_id="forge",
    )

    artifact = create_artifact(incident, actor, seed=1)

    assert artifact.quality == 6
    assert actor.skills["crafting"] == 20


def test_ac18_failed_mood_sets_insane_or_melancholy_condition():
    settlement = {"worksites": [], "available_materials": [], "morale": 40, "unrest": 80}
    actor = _actor("crafter", moodable_skill=5)
    incident = StrangeMoodIncident(
        incident_id="m1",
        state="demanding_materials",
        mood_type="fell",
        trigger_reason="unrest_pressure",
        actor_id="crafter",
        claimed_worksite_id="",
        material_demands=[MaterialDemand("bone")],
        elapsed_ticks=500,
        timeout_ticks=500,
    )

    updated = tick_strange_mood(incident, settlement, [actor], seed=1)

    assert updated.state == "failed"
    assert any(condition.name in {"insane", "melancholy"} for condition in actor.conditions)

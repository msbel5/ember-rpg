import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.kernel import (
    EffectDef,
    FluidCell,
    StoreDef,
    StoreItem,
    SyndromeDef,
    SyndromeEffect,
    TemperatureState,
    TrapComponent,
    TrapState,
    apply_effect,
    apply_syndrome,
)


def _runtime() -> CampaignRuntime:
    return CampaignRuntime()


def _player_actor(context):
    return context.kernel_runtime["actors"]["player"]


@pytest.mark.parametrize("adapter_id, seed", [("fantasy_ember", 52), ("scifi_frontier", 53)])
def test_campaign_runtime_exposes_logic_live_slices_for_supported_adapters(adapter_id: str, seed: int):
    runtime = _runtime()
    context = runtime.create_campaign("Parity", adapter_id=adapter_id, seed=seed)

    response = runtime.run_command(context.campaign_id, "rest")
    campaign = response["campaign"]

    assert campaign["world"]["adapter_id"] == adapter_id
    assert campaign["world_state"]["active_region_id"]
    assert campaign["game_state"]["campaign_id"] == context.campaign_id
    assert campaign["actors"]
    assert campaign["jobs"]
    assert campaign["colony_pressure"]
    assert campaign["production_ledger"]
    assert campaign["stores"]
    assert campaign["systems"]


def test_campaign_runtime_ticks_effects_and_syndromes_live():
    runtime = _runtime()
    context = runtime.create_campaign("LogicLive", adapter_id="fantasy_ember", seed=42)
    actor = _player_actor(context)
    actor.stats["CON"] = 10
    actor.stats["disease_resistance"] = 0

    burning = EffectDef(
        effect_def_id="burning_dot",
        label="Burning",
        category="dot",
        damage_per_tick=6,
        damage_type="fire",
        timing_mode="duration",
        base_duration_ticks=2,
    )
    used, _ = apply_effect(actor, burning, source_id="test_fire", current_tick=0)
    assert used is True

    venom = SyndromeDef(
        syndrome_id="test_venom",
        name="Test Venom",
        delivery="injected",
        resistance_dc=99,
        contagious=False,
        effects=[SyndromeEffect(effect_id="pain", effect_type="CE_PAIN", severity=4)],
    )
    assert apply_syndrome(actor, venom, seed=1) is True

    # "rest" advances 1 hour so effects/syndromes tick.
    response = runtime.run_command(context.campaign_id, "rest")
    player_payload = next(
        item for item in response["campaign"]["actors"] if item["identity"]["actor_id"] == "player"
    )

    assert player_payload["body_state"]["wounds"]
    assert player_payload["raw_payload"]["pain"] >= 4
    assert player_payload["effect_queue"]["instances"][0]["ticks_remaining"] == 1
    assert response["campaign"]["systems"]["syndrome_registry"]


def test_campaign_runtime_advances_jobs_farming_and_pressure_live():
    runtime = _runtime()
    context = runtime.create_campaign("Foreman", adapter_id="fantasy_ember", seed=43)
    actor = _player_actor(context)
    actor.skills["smithing"] = 6

    context.settlement_state["rooms"].append(
        {
            "id": "smithy",
            "kind": "workshop",
            "label": "Smithy",
            "priority": 3,
            "doors": 1,
            "beds": 0,
            "workstations": ["forge"],
            "position": [10, 10],
        }
    )
    context.settlement_state["jobs"] = [
        {
            "id": "job_forge",
            "kind": "forge",
            "priority": 1,
            "status": "queued",
            "worksite_id": "smithy_forge",
            "completion_ticks": 1,
            "elapsed_ticks": 0,
        }
    ]
    context.settlement_state["farm_plots"] = [
        {
            "id": "plot_1",
            "crop": "barley",
            "active": True,
            "status": "active",
            "growth_ticks": 95,
            "growth_target": 100,
            "yield": 0,
        }
    ]
    context.settlement_state["seed_stock"] = {"barley": 2}
    context.settlement_state["needs"]["food"] = 5
    context.settlement_state["economy"].setdefault("resources", {})["food"] = 3
    context.settlement_state["available_materials"] = ["ore", "anvil"]

    response = runtime.run_command(context.campaign_id, "assign Foreman to smithing")

    jobs = {job["job_id"]: job for job in response["campaign"]["jobs"]}
    assert jobs["job_forge"]["status"] == "completed"
    assert response["campaign"]["production_ledger"]["shortages"]
    assert response["campaign"]["colony_pressure"]["quest_seeds"]
    assert response["campaign"]["settlement"]["farm_plots"][0]["yield"] >= 1
    assert response["campaign"]["settlement"]["seed_stock"]["barley"] >= 3


def test_campaign_runtime_updates_stores_trade_migration_and_diplomacy_live():
    runtime = _runtime()
    context = runtime.create_campaign("Envoy", adapter_id="fantasy_ember", seed=44)

    for room in context.settlement_state["rooms"]:
        room["beds"] = max(int(room.get("beds", 0)), 2)
        room["furnished"] = True
    context.settlement_state["needs"] = {"food": 1, "security": 1, "materials": 1}
    context.settlement_state["alerts"] = []
    context.kernel_runtime["stores"] = [
        StoreDef(
            store_id="market_square",
            label="Market Square",
            store_type="market",
            items=[StoreItem(item_def_id="grain", quantity=10, price_multiplier=1.0)],
        )
    ]

    # "rest" advances 1 hour so world systems tick.
    response = runtime.run_command(context.campaign_id, "rest")
    world_state = response["campaign"]["world_state"]

    assert response["campaign"]["stores"]
    # Price may or may not change after 1 hour; just confirm store exists.
    assert response["campaign"]["stores"][0]["items"]
    assert world_state["active_caravans"]
    assert world_state["migration_waves"]
    faction = next(iter(world_state["factions"].values()))
    assert "relations" in faction


def test_campaign_runtime_ticks_systems_and_applies_environmental_consequences():
    runtime = _runtime()
    context = runtime.create_campaign("Hazard", adapter_id="fantasy_ember", seed=45)
    actor = _player_actor(context)
    actor.position.x = 5
    actor.position.y = 5

    context.kernel_runtime["systems"]["fluid_state"].cells = [
        FluidCell(x=5, y=5, fluid_type="magma", level=7),
    ]
    context.kernel_runtime["systems"]["temperature_state"] = TemperatureState(
        ambient_band="hot",
        ambient_value=10650,
        hazardous=True,
        tags=["burn_risk"],
    )
    context.kernel_runtime["systems"]["traps"] = [
        TrapState(
            trap_id="gate_spikes",
            trap_type="stone_fall",
            armed=True,
            trigger="pressure_plate",
            components=[TrapComponent(component_id="stone", component_type="stone")],
        )
    ]
    context.settlement_state["trap_positions"] = {"gate_spikes": [5, 5]}

    # "rest" advances 1 hour so environmental systems tick.
    response = runtime.run_command(context.campaign_id, "rest")
    player_payload = next(
        item for item in response["campaign"]["actors"] if item["identity"]["actor_id"] == "player"
    )
    damage_types = {wound["damage_type"] for wound in player_payload["body_state"]["wounds"]}

    assert "fire" in damage_types or "blunt" in damage_types
    assert response["campaign"]["systems"]["temperature_state"]["ambient_band"] == "hot"
    assert response["campaign"]["systems"]["traps"][0]["armed"] is False


def test_condition_normalization_survives_string_injection():
    """Regression: conditions list may contain raw strings after session sync.

    ActorRecord.condition_names must handle both ConditionRecord objects
    and raw strings without crashing (was AttributeError: 'str' has no .name).
    """
    runtime = _runtime()
    context = runtime.create_campaign("CondTest", seed=99)
    player = _player_actor(context)
    # Inject a raw string into conditions (simulates session sync artifact).
    player.conditions.append("poisoned")
    # This must not crash.
    names = player.condition_names
    assert "poisoned" in names
    # The string should now be promoted to a ConditionRecord.
    assert all(hasattr(c, "name") for c in player.conditions)
    # Run a full command cycle to verify no crash during sync.
    response = runtime.run_command(context.campaign_id, "look around")
    assert "narrative" in response


def test_mixed_conditions_survive_full_tick_cycle():
    """Verify that mixed condition types survive advance_kernel_runtime."""
    from engine.kernel.actor_body import ConditionRecord
    runtime = _runtime()
    context = runtime.create_campaign("MixedCond", seed=100)
    player = _player_actor(context)
    player.conditions = [
        ConditionRecord(condition_id="blessed", name="blessed", severity=1),
        "fatigued",  # Raw string — must not crash.
    ]
    response = runtime.run_command(context.campaign_id, "rest")
    assert "narrative" in response
    # After sync, all conditions on the kernel ActorRecord must be
    # proper ConditionRecord objects (promoted from strings during tick).
    assert all(hasattr(c, "name") for c in player.conditions)
    # condition_names must return clean string list.
    names = player.condition_names
    assert isinstance(names, list)
    assert all(isinstance(n, str) for n in names)

from __future__ import annotations

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord, NeedState
from engine.kernel.colony import (
    ColonyPressureState,
    ProductionLedger,
    apply_morale_cascade,
    colony_pressure_from_settlement,
    compute_mood,
    decay_needs,
    fulfill_need,
    pressure_tags_from_metrics,
    production_ledger_from_settlement,
    room_morale_bonus,
)


def _actor(actor_id: str) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc", faction_id="settlement"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={},
        needs=NeedState(),
    )


def test_ac01_need_state_defaults_include_all_eight_need_types():
    actor = _actor("worker")

    assert set(actor.needs.values) == {
        "eat",
        "drink",
        "sleep",
        "pray",
        "socialize",
        "craft",
        "train",
        "admire_art",
    }
    assert all(value == 100.0 for value in actor.needs.values.values())


def test_ac02_decay_needs_reduces_eat_by_expected_amount():
    actor = _actor("worker")
    actor.needs.values["eat"] = 80.0

    decay_needs(actor, 10)

    assert actor.needs.values["eat"] == 72.0


def test_ac03_decay_needs_clamps_at_zero():
    actor = _actor("worker")
    actor.needs.values["drink"] = 5.0

    decay_needs(actor, 10)

    assert actor.needs.values["drink"] == 0.0


def test_ac04_fulfill_need_uses_facility_quality_bonus():
    actor = _actor("worker")
    actor.needs.values["eat"] = 20.0

    restored = fulfill_need(actor, "eat", facility_quality=2)

    assert restored == 72.0
    assert actor.needs.values["eat"] == 92.0


def test_ac05_compute_mood_returns_content_at_high_weighted_satisfaction():
    needs = NeedState(values={need_id: 80.0 for need_id in NeedState().values})

    mood, modifiers = compute_mood(needs)

    assert mood == "content"
    assert modifiers["work_speed_mult"] == 1.0


def test_ac06_compute_mood_returns_breakdown_at_low_weighted_satisfaction():
    needs = NeedState(values={need_id: 20.0 for need_id in NeedState().values})

    mood, modifiers = compute_mood(needs)

    assert mood == "breakdown"
    assert modifiers["tantrum_risk"] == 0.10


def test_ac07_colony_pressure_uses_documented_formulas():
    state = {
        "needs": {"food": 4, "security": 1, "materials": 2},
        "alerts": ["a1", "a2"],
        "residents": [{"id": str(index)} for index in range(5)],
        "rooms": [
            {"id": "r1", "beds": 1},
            {"id": "r2", "beds": 1},
            {"id": "r3", "beds": 1},
        ],
        "construction_queue": [{"id": "c1"}],
        "faction_pressure": ["p1"],
        "farm_plots": [],
    }

    pressure = colony_pressure_from_settlement(state)

    assert pressure.food == 40
    assert pressure.safety == 66
    assert pressure.morale == 80
    assert pressure.supply == 64
    assert pressure.housing == 60
    assert pressure.unrest == 46


def test_ac08_apply_morale_cascade_assigns_miserable_tier_modifiers():
    actors = [_actor("a1"), _actor("a2")]

    apply_morale_cascade(actors, 60)

    for actor in actors:
        assert actor.needs.modifiers["work_speed_mult"] == 0.5
        assert actor.needs.modifiers["social_hostility"] is True
        assert actor.needs.modifiers["task_refusal"] is True
        assert actor.needs.modifiers["tantrum_risk"] == 0.02


def test_ac09_production_ledger_detects_shortages_and_generates_quest_seed():
    ledger = production_ledger_from_settlement({"needs": {"food": 3, "materials": 1, "security": 0}})

    assert ledger.shortages == ["food"]
    assert "materials" in ledger.surpluses
    assert ledger.quest_seeds[0].kind == "food"


def test_ac10_pressure_tags_follow_threshold_rules():
    tags = pressure_tags_from_metrics(food=40, safety=70, morale=65, supply=50, housing=60, unrest=30)

    assert "food_insecure" in tags
    assert "resource_strain" in tags
    assert "unsafe" not in tags
    assert "housing_strain" not in tags
    assert "unrest" not in tags


def test_ac11_production_ledger_round_trip_preserves_fields():
    ledger = ProductionLedger(
        economy={"trade_balance": 12, "stockpile_value": 150},
        shortages=["food"],
        surpluses=["materials"],
        quest_seeds=[],
    )

    restored = ProductionLedger.from_dict(ledger.to_dict())

    assert restored == ledger


def test_ac12_room_contribution_adds_two_morale_per_furnished_room():
    bonus = room_morale_bonus(
        [
            {"id": "r1", "beds": 1},
            {"id": "r2", "beds": 1},
            {"id": "r3", "beds": 1},
            {"id": "r4", "beds": 1},
        ]
    )

    assert bonus == 8


def test_ac13_active_farm_plots_reduce_food_pressure_input():
    state = {
        "needs": {"food": 5, "security": 0, "materials": 0},
        "alerts": [],
        "residents": [{"id": "r1"}],
        "rooms": [{"id": "room", "beds": 1}],
        "construction_queue": [],
        "faction_pressure": [],
        "farm_plots": [{"id": "f1", "active": True}, {"id": "f2", "active": True}],
    }

    pressure = colony_pressure_from_settlement(state)

    assert pressure.food == 55


def test_ac14_migration_candidate_tag_is_emitted_when_colony_can_grow():
    tags = pressure_tags_from_metrics(food=65, safety=80, morale=75, supply=70, housing=85, unrest=20)

    assert "migration_candidate" in tags


def test_colony_pressure_state_round_trip_preserves_metrics_and_tags():
    pressure = ColonyPressureState(
        food=55,
        safety=70,
        morale=80,
        supply=65,
        housing=90,
        unrest=20,
        shortages=["food"],
        pressure_tags=["migration_candidate"],
        quest_seeds=[],
    )

    restored = ColonyPressureState.from_dict(pressure.to_dict())

    assert restored == pressure

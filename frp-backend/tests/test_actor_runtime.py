from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.world.actor_runtime import (
    Actor,
    ActorAnimationState,
    ActorStats,
    CombatInfo,
    IF_ACTIVE,
    IF_IDLE,
    IF_JUSTDIED,
    IF_REALLYDIED,
    IF_RUNNING,
    IF_VISIBLE,
    MAX_SCRIPTS,
    SCR_AREA,
    SCR_DEFAULT,
    SCR_GENERAL,
    SCR_OVERRIDE,
    TriggerEvent,
)
from engine.world.behavior_tree import BehaviorNode, Status


class _ScriptNode(BehaviorNode):
    def __init__(self, name: str, result: Status) -> None:
        super().__init__(name)
        self.result = result

    def tick(self, ctx) -> Status:
        ctx.blackboard.setdefault("calls", []).append(self.name)
        return self.result


class _EntityAwareNode(BehaviorNode):
    def __init__(self) -> None:
        super().__init__("EntityAware")

    def tick(self, ctx) -> Status:
        ctx.blackboard["entity_id"] = ctx.entity.id
        return Status.SUCCESS


def _context() -> SimpleNamespace:
    return SimpleNamespace(entity=None, blackboard={})


def test_actor_defaults_match_runtime_contract() -> None:
    actor = Actor(id="actor_1")

    assert actor.kind == "npc"
    assert actor.position == (0, 0)
    assert actor.facing == "south"
    assert actor.state_flags & IF_ACTIVE
    assert actor.state_flags & IF_VISIBLE
    assert len(actor.script_slots) == MAX_SCRIPTS
    assert actor.script_slots == [None] * MAX_SCRIPTS


def test_script_slot_constants_stay_stable() -> None:
    assert SCR_OVERRIDE == 0
    assert SCR_AREA == 1
    assert SCR_GENERAL == 6
    assert SCR_DEFAULT == 7
    assert MAX_SCRIPTS == 8


def test_flag_helpers_and_query_methods_work() -> None:
    actor = Actor(id="flags")

    actor.set_flag(IF_IDLE)
    assert actor.has_flag(IF_IDLE)
    assert actor.is_idle() is True
    actor.toggle_flag(IF_RUNNING)
    assert actor.is_running() is True
    actor.clear_flag(IF_RUNNING)
    assert actor.is_running() is False
    actor.clear_flag(IF_ACTIVE)
    assert actor.is_active() is False
    assert actor.is_visible() is True


def test_position_and_facing_mutators_normalize_values() -> None:
    actor = Actor(id="move")

    actor.set_position((5, 7))
    actor.set_facing("NE")

    assert actor.get_position() == (5, 7)
    assert actor.get_facing() == "ne"
    assert actor.animation_state.facing == "ne"


def test_stat_methods_roundtrip_and_modify() -> None:
    actor = Actor(id="stats", stats_ref=ActorStats(hp=12, max_hp=18, str_val=11))

    assert actor.get_stat("str_val") == 11
    actor.set_stat("str_val", 14)
    assert actor.get_stat("str_val") == 14
    assert actor.modify_stat("hp", -2) == 10
    with pytest.raises(KeyError):
        actor.get_stat("luck")


def test_script_slot_management_validates_bounds() -> None:
    actor = Actor(id="slots")
    node = _ScriptNode("override", Status.SUCCESS)

    actor.attach_script(SCR_OVERRIDE, node)
    assert actor.get_script(SCR_OVERRIDE) is node
    actor.detach_script(SCR_OVERRIDE)
    assert actor.get_script(SCR_OVERRIDE) is None
    with pytest.raises(IndexError):
        actor.attach_script(MAX_SCRIPTS, node)


def test_tick_runs_scripts_in_priority_order_and_short_circuits() -> None:
    actor = Actor(id="ticker")
    ctx = _context()
    actor.attach_script(SCR_OVERRIDE, _ScriptNode("override", Status.FAILURE))
    actor.attach_script(SCR_AREA, _ScriptNode("area", Status.FAILURE))
    actor.attach_script(SCR_GENERAL, _ScriptNode("general", Status.SUCCESS))
    actor.attach_script(SCR_DEFAULT, _ScriptNode("default", Status.SUCCESS))

    result = actor.tick(ctx)

    assert result == Status.SUCCESS
    assert ctx.blackboard["calls"] == ["override", "area", "general"]
    assert actor.is_idle() is False


def test_tick_assigns_actor_to_context_for_behavior_nodes() -> None:
    actor = Actor(id="entity-aware")
    ctx = _context()
    actor.attach_script(SCR_OVERRIDE, _EntityAwareNode())

    result = actor.tick(ctx)

    assert result == Status.SUCCESS
    assert ctx.blackboard["entity_id"] == actor.id


def test_apply_damage_and_heal_follow_hp_contract() -> None:
    actor = Actor(id="combat", stats_ref=ActorStats(hp=7, max_hp=10))

    dealt = actor.apply_damage(3, source_id="enemy_1")
    healed = actor.apply_heal(2)

    assert dealt == 3
    assert actor.get_hp() == 6
    assert healed == 2
    assert actor.trigger_queue == [TriggerEvent(event_type="damage", source_id="enemy_1", payload={"amount": 3})]


def test_death_sets_justdied_and_next_tick_transitions_to_reallydied() -> None:
    actor = Actor(id="dead", stats_ref=ActorStats(hp=2, max_hp=2))

    actor.apply_damage(99, source_id="fatal")
    assert actor.get_hp() == 0
    assert actor.has_flag(IF_JUSTDIED)
    assert actor.is_dead() is True

    result = actor.tick(_context())

    assert result == Status.SUCCESS
    assert actor.has_flag(IF_REALLYDIED)
    assert actor.has_flag(IF_JUSTDIED) is False
    assert actor.is_active() is False


def test_tick_with_no_scripts_marks_actor_idle() -> None:
    actor = Actor(id="idle")

    result = actor.tick(_context())

    assert result == Status.FAILURE
    assert actor.has_flag(IF_IDLE)


def test_actor_serialization_round_trip_preserves_nested_runtime_state() -> None:
    actor = Actor(
        id="serialize",
        kind="creature",
        position=(9, 4),
        facing="west",
        stats_ref=ActorStats(hp=5, max_hp=12, level=3, xp=900),
        combat_info=CombatInfo(in_combat=True, initiative=7, movement_remaining=2),
        animation_state=ActorAnimationState(current_state="walk", facing="west", frame_cursor=2),
        current_path=[(9, 4), (8, 4)],
        trigger_queue=[TriggerEvent(event_type="alarm", source_id="bell", payload={"radius": 3})],
    )

    payload = actor.to_dict()
    restored = Actor.from_dict(payload)

    assert payload["script_slot_names"] == [None] * MAX_SCRIPTS
    assert restored.id == actor.id
    assert restored.kind == "creature"
    assert restored.position == (9, 4)
    assert restored.facing == "west"
    assert restored.stats_ref.level == 3
    assert restored.combat_info.in_combat is True
    assert restored.animation_state.current_state == "walk"
    assert restored.current_path == [(9, 4), (8, 4)]
    assert restored.trigger_queue == [TriggerEvent(event_type="alarm", source_id="bell", payload={"radius": 3})]

from __future__ import annotations

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.scripts import (
    Action,
    ScriptBlock,
    ScriptDef,
    ScriptState,
    Trigger,
    evaluate_trigger,
    execute_action,
    resolve_target,
    tick_script,
)


def _actor(actor_id: str, *, x: int, faction: str, hp: int = 20, max_hp: int = 20) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc", faction_id=faction),
        position=ActorPosition(x=x, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"hp": hp, "max_hp": max_hp},
        raw_payload={"visual_range": 10, "level": 5},
    )


def test_ac01_tick_script_returns_first_matching_block_actions_only():
    actor = _actor("npc", x=0, faction="allies")
    enemy = _actor("enemy", x=3, faction="enemies")
    script = ScriptDef(
        script_id="general_ai",
        label="General AI",
        blocks=[
            ScriptBlock(triggers=[Trigger("global_eq", {"scope": "local", "name": "alerted", "value": 1})], actions=[Action("wait")]),
            ScriptBlock(triggers=[Trigger("see", {"target_filter": "nearest_enemy"})], actions=[Action("attack", {"target": "nearest_enemy"})]),
            ScriptBlock(triggers=[], actions=[Action("flee")]),
        ],
    )
    script_state = ScriptState(actor_id="npc", scripts={"general": "general_ai"})

    actions = tick_script(actor, script_state, {"general_ai": script}, {"actors": [actor, enemy]}, {})

    assert [action.action_type for action in actions] == ["attack"]


def test_ac02_see_trigger_passes_with_enemy_in_visual_range():
    actor = _actor("npc", x=0, faction="allies")
    enemy = _actor("enemy", x=5, faction="enemies")

    result = evaluate_trigger(
        Trigger("see", {"target_filter": "nearest_enemy"}),
        actor,
        ScriptState(actor_id="npc"),
        {"actors": [actor, enemy]},
        {},
    )

    assert result is True


def test_ac03_hp_percent_lt_trigger_works_for_low_health():
    actor = _actor("npc", x=0, faction="allies", hp=8, max_hp=20)

    result = evaluate_trigger(
        Trigger("hp_percent_lt", {"target": "myself", "percent": 50}),
        actor,
        ScriptState(actor_id="npc"),
        {"actors": [actor]},
        {},
    )

    assert result is True


def test_ac04_global_eq_trigger_fails_when_local_variable_mismatches():
    actor = _actor("npc", x=0, faction="allies")
    script_state = ScriptState(actor_id="npc", variables={"alerted": 0})

    result = evaluate_trigger(
        Trigger("global_eq", {"scope": "local", "name": "alerted", "value": 1}),
        actor,
        script_state,
        {"actors": [actor]},
        {},
    )

    assert result is False


def test_ac05_attack_action_returns_attack_event_with_target_id():
    actor = _actor("npc", x=0, faction="allies")
    enemy = _actor("enemy", x=3, faction="enemies")

    event = execute_action(Action("attack", {"target": "nearest_enemy"}), actor, {"actors": [actor, enemy], "script_states": {}}, {})

    assert event == {"type": "attack", "target_id": "enemy"}


def test_ac06_set_global_action_updates_local_script_variables():
    actor = _actor("npc", x=0, faction="allies")
    script_state = ScriptState(actor_id="npc")
    world_context = {"actors": [actor], "script_states": {"npc": script_state}}

    execute_action(Action("set_global", {"scope": "local", "name": "alerted", "value": 1}), actor, world_context, {})

    assert script_state.variables["alerted"] == 1


def test_ac07_override_script_slot_runs_before_general():
    actor = _actor("npc", x=0, faction="allies")
    enemy = _actor("enemy", x=3, faction="enemies")
    override_script = ScriptDef(script_id="override_ai", label="Override", blocks=[ScriptBlock(triggers=[], actions=[Action("wait")])])
    general_script = ScriptDef(
        script_id="general_ai",
        label="General",
        blocks=[ScriptBlock(triggers=[Trigger("see", {"target_filter": "nearest_enemy"})], actions=[Action("attack", {"target": "nearest_enemy"})])],
    )
    script_state = ScriptState(actor_id="npc", scripts={"general": "general_ai", "override": "override_ai"})

    actions = tick_script(actor, script_state, {"general_ai": general_script, "override_ai": override_script}, {"actors": [actor, enemy]}, {})

    assert [action.action_type for action in actions] == ["wait"]


def test_ac08_shout_action_sets_heard_flag_on_allies_in_range():
    actor = _actor("npc", x=0, faction="allies")
    ally = _actor("ally", x=4, faction="allies")
    script_states = {
        "npc": ScriptState(actor_id="npc"),
        "ally": ScriptState(actor_id="ally"),
    }

    execute_action(Action("shout", {"message_id": "help"}), actor, {"actors": [actor, ally], "script_states": script_states, "hearing_range": 6}, {})

    assert script_states["ally"].variables["heard_shout_help"] is True


def test_ac09_resolve_target_nearest_enemy_picks_closest_hostile():
    actor = _actor("npc", x=0, faction="allies")
    enemies = [
        _actor("enemy_a", x=5, faction="enemies"),
        _actor("enemy_b", x=3, faction="enemies"),
        _actor("enemy_c", x=8, faction="enemies"),
    ]

    target = resolve_target("nearest_enemy", actor, {"actors": [actor, *enemies]})

    assert target is not None and target.identity.actor_id == "enemy_b"


def test_ac10_script_def_round_trip_preserves_nested_blocks():
    script = ScriptDef(
        script_id="guard_ai",
        label="Guard AI",
        blocks=[
            ScriptBlock(
                triggers=[Trigger("see", {"target_filter": "nearest_enemy"})],
                actions=[Action("attack", {"target": "nearest_enemy"}), Action("shout", {"message_id": "help"})],
            )
        ],
    )

    restored = ScriptDef.from_dict(script.to_dict())

    assert restored == script

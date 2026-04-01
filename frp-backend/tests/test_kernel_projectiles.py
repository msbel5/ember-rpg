from __future__ import annotations

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.effects import EffectDef
from engine.kernel.projectiles import (
    ProjectileDef,
    actors_along_line,
    actors_in_cone,
    actors_in_radius,
    launch_projectile,
    resolve_impact,
    tick_projectile,
)


def _actor(*, actor_id: str, x: float, y: float, faction: str = "allies") -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc", faction_id=faction),
        position=ActorPosition(x=int(x), y=int(y)),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"hp": 20, "max_hp": 20},
        raw_payload={"pos_float": (float(x), float(y)), "effect_registry": _effect_registry()},
    )


def _effect_registry() -> dict[str, EffectDef]:
    return {
        "burn": EffectDef(effect_def_id="burn", label="Burn", category="condition", condition_flag="burning"),
        "blast": EffectDef(effect_def_id="blast", label="Blast", category="dot", damage_per_tick=5, damage_type="fire"),
    }


def test_ac01_none_projectile_resolves_instantly():
    caster = _actor(actor_id="caster", x=0, y=0)
    target = _actor(actor_id="target", x=1, y=0, faction="enemies")
    proj_def = ProjectileDef(projectile_id="touch", projectile_type="none", effect_def_ids=["burn"])

    projectile = launch_projectile(proj_def, caster, target_pos=(1, 0), target_id="target", current_tick=0)
    events = resolve_impact(projectile, [target], _effect_registry(), current_tick=0)

    assert projectile.resolved is True
    assert events[0]["target_id"] == "target"


def test_ac02_arrow_arrives_after_distance_divided_by_speed():
    caster = _actor(actor_id="caster", x=0, y=0)
    proj_def = ProjectileDef(projectile_id="arrow", projectile_type="arrow", speed=5.0, effect_def_ids=["burn"])
    projectile = launch_projectile(proj_def, caster, target_pos=(15, 0), target_id="target", current_tick=0)

    assert tick_projectile(projectile) is False
    assert tick_projectile(projectile) is False
    assert tick_projectile(projectile) is True


def test_ac03_fireball_skips_allies_when_friendly_fire_disabled():
    caster = _actor(actor_id="caster", x=0, y=0, faction="allies")
    actors = [
        _actor(actor_id="ally_1", x=5, y=0, faction="allies"),
        _actor(actor_id="ally_2", x=6, y=0, faction="allies"),
        _actor(actor_id="enemy_1", x=5, y=1, faction="enemies"),
        _actor(actor_id="enemy_2", x=6, y=1, faction="enemies"),
    ]
    proj_def = ProjectileDef(projectile_id="fireball", projectile_type="fireball", area_radius=3, friendly_fire=False, effect_def_ids=["burn"])
    projectile = launch_projectile(proj_def, caster, target_pos=(5, 0), target_id=None, current_tick=0)

    events = resolve_impact(projectile, actors, _effect_registry(), current_tick=0)

    assert sorted(event["target_id"] for event in events) == ["enemy_1", "enemy_2"]


def test_ac04_cone_geometry_hits_only_targets_in_fan_and_range():
    candidates = [
        _actor(actor_id="front", x=3, y=0, faction="enemies"),
        _actor(actor_id="front_side", x=3, y=2, faction="enemies"),
        _actor(actor_id="behind", x=-2, y=1, faction="enemies"),
    ]

    hits = actors_in_cone((0, 0), (5, 0), 90, 5, candidates)

    assert sorted(actor.identity.actor_id for actor in hits) == ["front", "front_side"]


def test_ac05_bouncing_projectile_hits_up_to_max_additional_targets_with_decay():
    caster = _actor(actor_id="caster", x=0, y=0, faction="allies")
    targets = [
        _actor(actor_id="target_1", x=3, y=0, faction="enemies"),
        _actor(actor_id="target_2", x=4, y=1, faction="enemies"),
        _actor(actor_id="target_3", x=5, y=1, faction="enemies"),
        _actor(actor_id="target_4", x=6, y=1, faction="enemies"),
    ]
    proj_def = ProjectileDef(projectile_id="chain", projectile_type="bouncing", max_bounces=3, bounce_decay=0.8, effect_def_ids=["burn"])
    projectile = launch_projectile(proj_def, caster, target_pos=(3, 0), target_id="target_1", current_tick=0)

    events = resolve_impact(projectile, targets, _effect_registry(), current_tick=0)

    assert [event["target_id"] for event in events] == ["target_1", "target_2", "target_3", "target_4"]
    assert [event["decay_factor"] for event in events] == [1.0, 0.8, 0.64, 0.512]


def test_ac06_traveling_projectile_hits_actors_along_line():
    caster = _actor(actor_id="caster", x=0, y=0)
    target = _actor(actor_id="line_target", x=5, y=0.5, faction="enemies")
    off_line = _actor(actor_id="off_line", x=5, y=2, faction="enemies")
    proj_def = ProjectileDef(projectile_id="lightning", projectile_type="traveling", effect_def_ids=["blast"])
    projectile = launch_projectile(proj_def, caster, target_pos=(10, 0), target_id=None, current_tick=0)

    events = resolve_impact(projectile, [target, off_line], _effect_registry(), current_tick=0)

    assert [event["target_id"] for event in events] == ["line_target"]


def test_ac07_friendly_fire_true_hits_all_targets_in_area():
    caster = _actor(actor_id="caster", x=0, y=0, faction="allies")
    actors = [
        _actor(actor_id="ally", x=5, y=0, faction="allies"),
        _actor(actor_id="enemy", x=5, y=1, faction="enemies"),
    ]
    proj_def = ProjectileDef(projectile_id="fireball", projectile_type="fireball", area_radius=3, friendly_fire=True, effect_def_ids=["burn"])
    projectile = launch_projectile(proj_def, caster, target_pos=(5, 0), target_id=None, current_tick=0)

    events = resolve_impact(projectile, actors, _effect_registry(), current_tick=0)

    assert sorted(event["target_id"] for event in events) == ["ally", "enemy"]


def test_ac08_flight_tick_advances_position_and_arrives_on_exact_tick():
    caster = _actor(actor_id="caster", x=0, y=0)
    proj_def = ProjectileDef(projectile_id="arrow", projectile_type="arrow", speed=3.0, effect_def_ids=["burn"])
    projectile = launch_projectile(proj_def, caster, target_pos=(9, 0), target_id="target", current_tick=0)

    assert tick_projectile(projectile) is False
    assert projectile.current_pos == (3.0, 0.0)
    assert tick_projectile(projectile) is False
    assert tick_projectile(projectile) is True


def test_ac09_each_valid_target_receives_all_projectile_effect_ids():
    caster = _actor(actor_id="caster", x=0, y=0, faction="allies")
    targets = [
        _actor(actor_id="enemy_1", x=5, y=0, faction="enemies"),
        _actor(actor_id="enemy_2", x=5, y=1, faction="enemies"),
        _actor(actor_id="enemy_3", x=6, y=1, faction="enemies"),
    ]
    proj_def = ProjectileDef(projectile_id="fireball", projectile_type="fireball", area_radius=3, friendly_fire=False, effect_def_ids=["burn", "blast"])
    projectile = launch_projectile(proj_def, caster, target_pos=(5, 0), target_id=None, current_tick=0)

    events = resolve_impact(projectile, targets, _effect_registry(), current_tick=0)

    assert all(event["effects_applied"] == ["burn", "blast"] for event in events)


def test_ac10_projectile_def_round_trip_preserves_all_fields():
    definition = ProjectileDef(
        projectile_id="chain_lightning",
        projectile_type="bouncing",
        speed=7.5,
        area_radius=2,
        cone_angle=120,
        max_bounces=4,
        bounce_decay=0.75,
        effect_def_ids=["burn", "blast"],
        friendly_fire=False,
        hostile=True,
        damage_type="lightning",
        flags=["trail", "fragment"],
    )

    restored = ProjectileDef.from_dict(definition.to_dict())

    assert restored == definition


def test_actors_in_radius_filters_by_distance():
    center = (0, 0)
    candidates = [
        _actor(actor_id="near", x=2, y=0),
        _actor(actor_id="far", x=5, y=0),
    ]

    hits = actors_in_radius(center, 3, candidates)

    assert [actor.identity.actor_id for actor in hits] == ["near"]


def test_actors_along_line_filters_by_perpendicular_distance():
    start = (0, 0)
    end = (10, 0)
    candidates = [
        _actor(actor_id="close", x=5, y=0.5),
        _actor(actor_id="far", x=5, y=2),
    ]

    hits = actors_along_line(start, end, 1.0, candidates)

    assert [actor.identity.actor_id for actor in hits] == ["close"]

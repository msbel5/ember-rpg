"""
Targeting geometry contract tests.

Freezes the geometry primitives used by the projectile system so that
future delivery types (bow, fireball, gun, beam, laser) can rely on
the same underlying math without regression.

These tests are ADDITIVE — no renames, no refactors, no production edits.
They exercise the geometry helpers directly (actors_in_radius, actors_in_cone,
actors_along_line) and the flight/arrival model (tick_projectile, launch_projectile).

Future note: the same primitives are usable for non-projectile delivery
types (e.g. gaze attack radius, shout cone, trap trigger radius, aura pulse).
"""

from __future__ import annotations

import math

import pytest

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.effects import EffectDef
from engine.kernel.projectiles import (
    ProjectileDef,
    ProjectileInstance,
    actors_along_line,
    actors_in_cone,
    actors_in_radius,
    launch_projectile,
    resolve_impact,
    tick_projectile,
)
from engine.world.proximity import (
    RANGE_MELEE,
    RANGE_RANGED,
    RANGE_SHOUT,
    RANGE_SOCIAL,
    distance,
    has_line_of_sight,
    in_range,
)


# ── Shared fixtures ──────────────────────────────────────────────────


def _actor(
    *,
    actor_id: str,
    x: float,
    y: float,
    faction: str = "allies",
) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(
            actor_id=actor_id,
            display_name=actor_id,
            actor_type="npc",
            faction_id=faction,
        ),
        position=ActorPosition(x=int(x), y=int(y)),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"hp": 20, "max_hp": 20},
        raw_payload={
            "pos_float": (float(x), float(y)),
            "effect_registry": _effect_registry(),
        },
    )


def _effect_registry() -> dict[str, EffectDef]:
    return {
        "burn": EffectDef(
            effect_def_id="burn",
            label="Burn",
            category="condition",
            condition_flag="burning",
        ),
    }


# ═════════════════════════════════════════════════════════════════════
#  RADIUS GEOMETRY  (center + distance)
#  Future: aura, explosion, trap trigger, shout area, healing pulse
# ═════════════════════════════════════════════════════════════════════


class TestRadiusGeometry:
    """actors_in_radius: Euclidean distance from center ≤ radius."""

    def test_exact_boundary_included(self):
        """Actor at exactly radius distance IS included."""
        candidates = [_actor(actor_id="edge", x=3, y=0)]
        hits = actors_in_radius((0, 0), 3, candidates)
        assert len(hits) == 1

    def test_just_outside_boundary_excluded(self):
        """Actor barely beyond radius IS excluded."""
        candidates = [_actor(actor_id="outside", x=3, y=1)]
        hits = actors_in_radius((0, 0), 3, candidates)
        # distance ≈ 3.16, should be excluded for radius=3
        assert len(hits) == 0

    def test_center_included(self):
        """Actor at exact center IS included (distance=0)."""
        candidates = [_actor(actor_id="center", x=0, y=0)]
        hits = actors_in_radius((0, 0), 5, candidates)
        assert len(hits) == 1

    def test_multiple_actors_mixed_distances(self):
        """Only actors within radius returned, others excluded."""
        candidates = [
            _actor(actor_id="near", x=1, y=1),   # dist ≈ 1.41
            _actor(actor_id="mid", x=3, y=0),     # dist = 3.0
            _actor(actor_id="far", x=5, y=5),     # dist ≈ 7.07
        ]
        hits = actors_in_radius((0, 0), 4, candidates)
        assert sorted(a.identity.actor_id for a in hits) == ["mid", "near"]

    def test_zero_radius_hits_only_center(self):
        """Radius 0 only hits actors at the exact center."""
        candidates = [
            _actor(actor_id="at_center", x=0, y=0),
            _actor(actor_id="adjacent", x=1, y=0),
        ]
        hits = actors_in_radius((0, 0), 0, candidates)
        assert [a.identity.actor_id for a in hits] == ["at_center"]

    def test_radius_is_euclidean_not_chebyshev(self):
        """Diagonal actor at (3,3) has Euclidean dist ≈4.24, NOT Chebyshev=3."""
        candidates = [_actor(actor_id="diagonal", x=3, y=3)]
        # Chebyshev=3, Euclidean≈4.24
        hits_r3 = actors_in_radius((0, 0), 3, candidates)
        hits_r5 = actors_in_radius((0, 0), 5, candidates)
        assert len(hits_r3) == 0  # Euclidean ≈ 4.24 > 3
        assert len(hits_r5) == 1  # Euclidean ≈ 4.24 < 5


# ═════════════════════════════════════════════════════════════════════
#  CONE GEOMETRY  (origin + direction + angle + length)
#  Future: breath weapon, gaze attack, fan slash, shotgun spread
# ═════════════════════════════════════════════════════════════════════


class TestConeGeometry:
    """actors_in_cone: within angle arc AND within length distance."""

    def test_directly_ahead_within_range(self):
        """Actor directly in the cone direction is hit."""
        candidates = [_actor(actor_id="front", x=3, y=0, faction="enemies")]
        hits = actors_in_cone((0, 0), (5, 0), 90, 5, candidates)
        assert len(hits) == 1

    def test_behind_origin_excluded(self):
        """Actor behind the cone origin is excluded."""
        candidates = [_actor(actor_id="behind", x=-3, y=0, faction="enemies")]
        hits = actors_in_cone((0, 0), (5, 0), 90, 5, candidates)
        assert len(hits) == 0

    def test_beyond_length_excluded(self):
        """Actor in the right direction but beyond length is excluded."""
        candidates = [_actor(actor_id="far", x=10, y=0, faction="enemies")]
        hits = actors_in_cone((0, 0), (5, 0), 90, 5, candidates)
        assert len(hits) == 0

    def test_outside_angle_excluded(self):
        """Actor within range but outside the cone angle is excluded."""
        candidates = [_actor(actor_id="side", x=0, y=5, faction="enemies")]
        hits = actors_in_cone((0, 0), (5, 0), 45, 5, candidates)
        assert len(hits) == 0

    def test_wide_angle_catches_more(self):
        """180-degree cone catches actors to the sides."""
        side_actor = _actor(actor_id="side", x=2, y=2, faction="enemies")
        hits_narrow = actors_in_cone((0, 0), (5, 0), 45, 5, [side_actor])
        hits_wide = actors_in_cone((0, 0), (5, 0), 180, 5, [side_actor])
        assert len(hits_narrow) == 0
        assert len(hits_wide) == 1

    def test_zero_direction_returns_empty(self):
        """When origin == direction point, cone is degenerate, no hits."""
        candidates = [_actor(actor_id="any", x=1, y=0, faction="enemies")]
        hits = actors_in_cone((0, 0), (0, 0), 90, 5, candidates)
        assert len(hits) == 0

    def test_diagonal_cone_direction(self):
        """Cone aimed diagonally hits actors along that diagonal."""
        candidates = [
            _actor(actor_id="diagonal", x=3, y=3, faction="enemies"),
            _actor(actor_id="off_axis", x=4, y=0, faction="enemies"),
        ]
        hits = actors_in_cone((0, 0), (5, 5), 60, 6, candidates)
        hit_ids = [a.identity.actor_id for a in hits]
        assert "diagonal" in hit_ids
        assert "off_axis" not in hit_ids


# ═════════════════════════════════════════════════════════════════════
#  LINE GEOMETRY  (start + end + width)
#  Future: beam, laser, lightning bolt, ray, piercing arrow
# ═════════════════════════════════════════════════════════════════════


class TestLineGeometry:
    """actors_along_line: perpendicular distance to line ≤ width."""

    def test_on_line_hit(self):
        """Actor exactly on the line is hit."""
        candidates = [_actor(actor_id="on_line", x=5, y=0)]
        hits = actors_along_line((0, 0), (10, 0), 1.0, candidates)
        assert len(hits) == 1

    def test_near_line_within_width_hit(self):
        """Actor within width of the line is hit."""
        candidates = [_actor(actor_id="near", x=5, y=0.5)]
        hits = actors_along_line((0, 0), (10, 0), 1.0, candidates)
        assert len(hits) == 1

    def test_beyond_width_excluded(self):
        """Actor beyond width from the line is excluded."""
        candidates = [_actor(actor_id="far", x=5, y=2)]
        hits = actors_along_line((0, 0), (10, 0), 1.0, candidates)
        assert len(hits) == 0

    def test_before_start_excluded(self):
        """Actor behind the start of the line segment is excluded."""
        candidates = [_actor(actor_id="before", x=-3, y=0)]
        hits = actors_along_line((0, 0), (10, 0), 1.0, candidates)
        assert len(hits) == 0

    def test_after_end_excluded(self):
        """Actor beyond the end of the line segment is excluded."""
        candidates = [_actor(actor_id="after", x=12, y=0)]
        hits = actors_along_line((0, 0), (10, 0), 1.0, candidates)
        assert len(hits) == 0

    def test_diagonal_line(self):
        """Line along a diagonal still hits actors near it."""
        candidates = [
            _actor(actor_id="on_diag", x=3, y=3),
            _actor(actor_id="off_diag", x=3, y=0),
        ]
        hits = actors_along_line((0, 0), (6, 6), 1.0, candidates)
        hit_ids = [a.identity.actor_id for a in hits]
        assert "on_diag" in hit_ids
        assert "off_diag" not in hit_ids

    def test_zero_length_line_returns_empty(self):
        """Degenerate line (start == end) returns no hits."""
        candidates = [_actor(actor_id="any", x=0, y=0)]
        hits = actors_along_line((5, 5), (5, 5), 1.0, candidates)
        assert len(hits) == 0

    def test_narrow_width_is_precise(self):
        """Width=0.1 only hits actors extremely close to the line."""
        candidates = [
            _actor(actor_id="exact", x=5, y=0),
            _actor(actor_id="close", x=5, y=0.5),
        ]
        hits = actors_along_line((0, 0), (10, 0), 0.1, candidates)
        assert [a.identity.actor_id for a in hits] == ["exact"]


# ═════════════════════════════════════════════════════════════════════
#  FLIGHT / ARRIVAL  (speed, tick progression, exact arrival)
#  Future: arrows, thrown weapons, slow missiles, homing projectiles
# ═════════════════════════════════════════════════════════════════════


class TestFlightArrival:
    """tick_projectile: advances position by speed per tick until arrival."""

    def test_arrives_in_expected_ticks(self):
        """Distance / speed = expected tick count."""
        caster = _actor(actor_id="caster", x=0, y=0)
        proj_def = ProjectileDef(
            projectile_id="arrow",
            projectile_type="arrow",
            speed=4.0,
            effect_def_ids=["burn"],
        )
        proj = launch_projectile(
            proj_def, caster, target_pos=(12, 0), target_id="t", current_tick=0
        )
        ticks = 0
        while not tick_projectile(proj):
            ticks += 1
        ticks += 1  # count the arrival tick
        assert ticks == 3  # 12 / 4 = 3

    def test_position_advances_linearly(self):
        """After each tick, position moves by speed toward target."""
        caster = _actor(actor_id="caster", x=0, y=0)
        proj_def = ProjectileDef(
            projectile_id="arrow",
            projectile_type="arrow",
            speed=5.0,
            effect_def_ids=["burn"],
        )
        proj = launch_projectile(
            proj_def, caster, target_pos=(15, 0), target_id="t", current_tick=0
        )
        tick_projectile(proj)
        assert proj.current_pos == pytest.approx((5.0, 0.0), abs=0.01)
        tick_projectile(proj)
        assert proj.current_pos == pytest.approx((10.0, 0.0), abs=0.01)

    def test_arrival_lands_exactly_on_target(self):
        """On arrival tick, position equals target_pos exactly."""
        caster = _actor(actor_id="caster", x=0, y=0)
        proj_def = ProjectileDef(
            projectile_id="arrow",
            projectile_type="arrow",
            speed=5.0,
            effect_def_ids=["burn"],
        )
        proj = launch_projectile(
            proj_def, caster, target_pos=(10, 0), target_id="t", current_tick=0
        )
        tick_projectile(proj)  # 5.0
        arrived = tick_projectile(proj)  # 10.0
        assert arrived is True
        assert proj.current_pos == (10.0, 0.0)

    def test_instant_type_arrives_immediately(self):
        """projectile_type='none' resolves in zero ticks."""
        caster = _actor(actor_id="caster", x=0, y=0)
        proj_def = ProjectileDef(
            projectile_id="touch",
            projectile_type="none",
            effect_def_ids=["burn"],
        )
        proj = launch_projectile(
            proj_def, caster, target_pos=(10, 10), target_id="t", current_tick=0
        )
        arrived = tick_projectile(proj)
        assert arrived is True
        assert proj.current_pos == (10.0, 10.0)

    def test_cone_type_is_instant(self):
        """projectile_type='cone' also resolves instantly (no flight)."""
        caster = _actor(actor_id="caster", x=0, y=0)
        proj_def = ProjectileDef(
            projectile_id="breath",
            projectile_type="cone",
            cone_angle=90,
            effect_def_ids=["burn"],
        )
        proj = launch_projectile(
            proj_def, caster, target_pos=(5, 0), target_id=None, current_tick=0
        )
        arrived = tick_projectile(proj)
        assert arrived is True

    def test_diagonal_flight_advances_correctly(self):
        """Flight along a diagonal advances both x and y proportionally."""
        caster = _actor(actor_id="caster", x=0, y=0)
        proj_def = ProjectileDef(
            projectile_id="arrow",
            projectile_type="arrow",
            speed=5.0,
            effect_def_ids=["burn"],
        )
        target = (3.0, 4.0)  # distance = 5.0
        proj = launch_projectile(
            proj_def, caster, target_pos=target, target_id="t", current_tick=0
        )
        arrived = tick_projectile(proj)
        assert arrived is True
        assert proj.current_pos == pytest.approx(target, abs=0.01)

    def test_speed_greater_than_distance_arrives_in_one_tick(self):
        """If speed > distance, arrival happens in a single tick."""
        caster = _actor(actor_id="caster", x=0, y=0)
        proj_def = ProjectileDef(
            projectile_id="fast",
            projectile_type="arrow",
            speed=100.0,
            effect_def_ids=["burn"],
        )
        proj = launch_projectile(
            proj_def, caster, target_pos=(5, 0), target_id="t", current_tick=0
        )
        assert tick_projectile(proj) is True


# ═════════════════════════════════════════════════════════════════════
#  FRIENDLY FIRE FILTERING
#  Future: area denial, friendly auras, hostile-only beams
# ═════════════════════════════════════════════════════════════════════


class TestFriendlyFireFiltering:
    """resolve_impact: friendly_fire flag controls ally inclusion."""

    def test_friendly_fire_false_excludes_caster_faction(self):
        caster = _actor(actor_id="caster", x=0, y=0, faction="allies")
        actors = [
            _actor(actor_id="ally", x=5, y=0, faction="allies"),
            _actor(actor_id="enemy", x=5, y=1, faction="enemies"),
        ]
        proj_def = ProjectileDef(
            projectile_id="fb",
            projectile_type="fireball",
            area_radius=3,
            friendly_fire=False,
            effect_def_ids=["burn"],
        )
        proj = launch_projectile(
            proj_def, caster, target_pos=(5, 0), target_id=None, current_tick=0
        )
        events = resolve_impact(proj, actors, _effect_registry(), current_tick=0)
        assert [e["target_id"] for e in events] == ["enemy"]

    def test_friendly_fire_true_includes_all(self):
        caster = _actor(actor_id="caster", x=0, y=0, faction="allies")
        actors = [
            _actor(actor_id="ally", x=5, y=0, faction="allies"),
            _actor(actor_id="enemy", x=5, y=1, faction="enemies"),
        ]
        proj_def = ProjectileDef(
            projectile_id="fb",
            projectile_type="fireball",
            area_radius=3,
            friendly_fire=True,
            effect_def_ids=["burn"],
        )
        proj = launch_projectile(
            proj_def, caster, target_pos=(5, 0), target_id=None, current_tick=0
        )
        events = resolve_impact(proj, actors, _effect_registry(), current_tick=0)
        assert sorted(e["target_id"] for e in events) == ["ally", "enemy"]

    def test_neutral_faction_always_hit(self):
        """Actors with a different non-caster faction are always targeted."""
        caster = _actor(actor_id="caster", x=0, y=0, faction="allies")
        actors = [
            _actor(actor_id="neutral", x=5, y=0, faction="neutral"),
            _actor(actor_id="ally", x=5, y=1, faction="allies"),
        ]
        proj_def = ProjectileDef(
            projectile_id="fb",
            projectile_type="fireball",
            area_radius=5,
            friendly_fire=False,
            effect_def_ids=["burn"],
        )
        proj = launch_projectile(
            proj_def, caster, target_pos=(5, 0), target_id=None, current_tick=0
        )
        events = resolve_impact(proj, actors, _effect_registry(), current_tick=0)
        hit_ids = [e["target_id"] for e in events]
        assert "neutral" in hit_ids
        assert "ally" not in hit_ids


# ═════════════════════════════════════════════════════════════════════
#  PROXIMITY RANGE CONSTANTS  (tile-based range contract)
#  Future: different weapon range tiers, vision range, audio range
# ═════════════════════════════════════════════════════════════════════


class TestProximityRangeConstants:
    """Freeze the range constants used by the proximity system."""

    def test_melee_range_is_1(self):
        assert RANGE_MELEE == 1

    def test_ranged_range_is_5(self):
        assert RANGE_RANGED == 5

    def test_social_range_is_3(self):
        assert RANGE_SOCIAL == 3

    def test_shout_range_is_5(self):
        assert RANGE_SHOUT == 5

    def test_melee_is_strictly_less_than_ranged(self):
        assert RANGE_MELEE < RANGE_RANGED

    def test_social_is_between_melee_and_ranged(self):
        assert RANGE_MELEE < RANGE_SOCIAL <= RANGE_RANGED


# ═════════════════════════════════════════════════════════════════════
#  LINE OF SIGHT  (Bresenham's contract)
#  Future: fog of war, cover calculation, sniper lines
# ═════════════════════════════════════════════════════════════════════


class TestLineOfSight:
    """has_line_of_sight: Bresenham LoS through map tiles."""

    def test_no_map_always_clear(self):
        """Without a map, LoS is always True."""
        assert has_line_of_sight(None, [0, 0], [10, 10]) is True

    def test_adjacent_always_clear(self):
        assert has_line_of_sight(None, [5, 5], [5, 6]) is True

    def test_same_position_clear(self):
        assert has_line_of_sight(None, [3, 3], [3, 3]) is True


# ═════════════════════════════════════════════════════════════════════
#  PROJECTILE DEF SHAPE  (delivery-type registry contract)
#  Future: new projectile_types for gun, beam, laser, grenade
# ═════════════════════════════════════════════════════════════════════


class TestProjectileDefContract:
    """Freeze ProjectileDef fields that delivery types rely on."""

    def test_valid_projectile_types(self):
        """All supported projectile_type values."""
        for ptype in ("none", "arrow", "fireball", "cone", "bouncing", "traveling"):
            proj = ProjectileDef(
                projectile_id=f"test_{ptype}",
                projectile_type=ptype,
                effect_def_ids=["burn"],
            )
            assert proj.projectile_type == ptype

    def test_invalid_projectile_type_raises(self):
        with pytest.raises(ValueError, match="Unknown projectile_type"):
            ProjectileDef(
                projectile_id="bad",
                projectile_type="laser",
                effect_def_ids=["burn"],
            )

    def test_def_has_all_geometry_fields(self):
        """Every geometry-relevant field is present on ProjectileDef."""
        proj = ProjectileDef(
            projectile_id="test",
            projectile_type="fireball",
            speed=5.0,
            area_radius=3,
            cone_angle=90,
            friendly_fire=False,
            effect_def_ids=["burn"],
        )
        assert hasattr(proj, "speed")
        assert hasattr(proj, "area_radius")
        assert hasattr(proj, "cone_angle")
        assert hasattr(proj, "friendly_fire")

    def test_round_trip_preserves_geometry(self):
        """Serialization preserves all geometry fields."""
        original = ProjectileDef(
            projectile_id="test",
            projectile_type="cone",
            speed=7.0,
            area_radius=4,
            cone_angle=120,
            friendly_fire=False,
            effect_def_ids=["burn"],
            flags=["trail"],
        )
        restored = ProjectileDef.from_dict(original.to_dict())
        assert restored.speed == original.speed
        assert restored.area_radius == original.area_radius
        assert restored.cone_angle == original.cone_angle
        assert restored.friendly_fire == original.friendly_fire
        assert restored.flags == original.flags

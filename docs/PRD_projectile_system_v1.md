# PRD: Projectile System V1
**Project:** Ember RPG
**Phase:** 2
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the projectile (missile) system that carries spell and ranged weapon effects from source to target. Synthesizes GemRB M12 (Projectile.cpp — 6 projectile types, AoE, friend/foe filtering) with DF's material-based ranged combat. Every ranged attack and non-instant spell creates a `ProjectileInstance` that travels through space, impacts target(s), and delivers effects.

## 2. Scope

### In scope
- `ProjectileDef`: static definition (type, speed, area_radius, flags, effect_def_ids)
- `ProjectileInstance`: runtime state (position, velocity, target, tick_created)
- 6 projectile types: NONE (instant), ARROW (line), FIREBALL (point→explode), CONE (fan), BOUNCING (ricochet), TRAVELING (path AoE)
- Flight simulation: tick-based movement from source to target at defined speed
- Impact resolution: on arrival, apply effects to target(s)
- AoE resolution: effects applied to all actors within area_radius, friend/foe filtering
- Cone geometry: 90-degree fan from caster position, length = range
- Bouncing: ricochet to N additional targets within range
- Line/traveling: damage all actors along the path
- Integration with Effect System and Spell System

### Out of scope
- Visual projectile rendering (UI layer)
- Projectile animation frames
- Terrain collision (simplified — projectiles reach targets)

## 3. Functional Requirements (FR)

**FR-01 (ProjectileDef):** Defines: projectile_id, projectile_type (none/arrow/fireball/cone/bouncing/traveling), speed (tiles per tick), area_radius, max_bounces, cone_angle (degrees), effect_def_ids, flags (friendly_fire, trail, fragment), damage_type.

**FR-02 (NONE type):** Instant delivery. Effects applied to target immediately with no travel time. Used for touch spells, melee on-hit effects.

**FR-03 (ARROW type):** Linear flight from source to single target. Travel time = `distance / speed` ticks. On impact: apply effects to target only.

**FR-04 (FIREBALL type):** Linear flight to target point. On arrival: explode with area_radius. Apply effects to ALL actors within radius. Friend/foe check: if `friendly_fire=False`, skip allies of caster.

**FR-05 (CONE type):** Instant fan from caster position. Geometry: cone_angle degrees (default 90), length = range. All actors within cone receive effects. No travel time.

**FR-06 (BOUNCING type):** Hits primary target, then bounces to nearest unhit actor within range, up to max_bounces times. Each bounce reduces damage by 20% (bounce_decay = 0.8).

**FR-07 (TRAVELING type):** Moves from source toward target along line. All actors within 1 tile of the path receive effects (line AoE, e.g., lightning bolt).

**FR-08 (Friend/Foe):** AoE projectiles check `caster.faction_id` vs `target.faction_id`. If `friendly_fire=False` and factions match, skip target. If `hostile=True` on spell, only affect enemies.

**FR-09 (Flight Tick):** Each world tick, projectile position advances by speed tiles toward target. When distance_remaining <= 0, impact occurs.

**FR-10 (Impact Resolution):** On impact, collect all valid targets (single, AoE, cone, line, bounce). For each target: apply all effect_def_ids via Effect System's `apply_effect()`.

## 4. Data Structures

```python
@dataclass
class ProjectileDef:
    projectile_id: str
    projectile_type: str     # "none" | "arrow" | "fireball" | "cone" | "bouncing" | "traveling"
    speed: float = 5.0       # Tiles per tick
    area_radius: int = 0     # For fireball/AoE, in tiles
    cone_angle: int = 90     # For cone type, in degrees
    max_bounces: int = 0     # For bouncing type
    bounce_decay: float = 0.8
    effect_def_ids: list[str] = field(default_factory=list)
    friendly_fire: bool = True
    hostile: bool = False
    damage_type: str = ""
    flags: list[str] = field(default_factory=list)  # ["trail", "fragment"]

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectileDef": ...


@dataclass
class ProjectileInstance:
    instance_id: str
    projectile_def: ProjectileDef
    caster_id: str
    caster_faction: str
    source_pos: tuple[float, float]
    target_pos: tuple[float, float]
    target_id: str | None = None
    current_pos: tuple[float, float] = (0.0, 0.0)
    tick_created: int = 0
    resolved: bool = False
    targets_hit: list[str] = field(default_factory=list)
    bounces_remaining: int = 0

    def distance_remaining(self) -> float: ...
    def tick_flight(self) -> bool:
        """Advance position by speed. Returns True if arrived."""
        ...
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectileInstance": ...
```

## 5. Public API

```python
def launch_projectile(
    projectile_def: ProjectileDef,
    caster: ActorRecord,
    target_pos: tuple[float, float],
    target_id: str | None,
    current_tick: int,
) -> ProjectileInstance:
    """Create and launch a projectile instance."""

def tick_projectile(
    proj: ProjectileInstance,
) -> bool:
    """Advance projectile by one tick. Returns True if impact occurs."""

def resolve_impact(
    proj: ProjectileInstance,
    actors_in_area: list[ActorRecord],
    effect_registry: dict[str, "EffectDef"],
    current_tick: int,
    rng: Random | None = None,
) -> list[dict]:
    """
    Resolve projectile impact. Collect valid targets based on type.
    Apply effects to each. Returns list of {target_id, effects_applied, resisted}.
    """

def actors_in_cone(
    origin: tuple[float, float],
    direction: tuple[float, float],
    angle: int,
    length: int,
    candidates: list[ActorRecord],
) -> list[ActorRecord]:
    """Filter actors within cone geometry."""

def actors_in_radius(
    center: tuple[float, float],
    radius: int,
    candidates: list[ActorRecord],
) -> list[ActorRecord]:
    """Filter actors within circular radius."""

def actors_along_line(
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
    candidates: list[ActorRecord],
) -> list[ActorRecord]:
    """Filter actors within width tiles of the line."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-02]: Given projectile_type="none", when launched, then effects are applied instantly (no tick_flight needed).

AC-02 [FR-03]: Given an arrow at speed=5 and distance=15, when ticked 3 times, then projectile arrives and impacts single target.

AC-03 [FR-04]: Given a fireball with area_radius=3 arriving at target point with 4 actors (2 allies, 2 enemies) and friendly_fire=False, then only 2 enemies receive effects.

AC-04 [FR-05]: Given a cone with angle=90 and range=5, with 3 actors at various positions, when resolved, then only actors within the 90-degree fan and within 5 tiles receive effects.

AC-05 [FR-06]: Given bouncing projectile with max_bounces=3, when it hits primary target, then it bounces to up to 3 additional targets with 0.8 damage decay per bounce.

AC-06 [FR-07]: Given a traveling projectile from (0,0) to (10,0), with an actor at (5,0.5), then that actor is within the line AoE and receives effects.

AC-07 [FR-08]: Given friendly_fire=True, when AoE resolves, then ALL actors in area receive effects regardless of faction.

AC-08 [FR-09]: Given speed=3 and distance=9, when ticked once, position advances 3 tiles. After 3 ticks, impact occurs.

AC-09 [FR-10]: Given fireball impact with 3 valid targets, each target receives all effect_def_ids from the projectile.

AC-10 [FR-01]: ProjectileDef round-trip via to_dict()/from_dict() preserves all fields.

## 7. Performance Requirements
- launch_projectile: < 0.05 ms
- tick_projectile: < 0.01 ms
- resolve_impact with 20 candidates: < 1 ms
- actors_in_radius/cone/line with 50 candidates: < 0.5 ms

## 8. Error Handling
- Unknown projectile_type: raise ValueError
- AoE with radius=0: treat as single-target
- Bounce with no valid targets: stop bouncing
- Distance=0 (self-target): instant impact

## 9. Integration Points
- **Spell System** (PRD_spell_system_v1): spells create projectiles at PROJECTILE_LAUNCH step
- **Effect System** (PRD_effect_system_v1): impact applies effects via apply_effect()
- **Combat Resolution**: ranged weapon attacks use arrow-type projectiles
- **Actor Kernel**: actor positions for geometry checks

## 10. Test Coverage Target
- All 6 projectile types with dedicated tests
- AoE friend/foe filtering with mixed factions
- Cone geometry edge cases (0°, 180°, actors on boundary)
- Bounce chain with max_bounces boundary
- Line AoE with actors at various perpendicular distances
- Flight tick timing: exact tick count for arrival
- Serialization round-trip

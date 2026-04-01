from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, dist, hypot, radians
from random import Random
from typing import Any

from engine.kernel.actor import ActorRecord
from engine.kernel.common import serialize_value
from engine.kernel.effects import EffectDef, apply_effect


_INSTANT_TYPES = {"none", "cone"}


@dataclass
class ProjectileDef:
    projectile_id: str
    projectile_type: str
    speed: float = 5.0
    area_radius: int = 0
    cone_angle: int = 90
    max_bounces: int = 0
    bounce_decay: float = 0.8
    effect_def_ids: list[str] = field(default_factory=list)
    friendly_fire: bool = True
    hostile: bool = False
    damage_type: str = ""
    flags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        projectile_type = str(self.projectile_type).lower()
        if projectile_type not in {"none", "arrow", "fireball", "cone", "bouncing", "traveling"}:
            raise ValueError(f"Unknown projectile_type: {self.projectile_type}")
        self.projectile_type = projectile_type
        self.speed = float(self.speed)
        self.area_radius = int(self.area_radius)
        self.cone_angle = int(self.cone_angle)
        self.max_bounces = int(self.max_bounces)
        self.bounce_decay = float(self.bounce_decay)
        self.effect_def_ids = [str(effect_id) for effect_id in self.effect_def_ids]
        self.flags = [str(flag) for flag in self.flags]

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectileDef":
        return cls(**data)


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

    def distance_remaining(self) -> float:
        return dist(self.current_pos, self.target_pos)

    def tick_flight(self) -> bool:
        if self.resolved:
            return True
        if self.projectile_def.projectile_type in _INSTANT_TYPES:
            self.current_pos = self.target_pos
            return True
        remaining = self.distance_remaining()
        if remaining <= 0:
            self.current_pos = self.target_pos
            return True
        step = self.projectile_def.speed
        if step <= 0:
            self.current_pos = self.target_pos
            return True
        if step >= remaining:
            self.current_pos = self.target_pos
            return True
        dx = self.target_pos[0] - self.current_pos[0]
        dy = self.target_pos[1] - self.current_pos[1]
        scale = step / remaining
        self.current_pos = (
            self.current_pos[0] + (dx * scale),
            self.current_pos[1] + (dy * scale),
        )
        return False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectileInstance":
        payload = dict(data)
        payload["projectile_def"] = ProjectileDef.from_dict(payload["projectile_def"])
        payload["source_pos"] = tuple(float(value) for value in payload.get("source_pos", (0.0, 0.0)))
        payload["target_pos"] = tuple(float(value) for value in payload.get("target_pos", (0.0, 0.0)))
        payload["current_pos"] = tuple(float(value) for value in payload.get("current_pos", (0.0, 0.0)))
        payload["targets_hit"] = [str(actor_id) for actor_id in payload.get("targets_hit", [])]
        return cls(**payload)


def launch_projectile(
    projectile_def: ProjectileDef,
    caster: ActorRecord,
    target_pos: tuple[float, float],
    target_id: str | None,
    current_tick: int,
) -> ProjectileInstance:
    source_pos = _actor_pos(caster)
    normalized_target = (float(target_pos[0]), float(target_pos[1]))
    instance = ProjectileInstance(
        instance_id=f"{projectile_def.projectile_id}:{caster.identity.actor_id}:{current_tick}",
        projectile_def=projectile_def,
        caster_id=caster.identity.actor_id,
        caster_faction=str(caster.identity.faction_id or ""),
        source_pos=source_pos,
        target_pos=normalized_target,
        target_id=target_id,
        current_pos=source_pos,
        tick_created=int(current_tick),
        bounces_remaining=max(0, int(projectile_def.max_bounces)),
    )
    if projectile_def.projectile_type in _INSTANT_TYPES or dist(source_pos, normalized_target) <= 0:
        instance.current_pos = normalized_target
    return instance


def tick_projectile(proj: ProjectileInstance) -> bool:
    arrived = proj.tick_flight()
    return arrived


def resolve_impact(
    proj: ProjectileInstance,
    actors_in_area: list[ActorRecord],
    effect_registry: dict[str, EffectDef],
    current_tick: int,
    rng: Random | None = None,
) -> list[dict[str, Any]]:
    if proj.resolved:
        return []
    if proj.projectile_def.projectile_type == "none":
        if proj.target_id is not None:
            targets = [actor for actor in actors_in_area if actor.identity.actor_id == proj.target_id]
        else:
            targets = actors_in_area[:1]
        events = _apply_to_targets(proj, targets, effect_registry, current_tick, rng)
        proj.resolved = True
        return events

    if proj.projectile_def.projectile_type == "arrow":
        targets = [actor for actor in actors_in_area if actor.identity.actor_id == proj.target_id]
        events = _apply_to_targets(proj, _filter_targets(proj, targets), effect_registry, current_tick, rng)
        proj.resolved = True
        return events

    if proj.projectile_def.projectile_type == "fireball":
        targets = actors_in_area
        if proj.projectile_def.area_radius > 0:
            targets = actors_in_radius(proj.target_pos, proj.projectile_def.area_radius, actors_in_area)
        else:
            targets = [actor for actor in actors_in_area if actor.identity.actor_id == proj.target_id]
        events = _apply_to_targets(proj, _filter_targets(proj, targets), effect_registry, current_tick, rng)
        proj.resolved = True
        return events

    if proj.projectile_def.projectile_type == "cone":
        targets = actors_in_cone(
            proj.source_pos,
            proj.target_pos,
            proj.projectile_def.cone_angle,
            max(1, int(round(dist(proj.source_pos, proj.target_pos)))),
            actors_in_area,
        )
        events = _apply_to_targets(proj, _filter_targets(proj, targets), effect_registry, current_tick, rng)
        proj.resolved = True
        return events

    if proj.projectile_def.projectile_type == "traveling":
        targets = actors_along_line(proj.source_pos, proj.target_pos, 1.0, actors_in_area)
        events = _apply_to_targets(proj, _filter_targets(proj, targets), effect_registry, current_tick, rng)
        proj.resolved = True
        return events

    if proj.projectile_def.projectile_type == "bouncing":
        events = _resolve_bouncing(proj, actors_in_area, effect_registry, current_tick, rng)
        proj.resolved = True
        return events

    raise ValueError(f"Unknown projectile_type: {proj.projectile_def.projectile_type}")


def actors_in_cone(
    origin: tuple[float, float],
    direction: tuple[float, float],
    angle: int,
    length: int,
    candidates: list[ActorRecord],
) -> list[ActorRecord]:
    ox, oy = float(origin[0]), float(origin[1])
    dx, dy = float(direction[0]) - ox, float(direction[1]) - oy
    direction_mag = hypot(dx, dy)
    if direction_mag == 0:
        return []
    cos_threshold = _cosine_threshold(int(angle) / 2.0)
    hits: list[ActorRecord] = []
    for candidate in candidates:
        px, py = _actor_pos(candidate)
        vx, vy = px - ox, py - oy
        distance_to_actor = hypot(vx, vy)
        if distance_to_actor == 0 or distance_to_actor > float(length):
            continue
        dot = ((vx * dx) + (vy * dy)) / (distance_to_actor * direction_mag)
        if dot >= cos_threshold:
            hits.append(candidate)
    return hits


def actors_in_radius(
    center: tuple[float, float],
    radius: int,
    candidates: list[ActorRecord],
) -> list[ActorRecord]:
    cx, cy = float(center[0]), float(center[1])
    threshold = float(radius)
    return [
        candidate
        for candidate in candidates
        if dist((cx, cy), _actor_pos(candidate)) <= threshold
    ]


def actors_along_line(
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
    candidates: list[ActorRecord],
) -> list[ActorRecord]:
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    line_dx = ex - sx
    line_dy = ey - sy
    line_len_sq = (line_dx * line_dx) + (line_dy * line_dy)
    if line_len_sq == 0:
        return []
    hits: list[ActorRecord] = []
    for candidate in candidates:
        px, py = _actor_pos(candidate)
        projection = (((px - sx) * line_dx) + ((py - sy) * line_dy)) / line_len_sq
        if projection < 0 or projection > 1:
            continue
        closest = (sx + (projection * line_dx), sy + (projection * line_dy))
        if dist((px, py), closest) <= float(width):
            hits.append(candidate)
    return hits


def _resolve_bouncing(
    proj: ProjectileInstance,
    actors_in_area: list[ActorRecord],
    effect_registry: dict[str, EffectDef],
    current_tick: int,
    rng: Random | None,
) -> list[dict[str, Any]]:
    all_candidates = _filter_targets(proj, actors_in_area)
    if proj.target_id is not None:
        ordered_targets = [actor for actor in all_candidates if actor.identity.actor_id == proj.target_id]
    else:
        ordered_targets = []
    if not ordered_targets:
        ordered_targets = _nearest_targets(proj.source_pos, all_candidates)
    if not ordered_targets:
        return []

    events: list[dict[str, Any]] = []
    primary = ordered_targets[0]
    remaining = [
        actor
        for actor in all_candidates
        if actor.identity.actor_id != primary.identity.actor_id
    ]
    bounce_targets = [primary]
    origin = _actor_pos(primary)
    while proj.bounces_remaining > 0:
        nearest = _nearest_targets(origin, remaining)
        if not nearest:
            break
        next_target = nearest[0]
        bounce_targets.append(next_target)
        remaining = [
            actor
            for actor in remaining
            if actor.identity.actor_id != next_target.identity.actor_id
        ]
        origin = _actor_pos(next_target)
        proj.bounces_remaining -= 1

    decay = 1.0
    for target in bounce_targets:
        event = _apply_to_single_target(proj, target, effect_registry, current_tick, rng)
        event["decay_factor"] = round(decay, 12)
        events.append(event)
        decay *= proj.projectile_def.bounce_decay
    return events


def _apply_to_targets(
    proj: ProjectileInstance,
    targets: list[ActorRecord],
    effect_registry: dict[str, EffectDef],
    current_tick: int,
    rng: Random | None,
) -> list[dict[str, Any]]:
    return [
        _apply_to_single_target(proj, target, effect_registry, current_tick, rng)
        for target in targets
    ]


def _apply_to_single_target(
    proj: ProjectileInstance,
    target: ActorRecord,
    effect_registry: dict[str, EffectDef],
    current_tick: int,
    rng: Random | None,
) -> dict[str, Any]:
    applied: list[str] = []
    resisted: list[str] = []
    for effect_id in proj.projectile_def.effect_def_ids:
        effect_def = effect_registry.get(effect_id)
        if effect_def is None:
            continue
        success, _ = apply_effect(
            target,
            effect_def,
            proj.caster_id,
            current_tick=current_tick,
            rng=rng,
        )
        if success:
            applied.append(effect_id)
        else:
            resisted.append(effect_id)
    proj.targets_hit.append(target.identity.actor_id)
    return {
        "target_id": target.identity.actor_id,
        "effects_applied": applied,
        "resisted": resisted,
    }


def _filter_targets(proj: ProjectileInstance, candidates: list[ActorRecord]) -> list[ActorRecord]:
    caster_faction = proj.caster_faction
    filtered: list[ActorRecord] = []
    for candidate in candidates:
        actor_id = candidate.identity.actor_id
        if actor_id == proj.caster_id and not proj.projectile_def.friendly_fire:
            continue
        same_faction = caster_faction != "" and candidate.identity.faction_id == caster_faction
        if proj.projectile_def.hostile and same_faction:
            continue
        if not proj.projectile_def.friendly_fire and same_faction:
            continue
        filtered.append(candidate)
    return filtered


def _nearest_targets(origin: tuple[float, float], candidates: list[ActorRecord]) -> list[ActorRecord]:
    return sorted(
        candidates,
        key=lambda candidate: (dist(origin, _actor_pos(candidate)), candidate.identity.actor_id),
    )


def _actor_pos(actor: ActorRecord) -> tuple[float, float]:
    raw_pos = actor.raw_payload.get("pos_float")
    if isinstance(raw_pos, (list, tuple)) and len(raw_pos) >= 2:
        return float(raw_pos[0]), float(raw_pos[1])
    return float(actor.position.x), float(actor.position.y)


def _cosine_threshold(half_angle_degrees: float) -> float:
    if half_angle_degrees <= 0:
        return 1.0
    if half_angle_degrees >= 180:
        return -1.0
    return float(cos(radians(half_angle_degrees)))

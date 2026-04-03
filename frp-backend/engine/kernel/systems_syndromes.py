from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from random import Random
from typing import Any

from engine.kernel.actor import ActorRecord, ConditionRecord
from engine.kernel.common import serialize_value


@dataclass
class SyndromeEffect:
    effect_id: str
    effect_type: str
    severity: int
    target: str | None = None
    start_tick: int = 0
    end_tick: int = -1
    tick_counter: int = 0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyndromeEffect":
        return cls(**data)


@dataclass
class SyndromeDef:
    syndrome_id: str
    name: str
    delivery: str
    resistance_dc: int = 10
    contagious: bool = False
    contagion_probability: float = 0.05
    effects: list[SyndromeEffect] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyndromeDef":
        payload = dict(data)
        payload["effects"] = [
            item if isinstance(item, SyndromeEffect) else SyndromeEffect.from_dict(dict(item))
            for item in payload.get("effects", [])
        ]
        return cls(**payload)


def syndrome_registry_from_actors(actors: list[ActorRecord]) -> list[SyndromeDef]:
    registry: list[SyndromeDef] = []
    seen: set[str] = set()
    for actor in actors:
        for payload in actor.raw_payload.get("active_syndromes", []):
            syndrome_id = str(payload.get("syndrome_id", ""))
            if not syndrome_id or syndrome_id in seen:
                continue
            seen.add(syndrome_id)
            registry.append(
                SyndromeDef(
                    syndrome_id=syndrome_id,
                    name=str(payload.get("name", syndrome_id)),
                    delivery=str(payload.get("delivery", "contact")),
                    resistance_dc=int(payload.get("resistance_dc", 10)),
                    contagious=bool(payload.get("contagious", False)),
                    contagion_probability=float(payload.get("contagion_probability", 0.0)),
                    effects=[
                        item if isinstance(item, SyndromeEffect) else SyndromeEffect.from_dict(dict(item))
                        for item in payload.get("effects", [])
                    ],
                )
            )
        for condition in actor.conditions:
            if isinstance(condition, str):
                cond_id = condition
                cond_name = condition
            else:
                cond_id = condition.condition_id
                cond_name = condition.name
            syndrome_id = f"condition::{cond_id}"
            if syndrome_id in seen:
                continue
            seen.add(syndrome_id)
            cond_severity = int(getattr(condition, "severity", 1)) if not isinstance(condition, str) else 1
            registry.append(
                SyndromeDef(
                    syndrome_id=syndrome_id,
                    name=cond_name,
                    delivery="contact",
                    effects=[
                        SyndromeEffect(
                            effect_id=f"{cond_id}::severity",
                            effect_type=cond_name,
                            severity=cond_severity,
                            target="actor",
                        )
                    ],
                )
            )
        if actor.body_state is None:
            continue
        for condition in actor.body_state.conditions:
            if isinstance(condition, str):
                bc_id, bc_name, bc_sev = condition, condition, 1
            else:
                bc_id = condition.condition_id
                bc_name = condition.name
                bc_sev = int(condition.severity)
            syndrome_id = f"body_condition::{bc_id}"
            if syndrome_id in seen:
                continue
            seen.add(syndrome_id)
            registry.append(
                SyndromeDef(
                    syndrome_id=syndrome_id,
                    name=bc_name,
                    delivery="body_state",
                    effects=[
                        SyndromeEffect(
                            effect_id=f"{bc_id}::severity",
                            effect_type=bc_name,
                            severity=bc_sev,
                            target="body",
                        )
                    ],
                )
            )
    return registry


def apply_syndrome(actor: ActorRecord, syndrome: SyndromeDef, seed: int) -> bool:
    disease_resistance = int(actor.stats.get("disease_resistance", 0))
    toughness = int(actor.stats.get("END", 10))
    d20 = resolve_d20(seed)
    resistance_total = d20 + disease_resistance + (toughness // 2)
    if resistance_total >= int(syndrome.resistance_dc):
        return False
    actor.raw_payload.setdefault("active_syndromes", []).append(
        {
            "syndrome_id": syndrome.syndrome_id,
            "name": syndrome.name,
            "delivery": syndrome.delivery,
            "contagious": syndrome.contagious,
            "contagion_probability": syndrome.contagion_probability,
            "effects": [effect.to_dict() for effect in syndrome.effects],
        }
    )
    return True


def tick_syndromes(actor: ActorRecord) -> list[str]:
    active = list(actor.raw_payload.get("active_syndromes", []))
    kept: list[dict[str, Any]] = []
    events: list[str] = []
    for syndrome in active:
        effects = list(syndrome.get("effects", []))
        kept_effects: list[dict[str, Any]] = []
        for effect in effects:
            tick_counter = int(effect.get("tick_counter", 0))
            start_tick = int(effect.get("start_tick", 0))
            end_tick = int(effect.get("end_tick", -1))
            if tick_counter >= start_tick and (end_tick == -1 or tick_counter <= end_tick):
                apply_syndrome_effect(actor, effect)
                events.append(str(effect.get("effect_type", "unknown")))
            tick_counter += 1
            effect["tick_counter"] = tick_counter
            if end_tick == -1 or tick_counter <= end_tick:
                kept_effects.append(effect)
        if kept_effects:
            syndrome["effects"] = kept_effects
            kept.append(syndrome)
    actor.raw_payload["active_syndromes"] = kept
    return events


def spread_contagion(actors: list[ActorRecord], region_tiles: dict) -> list[tuple[str, str]]:
    del region_tiles
    infections: list[tuple[str, str]] = []
    for source in actors:
        for syndrome in source.raw_payload.get("active_syndromes", []):
            if not bool(syndrome.get("contagious", False)):
                continue
            probability = float(syndrome.get("contagion_probability", 0.0))
            for target in actors:
                if target.identity.actor_id == source.identity.actor_id:
                    continue
                if abs(target.position.x - source.position.x) + abs(target.position.y - source.position.y) > 1:
                    continue
                if has_active_syndrome(target, str(syndrome.get("syndrome_id", ""))):
                    continue
                if deterministic_probability(source.identity.actor_id, target.identity.actor_id) <= probability:
                    target.raw_payload.setdefault("active_syndromes", []).append(
                        {
                            "syndrome_id": syndrome["syndrome_id"],
                            "name": syndrome["name"],
                            "delivery": syndrome["delivery"],
                            "contagious": syndrome.get("contagious", False),
                            "contagion_probability": syndrome.get("contagion_probability", 0.0),
                            "effects": [dict(effect) for effect in syndrome.get("effects", [])],
                        }
                    )
                    infections.append((source.identity.actor_id, target.identity.actor_id))
    return infections


def apply_syndrome_effect(actor: ActorRecord, effect: dict[str, Any]) -> None:
    effect_type = str(effect.get("effect_type", ""))
    severity = int(effect.get("severity", 0))
    if effect_type == "CE_PAIN":
        actor.raw_payload["pain"] = int(actor.raw_payload.get("pain", 0)) + severity
    elif effect_type == "CE_BLEEDING":
        actor.stats["blood_loss"] = int(actor.stats.get("blood_loss", 0)) + severity
    elif effect_type == "CE_PARALYSIS":
        actor.conditions.append(ConditionRecord(condition_id="paralysis", name="paralyzed", severity=severity))
    elif effect_type == "CE_NAUSEA":
        actor.conditions.append(ConditionRecord(condition_id="nausea", name="nausea", severity=severity))
    elif effect_type == "CE_FEVER":
        actor.raw_payload["fever"] = int(actor.raw_payload.get("fever", 0)) + severity
    elif effect_type == "CE_NUMBNESS":
        actor.raw_payload["numbness"] = int(actor.raw_payload.get("numbness", 0)) + severity
    elif effect_type == "CE_UNCONSCIOUSNESS":
        actor.conditions.append(ConditionRecord(condition_id="unconscious", name="unconscious", severity=severity))
    elif effect_type == "CE_NECROSIS":
        actor.conditions.append(ConditionRecord(condition_id="necrosis", name="necrosis", severity=severity))
    elif effect_type == "CE_PERSONALITY_CHANGE":
        actor.raw_payload["personality_shift"] = int(actor.raw_payload.get("personality_shift", 0)) + severity
    elif effect_type == "CE_SPEED_CHANGE":
        actor.raw_payload["speed_penalty"] = int(actor.raw_payload.get("speed_penalty", 0)) + severity
    elif effect_type == "CE_STAT_CHANGE":
        actor.stats["syndrome_stat_delta"] = int(actor.stats.get("syndrome_stat_delta", 0)) + severity


def has_active_syndrome(actor: ActorRecord, syndrome_id: str) -> bool:
    return any(entry.get("syndrome_id") == syndrome_id for entry in actor.raw_payload.get("active_syndromes", []))


def deterministic_probability(source_id: str, target_id: str) -> float:
    digest = hashlib.sha256(f"{source_id}->{target_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF


def resolve_d20(seed: int) -> int:
    if 1 <= int(seed) <= 20:
        return int(seed)
    return Random(int(seed)).randint(1, 20)


__all__ = [
    "SyndromeDef",
    "SyndromeEffect",
    "apply_syndrome",
    "spread_contagion",
    "syndrome_registry_from_actors",
    "tick_syndromes",
]

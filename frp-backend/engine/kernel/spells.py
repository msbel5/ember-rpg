from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord
from engine.kernel.common import serialize_value
from engine.kernel.effects import apply_effect


@dataclass
class SpellDef:
    spell_id: str
    label: str
    spell_type: str
    school: str
    level: int
    casting_time: int
    range: int
    target_type: str
    area_radius: int = 0
    hostile: bool = False
    effect_def_ids: list[str] = field(default_factory=list)
    projectile_type: str = "none"
    components: list[str] = field(default_factory=list)
    material_cost: dict[str, int] = field(default_factory=dict)
    scaling_stat: str = ""
    scaling_formula: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpellDef":
        payload = dict(data)
        payload["effect_def_ids"] = [str(item) for item in payload.get("effect_def_ids", [])]
        payload["components"] = [str(item) for item in payload.get("components", [])]
        payload["material_cost"] = {str(key): int(value) for key, value in payload.get("material_cost", {}).items()}
        payload["tags"] = [str(item) for item in payload.get("tags", [])]
        return cls(**payload)


@dataclass
class SpellSlot:
    spell_level: int
    spell_id: str | None = None
    memorized: bool = False
    expended: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpellSlot":
        return cls(**data)


@dataclass
class Spellbook:
    actor_id: str
    spell_type: str
    known_spells: dict[int, list[str]] = field(default_factory=dict)
    slots: dict[int, list[SpellSlot]] = field(default_factory=dict)
    max_slots: dict[int, int] = field(default_factory=dict)

    def available_slots(self, level: int) -> int:
        return sum(1 for slot in self.slots.get(level, []) if slot.memorized and not slot.expended)

    def memorize(self, spell_id: str, level: int) -> bool:
        if self.spell_type == "sorcerer":
            return False
        for slot in self.slots.setdefault(level, []):
            if slot.spell_id is None:
                slot.spell_id = spell_id
                slot.memorized = True
                slot.expended = False
                return True
        return False

    def expend_slot(self, spell_id: str, level: int) -> bool:
        for slot in self.slots.get(level, []):
            if slot.spell_id == spell_id and slot.memorized and not slot.expended:
                slot.expended = True
                return True
        return False

    def rest_refresh(self) -> None:
        for slots in self.slots.values():
            for slot in slots:
                slot.expended = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Spellbook":
        payload = dict(data)
        payload["known_spells"] = {
            int(level): [str(spell_id) for spell_id in spell_ids]
            for level, spell_ids in payload.get("known_spells", {}).items()
        }
        payload["slots"] = {
            int(level): [SpellSlot.from_dict(slot) for slot in slots]
            for level, slots in payload.get("slots", {}).items()
        }
        payload["max_slots"] = {int(level): int(count) for level, count in payload.get("max_slots", {}).items()}
        return cls(**payload)


@dataclass
class CastingAttempt:
    caster_id: str
    spell_def: SpellDef
    target_id: str | None = None
    target_point: tuple[int, int] | None = None
    tick_started: int = 0
    ticks_remaining: int = 0
    interrupted: bool = False
    failed: bool = False
    failure_reason: str = ""
    completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CastingAttempt":
        payload = dict(data)
        payload["spell_def"] = SpellDef.from_dict(payload["spell_def"])
        return cls(**payload)


def compute_max_spell_slots(
    actor: ActorRecord,
    spell_type: str,
    class_table: dict[str, dict[int, dict[int, int]]],
) -> dict[int, int]:
    spell_kind = str(spell_type).lower()
    table = class_table.get(spell_kind)
    if table is None:
        raise ValueError(f"Unknown spell_type `{spell_type}`")
    level = int(actor.raw_payload.get("level", 1))
    class_slots = dict(table.get(level, {}))
    ability_score = _spell_ability_score(actor, spell_kind)
    result: dict[int, int] = {}
    for spell_level, base_count in class_slots.items():
        result[int(spell_level)] = int(base_count) + _bonus_slots(ability_score, int(spell_level))
    return result


def learn_spell(
    actor: ActorRecord,
    spellbook: Spellbook,
    spell_def: SpellDef,
    d100_roll: int,
) -> tuple[bool, str]:
    intelligence = int(actor.stats.get("INT", actor.stats.get("MND", 10)))
    chance = _learn_chance(intelligence)
    if int(d100_roll) <= chance:
        spellbook.known_spells.setdefault(spell_def.level, [])
        if spell_def.spell_id not in spellbook.known_spells[spell_def.level]:
            spellbook.known_spells[spell_def.level].append(spell_def.spell_id)
        return True, "learned"
    return False, "learning failed; scroll consumed"


def begin_casting(
    caster: ActorRecord,
    spellbook: Spellbook,
    spell_def: SpellDef,
    target_id: str | None,
    target_point: tuple[int, int] | None,
    current_tick: int,
) -> tuple[bool, CastingAttempt | None, str]:
    if int(current_tick) - int(caster.raw_payload.get("last_cast_tick", -999)) < 6:
        return False, None, "aura cooldown"
    if not _target_valid(spell_def, target_id, target_point):
        return False, None, "invalid target"
    if spell_def.spell_type in {"wizard", "priest"} and spellbook.available_slots(spell_def.level) <= 0:
        return False, None, "no available slot"
    attempt = CastingAttempt(
        caster_id=caster.identity.actor_id,
        spell_def=spell_def,
        target_id=target_id,
        target_point=target_point,
        tick_started=int(current_tick),
        ticks_remaining=int(spell_def.casting_time),
    )
    return True, attempt, ""


def tick_casting(
    attempt: CastingAttempt,
    damage_taken: int,
    d20_roll: int | None,
    d100_roll: int | None,
    caster: ActorRecord,
) -> tuple[str, CastingAttempt]:
    if attempt.failed:
        return "failed", attempt
    if damage_taken > 0:
        concentration_total = int(d20_roll or 1) + _ability_modifier(int(caster.stats.get("CON", caster.stats.get("END", 10))))
        if concentration_total < 10 + int(damage_taken):
            attempt.interrupted = True
            attempt.failed = True
            attempt.failure_reason = "interrupted"
            return "interrupted", attempt
    spell_failure = int(caster.raw_payload.get("spell_failure", 0))
    if spell_failure > 0 and int(d100_roll or 100) <= spell_failure:
        attempt.failed = True
        attempt.failure_reason = "spell failure"
        return "failed", attempt
    attempt.ticks_remaining = max(0, attempt.ticks_remaining - 1)
    if attempt.ticks_remaining == 0:
        attempt.completed = True
        return "ready", attempt
    return "casting", attempt


def resolve_cast(
    attempt: CastingAttempt,
    caster: ActorRecord,
    target: ActorRecord | None,
    d100_roll: int,
    current_tick: int,
) -> dict[str, Any]:
    recipient = target or caster
    resisted = int(d100_roll) <= int(recipient.stats.get("magic_resistance", 0))
    caster.raw_payload["last_cast_tick"] = int(current_tick)
    if resisted:
        return {"resisted": True, "projectile_launched": False, "effects_applied": [], "slot_expended": True}
    registry = dict(caster.raw_payload.get("effect_registry", {}))
    applied: list[str] = []
    projectile_launched = attempt.spell_def.projectile_type != "none"
    for effect_id in attempt.spell_def.effect_def_ids:
        effect_def = registry.get(effect_id)
        if effect_def is None:
            continue
        used, instance = apply_effect(recipient, effect_def, source_id=attempt.spell_def.spell_id, current_tick=int(current_tick))
        if effect_def.category == "healing" and effect_def.timing_mode == "instant" and effect_def.healing_per_tick > 0:
            recipient.stats["hp"] = min(
                int(recipient.stats.get("max_hp", recipient.stats.get("hp", 0))),
                int(recipient.stats.get("hp", 0)) + int(effect_def.healing_per_tick),
            )
            if recipient.effect_queue is not None and instance is not None:
                recipient.effect_queue.instances = [
                    current for current in recipient.effect_queue.instances if current.instance_id != instance.instance_id
                ]
                recipient.effect_queue.rebuild_condition_cache()
        if used:
            applied.append(effect_id)
    return {"resisted": False, "projectile_launched": projectile_launched, "effects_applied": applied, "slot_expended": True}


def rest_refresh_spellbook(spellbook: Spellbook) -> None:
    spellbook.rest_refresh()


def _spell_ability_score(actor: ActorRecord, spell_type: str) -> int:
    if spell_type == "wizard":
        return int(actor.stats.get("INT", actor.stats.get("MND", 10)))
    if spell_type == "priest":
        return int(actor.stats.get("WIS", actor.stats.get("INS", 10)))
    if spell_type == "sorcerer":
        return int(actor.stats.get("CHA", actor.stats.get("PRE", 10)))
    return 10


def _bonus_slots(ability_score: int, spell_level: int) -> int:
    allowance = max(0, (int(ability_score) - 10) // 4)
    if spell_level > allowance:
        return 0
    return max(0, allowance - spell_level + 1)


def _learn_chance(intelligence: int) -> int:
    table = [
        (20, 99),
        (19, 95),
        (18, 85),
        (16, 70),
        (14, 60),
        (12, 50),
        (10, 40),
        (9, 35),
    ]
    for threshold, chance in table:
        if intelligence >= threshold:
            return chance
    return 25


def _target_valid(spell_def: SpellDef, target_id: str | None, target_point: tuple[int, int] | None) -> bool:
    if spell_def.target_type == "self":
        return True
    if spell_def.target_type == "creature":
        return bool(target_id)
    if spell_def.target_type in {"point", "area"}:
        return target_point is not None
    raise ValueError(f"Unknown target_type `{spell_def.target_type}`")


def _ability_modifier(value: int) -> int:
    return (int(value) - 10) // 2

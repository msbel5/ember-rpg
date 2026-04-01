from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Any

from engine.kernel.actor import ActorRecord, ConditionRecord, WoundRecord
from engine.kernel.common import serialize_value


SAVE_STAT_MAP = {
    "fortitude": ("CON", "constitution"),
    "reflex": ("DEX", "dexterity"),
    "will": ("WIS", "wisdom"),
}


@dataclass
class EffectDef:
    effect_def_id: str
    label: str
    category: str
    target_stat: str = ""
    modifier_type: str = "flat"
    modifier_value: float = 0.0
    damage_per_tick: int = 0
    damage_type: str = ""
    condition_flag: str = ""
    healing_per_tick: int = 0
    timing_mode: str = "duration"
    base_duration_ticks: int = 0
    max_stacks: int = 1
    saving_throw_type: str = "none"
    saving_throw_dc: int = 0
    delivery: str = "direct"
    resistance_stat: str = ""
    resistance_dc: int = 0
    tags: list[str] = field(default_factory=list)
    source_type: str = ""
    dispellable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EffectDef":
        payload = dict(data)
        payload["tags"] = [str(item) for item in payload.get("tags", [])]
        return cls(**payload)


@dataclass
class EffectInstance:
    instance_id: str
    effect_def_id: str
    effect_def: EffectDef
    source_id: str
    target_id: str
    ticks_remaining: int = 0
    current_stacks: int = 1
    saved: bool = False
    tick_applied: int = 0

    def is_expired(self) -> bool:
        if self.ticks_remaining == -1:
            return False
        return self.ticks_remaining <= 0

    def tick(self) -> None:
        if self.ticks_remaining > 0:
            self.ticks_remaining -= 1

    def effective_modifier_value(self) -> float:
        if self.saved and self.effect_def.category == "stat_mod":
            return self.effect_def.modifier_value / 2.0
        return self.effect_def.modifier_value

    def effective_damage_per_tick(self) -> int:
        damage = int(self.effect_def.damage_per_tick)
        if self.saved and self.effect_def.category == "dot":
            return damage // 2
        return damage

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        registry: dict[str, EffectDef] | None = None,
    ) -> "EffectInstance":
        payload = dict(data)
        effect_def_id = str(payload["effect_def_id"])
        effect_def = None
        if registry is not None:
            effect_def = registry.get(effect_def_id)
        if effect_def is None:
            raw_def = payload.get("effect_def", {})
            effect_def = EffectDef.from_dict(raw_def)
        payload["effect_def"] = effect_def
        return cls(**payload)


@dataclass
class EffectQueue:
    actor_id: str
    instances: list[EffectInstance] = field(default_factory=list)
    _active_conditions: set[str] = field(default_factory=set, repr=False)

    def add(self, instance: EffectInstance) -> None:
        matching = [
            current
            for current in self.instances
            if current.effect_def_id == instance.effect_def_id
        ]
        same_source = next((current for current in matching if current.source_id == instance.source_id), None)
        if same_source is not None:
            same_source.ticks_remaining = instance.ticks_remaining
            same_source.saved = instance.saved
            same_source.tick_applied = instance.tick_applied
            same_source.effect_def = instance.effect_def
            self.rebuild_condition_cache()
            return
        max_stacks = max(1, int(instance.effect_def.max_stacks or 1))
        if len(matching) >= max_stacks:
            oldest = min(matching, key=lambda current: current.tick_applied)
            replace_index = self.instances.index(oldest)
            self.instances[replace_index] = instance
            self.rebuild_condition_cache()
            return
        self.instances.append(instance)
        self.rebuild_condition_cache()

    def remove(self, instance_id: str) -> None:
        self.instances = [instance for instance in self.instances if instance.instance_id != instance_id]
        self.rebuild_condition_cache()

    def tick_all(self, actor: ActorRecord, current_tick: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        equipped_item_ids = _equipped_item_ids(actor)
        expired_ids: list[str] = []
        for instance in list(self.instances):
            effect = instance.effect_def
            if effect.timing_mode == "while_equipped" and instance.source_id not in equipped_item_ids:
                expired_ids.append(instance.instance_id)
                events.append({"type": "effect_removed", "effect_id": effect.effect_def_id, "reason": "unequipped"})
                continue
            if effect.category == "dot":
                damage = instance.effective_damage_per_tick()
                if damage > 0 and actor.body_state is not None:
                    wound = _build_dot_wound(actor, effect, damage, current_tick)
                    actor.body_state.apply_wound(wound)
                    events.append({"type": "dot_damage", "effect_id": effect.effect_def_id, "damage": damage})
            elif effect.category == "healing":
                healing = max(0, int(effect.healing_per_tick))
                if healing > 0:
                    actor.stats["hp"] = min(
                        int(actor.stats.get("max_hp", actor.stats.get("hp", 0))),
                        int(actor.stats.get("hp", 0)) + healing,
                    )
                    events.append({"type": "healing", "effect_id": effect.effect_def_id, "amount": healing})
            instance.tick()
            if instance.is_expired():
                expired_ids.append(instance.instance_id)
                events.append({"type": "effect_expired", "effect_id": effect.effect_def_id, "tick": current_tick})
        if expired_ids:
            expired_set = set(expired_ids)
            self.instances = [instance for instance in self.instances if instance.instance_id not in expired_set]
        self.rebuild_condition_cache()
        _sync_actor_condition_state(actor)
        return events

    def compute_stat_modifier(self, stat_name: str) -> tuple[float, float, float | None]:
        flat_total = 0.0
        pct_total = 0.0
        set_override: float | None = None
        for instance in self.instances:
            effect = instance.effect_def
            if effect.category != "stat_mod":
                continue
            if effect.target_stat != stat_name:
                continue
            value = instance.effective_modifier_value()
            if effect.modifier_type == "percentage":
                pct_total += value
            elif effect.modifier_type == "set":
                set_override = value
            else:
                flat_total += value
        return flat_total, pct_total, set_override

    def has_condition(self, flag: str) -> bool:
        return str(flag) in self._active_conditions

    def active_conditions(self) -> set[str]:
        return set(self._active_conditions)

    def dispel_by_category(self, category: str) -> list[EffectInstance]:
        removed = [instance for instance in self.instances if instance.effect_def.category == category]
        self.instances = [instance for instance in self.instances if instance.effect_def.category != category]
        self.rebuild_condition_cache()
        return removed

    def dispel_by_tag(self, tag: str) -> list[EffectInstance]:
        removed = [instance for instance in self.instances if tag in instance.effect_def.tags]
        self.instances = [instance for instance in self.instances if tag not in instance.effect_def.tags]
        self.rebuild_condition_cache()
        return removed

    def dispel_by_id(self, effect_def_id: str) -> list[EffectInstance]:
        removed = [instance for instance in self.instances if instance.effect_def_id == effect_def_id]
        self.instances = [instance for instance in self.instances if instance.effect_def_id != effect_def_id]
        self.rebuild_condition_cache()
        return removed

    def rebuild_condition_cache(self) -> None:
        self._active_conditions = {
            instance.effect_def.condition_flag
            for instance in self.instances
            if instance.effect_def.category == "condition" and instance.effect_def.condition_flag
        }

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        registry: dict[str, EffectDef] | None = None,
    ) -> "EffectQueue":
        payload = dict(data)
        payload["instances"] = [
            EffectInstance.from_dict(item, registry) for item in payload.get("instances", [])
        ]
        queue = cls(actor_id=str(payload["actor_id"]), instances=payload["instances"])
        queue.rebuild_condition_cache()
        return queue


def apply_effect(
    target: ActorRecord,
    effect_def: EffectDef,
    source_id: str,
    *,
    current_tick: int = 0,
    d20_roll: int | None = None,
    rng: Random | None = None,
) -> tuple[bool, EffectInstance | None]:
    queue = _ensure_queue(target)
    if not check_delivery_requirements(target, effect_def.delivery):
        return False, None
    if effect_def.resistance_dc > 0 and effect_def.resistance_stat:
        resistance_roll = d20_roll if d20_roll is not None else _rng(rng).randint(1, 20)
        if check_resistance(target, effect_def.resistance_stat, effect_def.resistance_dc, resistance_roll):
            return False, None
    saved = False
    if effect_def.saving_throw_type != "none":
        save_roll = d20_roll if d20_roll is not None else _rng(rng).randint(1, 20)
        saved = resolve_saving_throw(target, effect_def.saving_throw_type, effect_def.saving_throw_dc, save_roll)
        if saved and effect_def.category == "condition":
            return False, None
    instance = EffectInstance(
        instance_id=f"{effect_def.effect_def_id}:{source_id}:{current_tick}:{len(queue.instances)}",
        effect_def_id=effect_def.effect_def_id,
        effect_def=effect_def,
        source_id=source_id,
        target_id=target.identity.actor_id,
        ticks_remaining=_initial_ticks(effect_def),
        saved=saved,
        tick_applied=current_tick,
    )
    queue.add(instance)
    _sync_actor_condition_state(target)
    return True, instance


def tick_effects(actor: ActorRecord, current_tick: int) -> list[dict[str, Any]]:
    queue = actor.effect_queue
    if queue is None:
        return []
    return queue.tick_all(actor, current_tick)


def compute_effective_stat(actor: ActorRecord, stat_name: str) -> int:
    base_value = float(actor.stats.get(stat_name, 0))
    queue = actor.effect_queue
    if queue is None:
        return int(base_value)
    flat_total, pct_total, set_override = queue.compute_stat_modifier(stat_name)
    effective = base_value + flat_total
    effective *= 1.0 + (pct_total / 100.0)
    if set_override is not None:
        effective = set_override
    return int(effective)


def dispel_effects(
    actor: ActorRecord,
    *,
    category: str | None = None,
    tag: str | None = None,
    effect_def_id: str | None = None,
) -> list[EffectInstance]:
    queue = actor.effect_queue
    if queue is None:
        return []
    removed: list[EffectInstance] = []
    if category is not None:
        removed = queue.dispel_by_category(category)
    elif tag is not None:
        removed = queue.dispel_by_tag(tag)
    elif effect_def_id is not None:
        removed = queue.dispel_by_id(effect_def_id)
    _sync_actor_condition_state(actor)
    return removed


def resolve_saving_throw(target: ActorRecord, save_type: str, dc: int, d20_roll: int) -> bool:
    roll = int(d20_roll)
    if roll <= 1:
        return False
    if roll >= 20:
        return True
    save_key = str(save_type).lower()
    save_bonus = int(target.raw_payload.get("save_bonuses", {}).get(save_key, 0))
    stat_bonus = _ability_modifier(_save_stat_value(target, save_key))
    return roll + save_bonus + stat_bonus >= int(dc)


def check_resistance(target: ActorRecord, resistance_stat: str, resistance_dc: int, d20_roll: int) -> bool:
    roll = int(d20_roll)
    stat_value = _stat_lookup(target, resistance_stat)
    return roll + _ability_modifier(stat_value) >= int(resistance_dc)


def check_delivery_requirements(target: ActorRecord, delivery: str) -> bool:
    mode = str(delivery or "direct").lower()
    if mode == "direct":
        return True
    if mode == "contact":
        torso_blocked = any(
            int(item.payload.get("coverage_percentage", 100)) >= 100
            for _, item in target.equipment.covering_items("torso")
        )
        return not torso_blocked
    if mode == "inhaled":
        return _has_functioning_part(target, {"lungs", "lung", "chest"})
    if mode == "injected":
        if target.body_state is None:
            return False
        return any(wound.open_wound for wound in target.body_state.wounds)
    if mode == "ingested":
        return _has_functioning_part(target, {"stomach", "gut", "torso"})
    return True


def _ensure_queue(actor: ActorRecord) -> EffectQueue:
    if actor.effect_queue is None:
        actor.effect_queue = EffectQueue(actor_id=actor.identity.actor_id)
    return actor.effect_queue


def _sync_actor_condition_state(actor: ActorRecord) -> None:
    queue = actor.effect_queue
    active = sorted(queue.active_conditions()) if queue is not None else []
    actor.conditions = [
        ConditionRecord(condition_id=f"effect:{flag}", name=flag, duration_ticks=None, severity=1, tags=["effect"])
        for flag in active
    ]


def _equipped_item_ids(actor: ActorRecord) -> set[str]:
    equipped: set[str] = set()
    for items in actor.equipment.slots.values():
        for item in items:
            equipped.add(item.instance_id)
    return equipped


def _initial_ticks(effect_def: EffectDef) -> int:
    if effect_def.timing_mode in {"permanent", "while_equipped"}:
        return -1
    if effect_def.timing_mode == "duration":
        return int(effect_def.base_duration_ticks)
    return int(effect_def.base_duration_ticks)


def _build_dot_wound(actor: ActorRecord, effect_def: EffectDef, damage: int, current_tick: int) -> WoundRecord:
    assert actor.body_state is not None
    body_part_id = "torso" if "torso" in actor.body_state.parts else next(iter(actor.body_state.parts))
    return WoundRecord(
        wound_id=f"{effect_def.effect_def_id}:{body_part_id}:{current_tick}:{len(actor.body_state.wounds)}",
        body_part_id=body_part_id,
        damage_type=effect_def.damage_type or "effect",
        damage_amount=max(0, int(damage)),
        bleeding=max(0, int(damage // 2 if effect_def.damage_type == "bleed" else 0)),
        pain=max(0, int(damage)),
        open_wound=False,
        untreated=False,
        tags=list(effect_def.tags),
    )


def _rng(rng: Random | None) -> Random:
    return rng if rng is not None else Random(0)


def _save_stat_value(target: ActorRecord, save_key: str) -> int:
    for candidate in SAVE_STAT_MAP.get(save_key, ("WIS",)):
        if candidate in target.stats:
            return int(target.stats[candidate])
    return 10


def _stat_lookup(target: ActorRecord, stat_name: str) -> int:
    aliases = {
        "con": ("CON", "constitution"),
        "constitution": ("CON", "constitution"),
        "dex": ("DEX", "dexterity"),
        "dexterity": ("DEX", "dexterity"),
        "wis": ("WIS", "wisdom"),
        "wisdom": ("WIS", "wisdom"),
        "str": ("STR", "strength"),
        "strength": ("STR", "strength"),
    }
    key = str(stat_name).lower()
    for candidate in aliases.get(key, (stat_name, stat_name.upper(), key)):
        if candidate in target.stats:
            return int(target.stats[candidate])
    return int(target.stats.get(str(stat_name), 0))


def _ability_modifier(value: int) -> int:
    return (int(value) - 10) // 2


def _has_functioning_part(target: ActorRecord, part_tokens: set[str]) -> bool:
    if target.body_state is None:
        return False
    for part_id, state in target.body_state.parts.items():
        lowered = part_id.lower()
        if any(token in lowered for token in part_tokens):
            return state.current_hp > 0
    return True

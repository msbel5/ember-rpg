from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Any

from engine.kernel.actor import ActorRecord, MaterialDef
from engine.kernel.actor_items import (
    CANONICAL_EQUIPMENT_SLOTS,
    candidate_canonical_slots_for_item_payload,
    canonical_equipment_slot,
    preferred_storage_slot_for_item,
)
from engine.kernel.common import serialize_value
from engine.kernel.combat import QUALITY_MULTIPLIERS
from engine.kernel.effects import apply_effect


EQUIPMENT_SLOTS = sorted(set(list(CANONICAL_EQUIPMENT_SLOTS) + [
    "quiver_1", "quiver_2", "quiver_3", "quiver_4",
    "quick_item_1", "quick_item_2", "quick_item_3",
]))
INVENTORY_SIZE = 16


@dataclass
class CombatHeader:
    attack_type: str
    range: int
    speed_factor: int
    thac0_bonus: int = 0
    dice_count: int = 1
    dice_sides: int = 6
    damage_bonus: int = 0
    damage_type: str = "bludgeoning"
    on_hit_effect_ids: list[str] = field(default_factory=list)
    projectile_type: str = "none"
    ammo_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CombatHeader":
        payload = dict(data)
        payload["on_hit_effect_ids"] = [str(item) for item in payload.get("on_hit_effect_ids", [])]
        return cls(**payload)


@dataclass
class ItemRequirements:
    min_mig: int = 0
    min_agi: int = 0
    min_mnd: int = 0
    min_ins: int = 0
    min_end: int = 0
    min_pre: int = 0
    min_level: int = 0
    class_usability: list[str] = field(default_factory=list)

    def met_by(self, actor: ActorRecord) -> tuple[bool, list[str]]:
        failures: list[str] = []
        # Item requirement checks use canonical Ember stat keys.
        checks = [
            ("min_mig", ("MIG",)),
            ("min_agi", ("AGI",)),
            ("min_mnd", ("MND",)),
            ("min_ins", ("INS",)),
            ("min_end", ("END",)),
            ("min_pre", ("PRE",)),
        ]
        for field_name, stat_keys in checks:
            required = int(getattr(self, field_name))
            if required <= 0:
                continue
            actual = _actor_stat(actor, *stat_keys)
            if actual < required:
                failures.append(f"{field_name}: need {required} have {actual}")
        if self.min_level > 0:
            actual_level = int(actor.raw_payload.get("level", 0))
            if actual_level < self.min_level:
                failures.append(f"min_level: need {self.min_level} have {actual_level}")
        if self.class_usability:
            actor_class = str(actor.raw_payload.get("class_id", "")).lower()
            allowed = {entry.lower() for entry in self.class_usability}
            if actor_class and actor_class not in allowed:
                failures.append(f"class_usability: {actor_class} not allowed")
        return len(failures) == 0, failures

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemRequirements":
        payload = dict(data)
        payload["class_usability"] = [str(item) for item in payload.get("class_usability", [])]
        return cls(**payload)


@dataclass
class ItemDef:
    item_def_id: str
    label: str
    item_type: str
    item_category: str
    weight: int
    base_price: int
    max_stack: int = 1
    enchantment: int = 0
    requirements: ItemRequirements = field(default_factory=ItemRequirements)
    combat_headers: list[CombatHeader] = field(default_factory=list)
    equip_effect_ids: list[str] = field(default_factory=list)
    use_effect_ids: list[str] = field(default_factory=list)
    lore_to_identify: int = 0
    base_durability: int = 100
    flags: list[str] = field(default_factory=list)
    description: str = ""
    identified_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemDef":
        payload = dict(data)
        payload["requirements"] = ItemRequirements.from_dict(payload.get("requirements", {}))
        payload["combat_headers"] = [CombatHeader.from_dict(item) for item in payload.get("combat_headers", [])]
        payload["equip_effect_ids"] = [str(item) for item in payload.get("equip_effect_ids", [])]
        payload["use_effect_ids"] = [str(item) for item in payload.get("use_effect_ids", [])]
        payload["flags"] = [str(item) for item in payload.get("flags", [])]
        return cls(**payload)


@dataclass
class ItemInstance:
    instance_id: str
    item_def_id: str
    material_id: str = "iron"
    quality: int = 0
    wear: int = 0
    max_wear: int = 100
    identified: bool = False
    charges: int = -1
    stack_count: int = 1
    equipped_slot: str | None = None

    @property
    def is_broken(self) -> bool:
        return self.wear >= self.max_wear

    def add_wear(self, amount: int) -> None:
        self.wear = min(int(self.max_wear), int(self.wear) + max(0, int(amount)))

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemInstance":
        return cls(**data)


def can_equip(actor: ActorRecord, item_def: ItemDef) -> tuple[bool, list[str]]:
    return item_def.requirements.met_by(actor)


def equip_item(actor: ActorRecord, item: ItemInstance, slot: str, item_def: ItemDef) -> list[dict[str, Any]]:
    if slot not in EQUIPMENT_SLOTS:
        raise ValueError(f"Invalid equipment slot `{slot}`")
    if not _item_fits_slot(item_def, slot):
        raise ValueError(f"{item_def.item_type} cannot be equipped to {slot}")
    allowed, failures = can_equip(actor, item_def)
    if not allowed:
        raise ValueError("; ".join(failures))

    events: list[dict[str, Any]] = []
    requested_slot = str(slot)
    canonical_slot = canonical_equipment_slot(requested_slot)
    storage_slot = requested_slot
    if canonical_slot is not None:
        storage_slot = preferred_storage_slot_for_item(
            canonical_slot,
            {
                "id": item_def.item_def_id,
                "item_def_id": item_def.item_def_id,
                "name": item_def.label,
                "type": item_def.item_type,
            },
            requested_slot=requested_slot,
        )
    alias_slots = [storage_slot]
    existing: list[ItemInstance] = []
    for alias_slot in alias_slots:
        existing.extend(actor.equipment.slots.get(alias_slot, []))
        if alias_slot != storage_slot:
            actor.equipment.slots[alias_slot] = []
    if existing:
        for previous in existing:
            previous.equipped_slot = None
            actor.inventory.append(previous)
            events.append({"type": "unequipped", "item_id": previous.instance_id, "slot": storage_slot, "canonical_slot": canonical_slot or storage_slot})
    actor.equipment.slots[storage_slot] = [item]
    item.equipped_slot = canonical_slot or storage_slot
    if item in actor.inventory:
        actor.inventory.remove(item)
    for effect_id in item_def.equip_effect_ids:
        effect_def = _effect_registry(actor).get(effect_id)
        if effect_def is None:
            continue
        apply_effect(actor, effect_def, source_id=item.instance_id, current_tick=0)
        events.append({"type": "equip_effect", "effect_id": effect_id})
    events.append({"type": "equipped", "item_id": item.instance_id, "slot": storage_slot, "canonical_slot": canonical_slot or storage_slot})
    return events


def unequip_item(actor: ActorRecord, slot: str) -> list[dict[str, Any]]:
    if slot not in EQUIPMENT_SLOTS:
        raise ValueError(f"Invalid equipment slot `{slot}`")
    items = list(actor.equipment.slots.get(slot, []))
    if not items:
        return []
    actor.equipment.slots[slot] = []
    removed_item_ids = {item.instance_id for item in items}
    for item in items:
        item.equipped_slot = None
        actor.inventory.append(item)
    if actor.effect_queue is not None:
        actor.effect_queue.instances = [
            instance for instance in actor.effect_queue.instances if instance.source_id not in removed_item_ids
        ]
        actor.effect_queue.rebuild_condition_cache()
    return [{"type": "unequipped", "item_id": item.instance_id, "slot": slot} for item in items]


def use_item(
    actor: ActorRecord,
    item: ItemInstance,
    item_def: ItemDef,
    target: ActorRecord | None,
    rng: Random | None = None,
) -> dict[str, Any]:
    if not item_def.use_effect_ids:
        raise ValueError("Item has no use effects")
    registry = _effect_registry(actor)
    recipient = target or actor
    applied: list[str] = []
    for effect_id in item_def.use_effect_ids:
        effect_def = registry.get(effect_id)
        if effect_def is None:
            continue
        used, instance = apply_effect(recipient, effect_def, source_id=item.instance_id, current_tick=0, rng=rng)
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
    destroyed = False
    if item.charges > 0:
        item.charges -= 1
        if item.charges <= 0:
            destroyed = item_def.item_type in {"potion", "scroll"}
    return {"effects": applied, "charges_remaining": item.charges, "destroyed": destroyed}


def identify_item(actor: ActorRecord, item: ItemInstance, item_def: ItemDef) -> bool:
    lore = int(actor.skills.get("lore", 0))
    if lore >= int(item_def.lore_to_identify):
        item.identified = True
        return True
    return False


def compute_item_wear(item: ItemInstance, item_def: ItemDef, material: MaterialDef) -> int:
    hardness_ratio = float(material.impact_fracture or 100) / 100.0
    quality_multiplier = QUALITY_MULTIPLIERS.get(int(item.quality), 1.0)
    item.max_wear = int(item_def.base_durability * hardness_ratio * quality_multiplier)
    return item.max_wear


def apply_item_wear(item: ItemInstance, wear_amount: int) -> bool:
    was_broken = item.is_broken
    item.add_wear(wear_amount)
    return not was_broken and item.is_broken


def can_stack(a: ItemInstance, b: ItemInstance) -> bool:
    return (
        a.item_def_id == b.item_def_id
        and a.material_id == b.material_id
        and a.quality == b.quality
        and not a.is_broken
        and not b.is_broken
        and a.equipped_slot is None
        and b.equipped_slot is None
    )


def compute_encumbrance(inventory: list[ItemInstance], item_registry: dict[str, ItemDef]) -> int:
    total = 0
    for item in inventory:
        item_def = item_registry[item.item_def_id]
        total += int(item_def.weight) * max(1, int(item.stack_count))
    return total


def bypasses_weapon_immunity(item_def: ItemDef, target_traits: dict[str, Any]) -> bool:
    if not bool(target_traits.get("immune_to_nonmagical_weapons")):
        return True
    return int(item_def.enchantment) > 0 or "magical" in {flag.lower() for flag in item_def.flags}


def _item_fits_slot(item_def: ItemDef, slot: str) -> bool:
    normalized_slot = str(slot).strip().lower()
    if normalized_slot.startswith("quiver_"):
        return item_def.item_type in {"ammunition"}
    if normalized_slot.startswith("quick_item_"):
        return item_def.item_type in {"potion", "scroll", "wand", "misc"}
    canonical_slot = canonical_equipment_slot(normalized_slot)
    if canonical_slot is None:
        return False
    candidates = set(
        candidate_canonical_slots_for_item_payload(
            {
                "id": item_def.item_def_id,
                "item_def_id": item_def.item_def_id,
                "name": item_def.label,
                "type": item_def.item_type,
                "slot": normalized_slot,
            }
        )
    )
    if canonical_slot in candidates:
        return True
    if canonical_slot == "ring_right" and "ring_left" in candidates:
        return True
    if canonical_slot == "trinket_2" and "trinket_1" in candidates:
        return True
    if canonical_slot.startswith("attunement_") and {"attunement_1", "attunement_2", "attunement_3"} & candidates:
        return True
    return False


def _effect_registry(actor: ActorRecord) -> dict[str, Any]:
    return dict(actor.raw_payload.get("effect_registry", {}))


def _actor_stat(actor: ActorRecord, *keys: str) -> int:
    for key in keys:
        if key in actor.stats:
            return int(actor.stats[key])
    return 0

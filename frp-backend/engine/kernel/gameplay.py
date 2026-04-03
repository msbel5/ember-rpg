from __future__ import annotations

import re
import uuid
from typing import Any

from engine.kernel.actor_records import ActorRecord
from engine.kernel.actor_items import ItemStack, item_stack_from_legacy_payload


def add_inventory_item(
    actor: ActorRecord,
    *,
    item_def_id: str,
    quantity: int = 1,
    item_data: dict[str, Any] | None = None,
    instance_prefix: str = "item",
) -> list[ItemStack]:
    created: list[ItemStack] = []
    payload = dict(item_data or {})
    payload.setdefault("id", item_def_id)
    payload.setdefault("item_def_id", item_def_id)
    payload.setdefault("name", payload.get("name", item_def_id.replace("_", " ").title()))
    for _ in range(max(1, int(quantity))):
        item_payload = dict(payload)
        item_payload["quantity"] = 1
        item_payload["instance_id"] = f"{instance_prefix}_{uuid.uuid4().hex[:8]}"
        stack = item_stack_from_legacy_payload(item_payload)
        actor.inventory.append(stack)
        created.append(stack)
    return created


def remove_inventory_item(actor: ActorRecord, *, item_def_id: str, quantity: int = 1) -> list[ItemStack]:
    removed: list[ItemStack] = []
    remaining = max(1, int(quantity))
    for item in list(actor.inventory):
        if remaining <= 0:
            break
        if getattr(item, "item_def_id", "") != item_def_id:
            continue
        stack_qty = max(1, int(getattr(item, "quantity", 1)))
        if stack_qty <= remaining:
            actor.inventory.remove(item)
            removed.append(item)
            remaining -= stack_qty
            continue
        item.quantity = stack_qty - remaining
        removed_payload = item.to_dict()
        removed_payload["quantity"] = remaining
        removed_payload["instance_id"] = f"removed_{uuid.uuid4().hex[:8]}"
        removed.append(ItemStack.from_dict(removed_payload))
        remaining = 0
    return removed


def equip_inventory_item(actor: ActorRecord, *, item: ItemStack, slot: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    existing = list(actor.equipment.slots.get(slot, []))
    if existing:
        for previous in existing:
            previous.payload.pop("equipped_slot", None)
            actor.inventory.append(previous)
            events.append({"type": "unequipped", "item_id": previous.instance_id, "slot": slot})
    actor.equipment.slots[slot] = [item]
    item.payload["equipped_slot"] = slot
    if item in actor.inventory:
        actor.inventory.remove(item)
    events.append({"type": "equipped", "item_id": item.instance_id, "slot": slot})
    return events


def unequip_actor_slot(actor: ActorRecord, *, slot: str) -> list[dict[str, Any]]:
    items = list(actor.equipment.slots.get(slot, []))
    if not items:
        return []
    actor.equipment.slots[slot] = []
    for item in items:
        item.payload.pop("equipped_slot", None)
        actor.inventory.append(item)
    return [{"type": "unequipped", "item_id": item.instance_id, "slot": slot} for item in items]


def craft_recipe(
    actor: ActorRecord,
    *,
    recipe: dict[str, Any],
    item_catalog: dict[str, dict[str, Any]] | None = None,
    instance_prefix: str = "craft",
) -> dict[str, Any]:
    consumed: list[ItemStack] = []
    for ingredient in recipe.get("ingredients", []):
        ingredient_id = str(ingredient.get("item_id", ""))
        ingredient_qty = int(ingredient.get("quantity", 1))
        consumed.extend(remove_inventory_item(actor, item_def_id=ingredient_id, quantity=ingredient_qty))
    created: list[ItemStack] = []
    catalog = item_catalog or {}
    for product in recipe.get("products", []):
        product_id = str(product.get("item_id", ""))
        product_qty = int(product.get("quantity", 1))
        created.extend(
            add_inventory_item(
                actor,
                item_def_id=product_id,
                quantity=product_qty,
                item_data=catalog.get(product_id),
                instance_prefix=instance_prefix,
            )
        )
    xp_reward = int(recipe.get("xp_reward", 0))
    if xp_reward > 0:
        actor.xp = actor.xp + xp_reward
    return {"consumed": consumed, "created": created, "xp_reward": xp_reward}


def apply_rest(actor: ActorRecord, *, long_rest: bool, current_tick: int) -> dict[str, Any]:
    if long_rest:
        actor.hp = int(actor.stats.get("max_hp", actor.stats.get("hp", 1)))
        actor.spell_points = int(actor.raw_payload.get("max_spell_points", actor.spell_points))
        spellbooks_raw = actor.raw_payload.get("spellbooks", {})
        from engine.kernel.spells import Spellbook, rest_refresh_spellbook

        for book_key, book_data in spellbooks_raw.items():
            if isinstance(book_data, dict):
                spellbook = Spellbook.from_dict(book_data)
                rest_refresh_spellbook(spellbook)
                spellbooks_raw[book_key] = spellbook.to_dict()
        exhaustion = int(actor.raw_payload.get("exhaustion_level", 0))
        if exhaustion > 0:
            actor.raw_payload["exhaustion_level"] = max(0, exhaustion - 1)
        actor.raw_payload["last_long_rest_tick"] = int(current_tick)
        return {"hours": 8, "healed": 0, "spell_points_restored": True}

    end_mod = (int(actor.stats.get("END", 10)) - 10) // 2
    heal_amount = max(1, end_mod + int(actor.raw_payload.get("level", 1)))
    actor.hp = min(int(actor.stats.get("max_hp", actor.hp)), actor.hp + heal_amount)
    max_sp = int(actor.raw_payload.get("max_spell_points", 0))
    restored_sp = 0
    if max_sp > 0:
        restored_sp = max(1, max_sp // 4)
        actor.spell_points = min(max_sp, actor.spell_points + restored_sp)
    return {"hours": 1, "healed": heal_amount, "spell_points_restored": restored_sp}


def cast_registry_spell(
    actor: ActorRecord,
    *,
    spell_id: str,
    spell_data: dict[str, Any],
    target: ActorRecord | None,
    current_tick: int,
) -> dict[str, Any]:
    cost = int(spell_data.get("cost", 0))
    if cost > 0:
        actor.spell_points = actor.spell_points - cost
    recipient = target or actor
    applied: list[dict[str, Any]] = []
    for effect in spell_data.get("effects", []):
        effect_type = str(effect.get("type", ""))
        if effect_type == "damage":
            amount = _resolve_effect_amount(effect.get("amount", 0))
            recipient.hp = max(0, recipient.hp - amount)
            applied.append({"type": "damage", "amount": amount, "target": recipient.name})
        elif effect_type == "heal":
            amount = _resolve_effect_amount(effect.get("amount", 0))
            recipient.hp = min(int(recipient.stats.get("max_hp", recipient.hp)), recipient.hp + amount)
            applied.append({"type": "heal", "amount": amount, "target": recipient.name})
        elif effect_type in {"buff", "status"}:
            active = list(recipient.raw_payload.get("active_spell_effects", []))
            active.append(
                {
                    "spell_id": spell_id,
                    "effect_type": effect_type,
                    "effect": dict(effect),
                    "applied_tick": int(current_tick),
                }
            )
            recipient.raw_payload["active_spell_effects"] = active
            applied.append({"type": effect_type, "target": recipient.name})
        else:
            applied.append({"type": effect_type or "unknown", "target": recipient.name})
    return {"cost": cost, "applied": applied}


def _resolve_effect_amount(raw_amount: Any) -> int:
    if isinstance(raw_amount, (int, float)):
        return max(0, int(raw_amount))
    text = str(raw_amount).strip().lower()
    match = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", text)
    if match is None:
        try:
            return max(0, int(text))
        except ValueError:
            return 0
    dice_count = int(match.group(1))
    dice_sides = int(match.group(2))
    modifier = int(match.group(3) or 0)
    average = dice_count * (dice_sides + 1) // 2
    return max(0, average + modifier)


__all__ = [
    "add_inventory_item",
    "apply_rest",
    "cast_registry_spell",
    "craft_recipe",
    "equip_inventory_item",
    "remove_inventory_item",
    "unequip_actor_slot",
]
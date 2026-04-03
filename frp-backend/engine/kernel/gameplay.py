from __future__ import annotations

import copy
import re
import uuid
from typing import Any

from engine.kernel.actor_records import ActorRecord
from engine.kernel.actor_items import ItemStack, item_stack_from_legacy_payload
from engine.kernel.effects import EffectDef, tick_effects
from engine.kernel.spells import SpellDef, Spellbook, begin_casting, resolve_cast
from engine.world.entity import Entity, EntityType


GROUND_ITEMS_STATE_KEY = "ground_items"


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


def restore_ground_item_entities(session: Any) -> list[Entity]:
    spatial_index = getattr(session, "spatial_index", None)
    if spatial_index is None:
        return []
    stored_entities = list(getattr(session, "campaign_state", {}).get(GROUND_ITEMS_STATE_KEY, []))
    if not stored_entities:
        return []
    existing_ids = {
        str(entity.id)
        for entity in spatial_index.all_entities()
        if getattr(entity, "entity_type", None) == EntityType.ITEM
    }
    restored: list[Entity] = []
    for payload in stored_entities:
        entity_id = str(payload.get("id", "")).strip()
        if not entity_id or entity_id in existing_ids:
            continue
        entity = Entity.from_dict(copy.deepcopy(payload))
        spatial_index.add(entity)
        restored.append(entity)
    return restored


def persist_ground_item_entities(session: Any) -> list[dict[str, Any]]:
    spatial_index = getattr(session, "spatial_index", None)
    if spatial_index is None:
        getattr(session, "campaign_state", {})[GROUND_ITEMS_STATE_KEY] = []
        return []
    ground_items = [
        entity.to_dict()
        for entity in spatial_index.all_entities()
        if getattr(entity, "entity_type", None) == EntityType.ITEM
    ]
    session.campaign_state[GROUND_ITEMS_STATE_KEY] = copy.deepcopy(ground_items)
    return ground_items


def spawn_ground_item_entity(
    session: Any,
    *,
    item: dict[str, Any],
    position: tuple[int, int] | None = None,
    entity_id: str | None = None,
) -> Entity:
    spatial_index = getattr(session, "spatial_index", None)
    if spatial_index is None:
        raise ValueError("Session has no spatial index for ground-item authority")
    payload = _normalize_ground_item_payload(item)
    px, py = position or _session_position(session)
    entity = Entity(
        id=str(entity_id or payload.get("ground_instance_id") or payload.get("instance_id") or Entity.generate_id()),
        entity_type=EntityType.ITEM,
        name=str(payload.get("name", payload.get("id", "Unknown Item"))),
        position=(int(px), int(py)),
        glyph="!",
        color="yellow",
        blocking=False,
        inventory=[copy.deepcopy(payload)],
    )
    spatial_index.add(entity)
    persist_ground_item_entities(session)
    return entity


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


def pickup_ground_item(session: Any, *, query: str = "") -> dict[str, Any]:
    restore_ground_item_entities(session)
    spatial_index = getattr(session, "spatial_index", None)
    if spatial_index is None:
        return {"success": False, "reason": "no_spatial_index"}
    px, py = _session_position(session)
    entities_here = list(spatial_index.at(int(px), int(py)))
    items_here = [entity for entity in entities_here if entity.entity_type == EntityType.ITEM]
    target = (query or "").lower().strip()
    match = None
    if target:
        normalized_target = target.replace("_", " ")
        match = next(
            (
                entity
                for entity in items_here
                if _ground_item_matches(entity, target, normalized_target)
            ),
            None,
        )
    elif items_here:
        match = items_here[0]
    if match is None:
        return {"success": False, "reason": "not_found"}
    item_payload = _normalize_ground_item_payload((match.inventory or [{}])[0])
    item_payload["entity_id"] = match.id
    item_payload["ground_instance_id"] = match.id
    status = session.assess_item_addition(item_payload, merge=True)
    if not bool(status.get("allowed", False)):
        if status.get("reason") == "overweight":
            session._record_add_item_failure(status)
        return {"success": False, "reason": str(status.get("reason", "blocked")), "item_name": match.name}
    spatial_index.remove(match)
    added = session.add_item(item_payload, merge=True)
    if added is None:
        spatial_index.add(match)
        persist_ground_item_entities(session)
        return {"success": False, "reason": "add_failed", "item_name": match.name}
    persist_ground_item_entities(session)
    return {"success": True, "item_name": match.name, "item": added, "entity_id": match.id}


def drop_inventory_item(session: Any, *, query: str) -> dict[str, Any]:
    restore_ground_item_entities(session)
    removed = session.remove_item(query)
    if removed is None:
        return {"success": False, "reason": "missing_inventory_item", "item_name": query}
    entity = spawn_ground_item_entity(session, item=removed)
    return {
        "success": True,
        "item_name": str(removed.get("name", removed.get("id", query))),
        "item": removed,
        "entity_id": entity.id,
    }


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
    skill_name = str(recipe.get("skill", ""))
    skill_dc = int(recipe.get("skill_dc", 0))
    player_skill = int(actor.skills.get(skill_name, 0)) if skill_name else 0
    if skill_name and skill_dc > 0 and player_skill < skill_dc:
        return {
            "success": False,
            "reason": "skill_too_low",
            "skill": skill_name,
            "required": skill_dc,
            "actual": player_skill,
        }

    for ingredient in recipe.get("ingredients", []):
        ingredient_id = str(ingredient.get("item_id", ""))
        ingredient_qty = int(ingredient.get("quantity", 1))
        available_qty = _count_actor_inventory_item(actor, ingredient_id)
        if available_qty < ingredient_qty:
            return {
                "success": False,
                "reason": "missing_ingredient",
                "item_id": ingredient_id,
                "required": ingredient_qty,
                "available": available_qty,
            }

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
    return {"success": True, "consumed": consumed, "created": created, "xp_reward": xp_reward}


def resolve_rest(actor: ActorRecord, *, long_rest: bool, current_tick: int) -> dict[str, Any]:
    if long_rest:
        last_long_rest = int(actor.raw_payload.get("last_long_rest_tick", 0))
        if current_tick - last_long_rest < 24 and last_long_rest > 0:
            return {"success": False, "reason": "cooldown", "hours": 0}
    rest_result = apply_rest(actor, long_rest=long_rest, current_tick=current_tick)
    return {"success": True, **rest_result}


def apply_rest(actor: ActorRecord, *, long_rest: bool, current_tick: int) -> dict[str, Any]:
    if long_rest:
        actor.hp = int(actor.stats.get("max_hp", actor.stats.get("hp", 1)))
        actor.spell_points = actor.max_spell_points
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
    heal_amount = max(1, end_mod + int(actor.level))
    actor.hp = min(int(actor.stats.get("max_hp", actor.hp)), actor.hp + heal_amount)
    max_sp = int(actor.max_spell_points)
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
    spell_label = str(spell_data.get("name", spell_id.replace("_", " ").title()))
    if cost > actor.spell_points:
        return {
            "success": False,
            "reason": "insufficient_spell_points",
            "cost": cost,
            "spell_label": spell_label,
            "applied": [],
        }
    spell_def = _spell_def_from_registry_data(spell_id, spell_data, target)
    spellbook = Spellbook(actor_id=actor.identity.actor_id, spell_type=spell_def.spell_type)
    target_id = target.identity.actor_id if spell_def.target_type == "creature" and target is not None else None
    ok, attempt, reason = begin_casting(actor, spellbook, spell_def, target_id, None, int(current_tick))
    if not ok or attempt is None:
        return {
            "success": False,
            "reason": reason or "cast_failed",
            "cost": cost,
            "spell_label": spell_label,
            "applied": [],
        }
    previous_registry = dict(actor.raw_payload.get("effect_registry", {}))
    registry_patch = _build_spell_effect_registry(spell_def.spell_id, spell_data)
    actor.raw_payload["effect_registry"] = {**previous_registry, **registry_patch}
    try:
        actor.spell_points = actor.spell_points - cost
        resolution = resolve_cast(attempt, actor, target, d100_roll=100, current_tick=int(current_tick))
        recipient = target or actor
        effect_events = tick_effects(recipient, int(current_tick))
    finally:
        actor.raw_payload["effect_registry"] = previous_registry
    applied = _build_applied_spell_effects(
        spell_def=spell_def,
        spell_data=spell_data,
        recipient=target or actor,
        resolution=resolution,
        effect_events=effect_events,
    )
    return {
        "success": not bool(resolution.get("resisted", False)),
        "reason": "resisted" if resolution.get("resisted", False) else "",
        "cost": cost,
        "spell_label": spell_label,
        "applied": applied,
        "effects_applied": list(resolution.get("effects_applied", [])),
    }


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


def _build_spell_effect_registry(spell_id: str, spell_data: dict[str, Any]) -> dict[str, EffectDef]:
    registry: dict[str, EffectDef] = {}
    for index, effect in enumerate(spell_data.get("effects", [])):
        if not isinstance(effect, dict):
            continue
        effect_id = _spell_effect_id(spell_id, index, effect)
        registry[effect_id] = _effect_def_from_spell_effect(effect_id, effect)
    return registry


def _spell_def_from_registry_data(
    spell_id: str,
    spell_data: dict[str, Any],
    target: ActorRecord | None,
) -> SpellDef:
    target_type = _spell_target_type(str(spell_data.get("target_type", "single")), target)
    return SpellDef(
        spell_id=spell_id,
        label=str(spell_data.get("name", spell_id.replace("_", " ").title())),
        spell_type=str(spell_data.get("spell_type", "sorcerer")),
        school=str(spell_data.get("school", "evocation")),
        level=int(spell_data.get("level", 1)),
        casting_time=int(spell_data.get("casting_time", 0)),
        range=int(spell_data.get("range", 0)),
        target_type=target_type,
        hostile=target_type != "self",
        effect_def_ids=[
            _spell_effect_id(spell_id, index, effect)
            for index, effect in enumerate(spell_data.get("effects", []))
            if isinstance(effect, dict)
        ],
        projectile_type="none",
    )


def _spell_effect_id(spell_id: str, index: int, effect: dict[str, Any]) -> str:
    suffix = str(effect.get("type", f"effect_{index}")).strip().lower().replace(" ", "_")
    return f"{spell_id}_{index}_{suffix}"


def _effect_def_from_spell_effect(effect_id: str, effect: dict[str, Any]) -> EffectDef:
    effect_type = str(effect.get("type", "unknown")).lower()
    amount = _resolve_effect_amount(effect.get("amount", 0))
    if effect_type == "damage":
        return EffectDef(
            effect_def_id=effect_id,
            label=str(effect.get("damage_type", "damage")).title(),
            category="dot",
            damage_per_tick=amount,
            damage_type=str(effect.get("damage_type", "arcane")),
            timing_mode="duration",
            base_duration_ticks=1,
        )
    if effect_type == "heal":
        return EffectDef(
            effect_def_id=effect_id,
            label="Healing",
            category="healing",
            healing_per_tick=amount,
            timing_mode="instant",
            base_duration_ticks=0,
        )
    if effect_type == "buff":
        stat_key = _normalize_spell_stat(str(effect.get("stat", "")))
        return EffectDef(
            effect_def_id=effect_id,
            label=f"Buff {stat_key}",
            category="stat_mod",
            target_stat=stat_key,
            modifier_type="flat",
            modifier_value=float(effect.get("amount", effect.get("bonus", 0))),
            timing_mode="duration",
            base_duration_ticks=max(1, int(effect.get("duration", 1))),
        )
    return EffectDef(
        effect_def_id=effect_id,
        label=str(effect.get("status", effect_type)).replace("_", " ").title(),
        category="condition",
        condition_flag=str(effect.get("status", effect_type)).lower().replace(" ", "_"),
        timing_mode="duration",
        base_duration_ticks=max(1, int(effect.get("duration", 1))),
    )


def _build_applied_spell_effects(
    *,
    spell_def: SpellDef,
    spell_data: dict[str, Any],
    recipient: ActorRecord,
    resolution: dict[str, Any],
    effect_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if resolution.get("resisted", False):
        return []
    damage_by_effect = {
        str(event.get("effect_id", "")): int(event.get("damage", 0))
        for event in effect_events
        if str(event.get("type", "")) == "dot_damage"
    }
    healing_by_effect = {
        str(effect_id): _resolve_effect_amount(effect.get("amount", 0))
        for effect_id, effect in zip(spell_def.effect_def_ids, spell_data.get("effects", []), strict=False)
        if isinstance(effect, dict) and str(effect.get("type", "")).lower() == "heal"
    }
    applied: list[dict[str, Any]] = []
    for effect_id, effect in zip(spell_def.effect_def_ids, spell_data.get("effects", []), strict=False):
        if not isinstance(effect, dict):
            continue
        effect_type = str(effect.get("type", "unknown")).lower()
        if effect_type == "damage":
            applied.append({
                "type": "damage",
                "amount": damage_by_effect.get(effect_id, _resolve_effect_amount(effect.get("amount", 0))),
                "target": recipient.name,
            })
        elif effect_type == "heal":
            applied.append({
                "type": "heal",
                "amount": healing_by_effect.get(effect_id, 0),
                "target": recipient.name,
            })
        else:
            applied.append({"type": effect_type, "target": recipient.name})
    return applied


def _spell_target_type(raw_target_type: str, target: ActorRecord | None) -> str:
    normalized = raw_target_type.strip().lower()
    if normalized == "self":
        return "self"
    if target is not None:
        return "creature"
    return "self"


def _normalize_spell_stat(stat_name: str) -> str:
    normalized = stat_name.strip().lower()
    mapping = {
        "armor_class": "ac",
        "ac": "ac",
        "mig": "MIG",
        "agi": "AGI",
        "mnd": "MND",
        "ins": "INS",
        "pre": "PRE",
        "end": "END",
    }
    return mapping.get(normalized, stat_name.upper() if len(stat_name) <= 3 else stat_name)


def _normalize_ground_item_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(dict(payload or {}))
    item_id = str(normalized.get("id") or normalized.get("item_def_id") or normalized.get("name", "item")).strip()
    normalized["id"] = item_id.lower().replace(" ", "_")
    normalized.setdefault("item_def_id", normalized["id"])
    normalized.setdefault("name", item_id.replace("_", " ").title())
    normalized.setdefault("qty", int(normalized.get("quantity", normalized.get("qty", 1)) or 1))
    normalized.setdefault("quantity", int(normalized["qty"]))
    normalized.setdefault("type", "item")
    return normalized


def _ground_item_matches(entity: Entity, target: str, normalized_target: str) -> bool:
    if target in entity.name.lower() or normalized_target in entity.name.lower():
        return True
    for payload in entity.inventory or []:
        normalized_payload = _normalize_ground_item_payload(payload)
        payload_id = str(normalized_payload.get("id", "")).lower()
        payload_name = str(normalized_payload.get("name", "")).lower()
        if target == payload_id or normalized_target == payload_name:
            return True
        if target in payload_id or normalized_target in payload_name:
            return True
    return False


def _session_position(session: Any) -> tuple[int, int]:
    position = list(getattr(session, "position", [0, 0]) or [0, 0])
    if len(position) < 2:
        return (0, 0)
    return (int(position[0]), int(position[1]))


def _count_actor_inventory_item(actor: ActorRecord, item_def_id: str) -> int:
    target_id = str(item_def_id).strip().lower()
    total = 0
    for item in actor.inventory:
        if getattr(item, "item_def_id", "").lower() != target_id:
            continue
        total += max(1, int(getattr(item, "quantity", 1)))
    return total


__all__ = [
    "add_inventory_item",
    "apply_rest",
    "cast_registry_spell",
    "craft_recipe",
    "drop_inventory_item",
    "equip_inventory_item",
    "persist_ground_item_entities",
    "pickup_ground_item",
    "remove_inventory_item",
    "resolve_rest",
    "restore_ground_item_entities",
    "spawn_ground_item_entity",
    "unequip_actor_slot",
]
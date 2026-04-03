"""Gameplay command handlers: equipment, inventory, crafting, rest, and spells.

Each handler follows the maybe_handle pattern — returns
(narrative, command_type, hours_advanced) or None when the
command text does not match.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import TYPE_CHECKING, Any, Optional

from engine.data._shared import items_registry, load_registry_list, recipes_registry, spells_registry
from engine.kernel.items import (
    EQUIPMENT_SLOTS,
    ItemDef,
    ItemInstance,
    equip_item,
    unequip_item,
)
from engine.kernel.spells import (
    Spellbook,
    SpellDef,
    begin_casting,
    resolve_cast,
    rest_refresh_spellbook,
)

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext
    from engine.kernel.actor import ActorRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _player(context: "CampaignContext") -> Optional["ActorRecord"]:
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    return actors.get("player")


def _fuzzy_match(query: str, candidates: dict[str, dict], name_key: str = "name") -> Optional[tuple[str, dict]]:
    """Find best match by id or name substring."""
    query_lower = query.lower().strip().replace(" ", "_")
    # Exact id match first.
    if query_lower in candidates:
        return query_lower, candidates[query_lower]
    # Substring match on name.
    for cid, entry in candidates.items():
        entry_name = str(entry.get(name_key, cid)).lower()
        if query_lower in entry_name or query_lower in cid.lower():
            return cid, entry
    return None


def _fuzzy_match_list(query: str, entries: list) -> Optional[dict]:
    """Find best match from a list of dicts by name substring."""
    query_lower = query.lower().strip().replace("_", " ")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_name = str(entry.get("name", "")).lower()
        entry_id = str(entry.get("id", "")).lower()
        if query_lower == entry_name or query_lower == entry_id:
            return entry
    # Substring match.
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_name = str(entry.get("name", "")).lower()
        entry_id = str(entry.get("id", "")).lower()
        if query_lower in entry_name or query_lower in entry_id:
            return entry
    return None


def _find_inventory_item_by_name(player: "ActorRecord", name: str) -> Optional[Any]:
    """Find an item in player.inventory by def_id or name substring."""
    name_lower = name.lower().strip().replace(" ", "_")
    for item in player.inventory:
        def_id = getattr(item, "item_def_id", "")
        if def_id == name_lower or name_lower in def_id.lower():
            return item
    return None


def _item_def_from_registry(item_def_id: str) -> Optional[dict]:
    registry = items_registry()
    return registry.get(item_def_id)


def _slot_for_item_type(item_type: str) -> str:
    """Determine equipment slot from item type string."""
    mapping = {
        "weapon": "weapon_1",
        "armor": "armor",
        "shield": "shield",
        "helmet": "helmet",
        "boots": "boots",
        "gloves": "gloves",
        "ring": "left_ring",
        "amulet": "amulet",
        "belt": "belt",
        "cloak": "cloak",
    }
    return mapping.get(item_type.lower(), "quick_item_1")


def _build_item_def(raw: dict) -> ItemDef:
    """Build a kernel ItemDef from a raw registry dict."""
    return ItemDef(
        item_def_id=str(raw.get("id", "")),
        label=str(raw.get("name", raw.get("id", ""))),
        item_type=str(raw.get("type", "misc")),
        item_category=str(raw.get("category", raw.get("type", "misc"))),
        weight=int(float(raw.get("weight", 0))),
        base_price=int(raw.get("value", 0)),
    )


def _summarize_events(events: list[dict]) -> str:
    parts = []
    for ev in events:
        ev_type = ev.get("type", "")
        if ev_type == "equipped":
            parts.append(f"Equipped item to {ev.get('slot', 'slot')}.")
        elif ev_type == "unequipped":
            parts.append(f"Unequipped item from {ev.get('slot', 'slot')}.")
        elif ev_type == "equip_effect":
            parts.append(f"Applied effect {ev.get('effect_id', '')}.")
    return " ".join(parts) if parts else "Done."


# ---------------------------------------------------------------------------
# Handler 1: Equipment (equip / unequip)
# ---------------------------------------------------------------------------

_EQUIP_RE = re.compile(r"^equip\s+(.+)$", re.IGNORECASE)
_UNEQUIP_RE = re.compile(r"^unequip\s+(.+)$", re.IGNORECASE)


def maybe_handle_equipment_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    player = _player(context)
    if player is None:
        return None

    match = _EQUIP_RE.match(command_text.strip())
    if match:
        item_name = match.group(1).strip()
        item = _find_inventory_item_by_name(player, item_name)
        if item is None:
            return (f"You don't have '{item_name}' in your inventory.", "equipment", 0)
        raw_def = _item_def_from_registry(item.item_def_id)
        if raw_def is None:
            return (f"Unknown item definition for '{item_name}'.", "equipment", 0)
        item_def = _build_item_def(raw_def)
        slot = _slot_for_item_type(item_def.item_type)
        # Build a kernel ItemInstance from the inventory ItemStack.
        kernel_item = ItemInstance(
            instance_id=getattr(item, "instance_id", str(uuid.uuid4())),
            item_def_id=item.item_def_id,
            material_id=getattr(item, "material_id", None) or "iron",
            quality=int(getattr(item, "quality", 0)),
            wear=int(getattr(item, "wear", 0)),
        )
        try:
            events = equip_item(player, kernel_item, slot, item_def)
        except ValueError as exc:
            return (f"Cannot equip: {exc}", "equipment", 0)
        narrative = _summarize_events(events)
        logger.info("Equip: %s equipped %s to %s", player.name, item_name, slot)
        return (narrative, "equipment", 0)

    match = _UNEQUIP_RE.match(command_text.strip())
    if match:
        item_name = match.group(1).strip().lower().replace(" ", "_")
        # Search equipped slots for matching item.
        target_slot = None
        for slot_name, slot_items in player.equipment.slots.items():
            for equipped in slot_items:
                def_id = getattr(equipped, "item_def_id", "")
                if item_name in def_id.lower() or item_name == slot_name.lower():
                    target_slot = slot_name
                    break
            if target_slot:
                break
        if target_slot is None:
            return (f"No equipped item matching '{item_name}' found.", "equipment", 0)
        events = unequip_item(player, target_slot)
        narrative = _summarize_events(events)
        logger.info("Unequip: %s unequipped %s", player.name, target_slot)
        return (narrative, "equipment", 0)

    return None


# ---------------------------------------------------------------------------
# Handler 2: Inventory (pickup / take / drop)
# ---------------------------------------------------------------------------

_PICKUP_RE = re.compile(r"^(?:pickup|take)\s+(.+)$", re.IGNORECASE)
_DROP_RE = re.compile(r"^drop\s+(.+)$", re.IGNORECASE)


def maybe_handle_inventory_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    player = _player(context)
    if player is None:
        return None

    match = _PICKUP_RE.match(command_text.strip())
    if match:
        item_name = match.group(1).strip()
        item_name_lower = item_name.lower().replace(" ", "_")
        # Search ground / session entities for matching item.
        from engine.kernel.actor_items import ItemStack
        new_item = ItemStack(
            instance_id=f"pickup_{uuid.uuid4().hex[:8]}",
            item_def_id=item_name_lower,
            quantity=1,
        )
        player.inventory.append(new_item)
        logger.info("Pickup: %s picked up %s", player.name, item_name)
        return (f"Picked up {item_name}.", "inventory", 0)

    match = _DROP_RE.match(command_text.strip())
    if match:
        item_name = match.group(1).strip()
        item = _find_inventory_item_by_name(player, item_name)
        if item is None:
            return (f"You don't have '{item_name}' to drop.", "inventory", 0)
        player.inventory.remove(item)
        logger.info("Drop: %s dropped %s", player.name, item_name)
        return (f"Dropped {item_name}.", "inventory", 0)

    return None


# ---------------------------------------------------------------------------
# Handler 3: Crafting
# ---------------------------------------------------------------------------

_CRAFT_RE = re.compile(r"^craft\s+(.+)$", re.IGNORECASE)


def maybe_handle_craft_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    player = _player(context)
    if player is None:
        return None

    match = _CRAFT_RE.match(command_text.strip())
    if not match:
        return None

    recipe_name = match.group(1).strip()
    recipes = recipes_registry()
    found = _fuzzy_match(recipe_name, recipes)
    if found is None:
        return (f"No recipe found for '{recipe_name}'.", "craft", 0)
    recipe_id, recipe = found

    # Check skill requirement.
    skill_name = str(recipe.get("skill", ""))
    skill_dc = int(recipe.get("skill_dc", 0))
    if skill_name and skill_dc > 0:
        player_skill = int(player.skills.get(skill_name, 0))
        if player_skill < skill_dc:
            return (
                f"Crafting {recipe.get('name', recipe_id)} requires {skill_name} "
                f"{skill_dc} (you have {player_skill}).",
                "craft", 0,
            )

    # Check and consume ingredients.
    ingredients = list(recipe.get("ingredients", []))
    for ingredient in ingredients:
        needed_id = str(ingredient.get("item_id", ""))
        needed_qty = int(ingredient.get("quantity", 1))
        count = sum(
            1 for inv_item in player.inventory
            if getattr(inv_item, "item_def_id", "") == needed_id
        )
        if count < needed_qty:
            return (
                f"Missing ingredient: need {needed_qty}x {needed_id} (have {count}).",
                "craft", 0,
            )

    # Consume ingredients.
    for ingredient in ingredients:
        needed_id = str(ingredient.get("item_id", ""))
        needed_qty = int(ingredient.get("quantity", 1))
        removed = 0
        for inv_item in list(player.inventory):
            if removed >= needed_qty:
                break
            if getattr(inv_item, "item_def_id", "") == needed_id:
                player.inventory.remove(inv_item)
                removed += 1

    # Create products.
    from engine.kernel.actor_items import ItemStack
    products = list(recipe.get("products", []))
    product_names = []
    for product in products:
        product_id = str(product.get("item_id", recipe_id))
        product_qty = int(product.get("quantity", 1))
        for _ in range(product_qty):
            new_item = ItemStack(
                instance_id=f"craft_{uuid.uuid4().hex[:8]}",
                item_def_id=product_id,
                quantity=1,
            )
            player.inventory.append(new_item)
        product_names.append(f"{product_qty}x {product_id}")

    xp_reward = int(recipe.get("xp_reward", 0))
    if xp_reward > 0:
        player.raw_payload["xp"] = int(player.raw_payload.get("xp", 0)) + xp_reward

    crafted = ", ".join(product_names)
    logger.info("Craft: %s crafted %s", player.name, crafted)
    return (f"Crafted {crafted}. Gained {xp_reward} XP.", "craft", 2)


# ---------------------------------------------------------------------------
# Handler 4: Rest (short rest / long rest)
# ---------------------------------------------------------------------------

_REST_RE = re.compile(
    r"^(short\s+rest|long\s+rest|rest|sleep)$", re.IGNORECASE,
)


def maybe_handle_rest_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    player = _player(context)
    if player is None:
        return None

    match = _REST_RE.match(command_text.strip())
    if not match:
        return None

    rest_type = match.group(1).lower().strip()
    is_long = rest_type in ("long rest", "sleep")

    current_tick = int(player.raw_payload.get("game_tick", 0))

    if is_long:
        # Check 24h cooldown (24 ticks).
        last_long_rest = int(player.raw_payload.get("last_long_rest_tick", 0))
        if current_tick - last_long_rest < 24 and last_long_rest > 0:
            return (
                "You cannot take a long rest yet. You must wait before resting again.",
                "rest", 0,
            )
        # Full HP restore.
        player.stats["hp"] = int(player.stats.get("max_hp", player.stats.get("hp", 1)))
        # Restore spell points.
        player.raw_payload["spell_points"] = int(
            player.raw_payload.get("max_spell_points", player.raw_payload.get("spell_points", 0))
        )
        # Refresh spellbooks.
        spellbooks_raw = player.raw_payload.get("spellbooks", {})
        for _book_key, book_data in spellbooks_raw.items():
            if isinstance(book_data, dict):
                book = Spellbook.from_dict(book_data)
                rest_refresh_spellbook(book)
                spellbooks_raw[_book_key] = book.to_dict()
            elif isinstance(book_data, Spellbook):
                rest_refresh_spellbook(book_data)
        # Reduce exhaustion.
        exhaustion = int(player.raw_payload.get("exhaustion_level", 0))
        if exhaustion > 0:
            player.raw_payload["exhaustion_level"] = max(0, exhaustion - 1)
        player.raw_payload["last_long_rest_tick"] = current_tick
        logger.info("Long rest: %s fully restored", player.name)
        return (
            f"{player.name} takes a long rest. HP fully restored. Spell slots refreshed.",
            "rest", 8,
        )
    else:
        # Short rest: heal by END modifier + level.
        end_mod = (int(player.stats.get("END", 10)) - 10) // 2
        level = int(player.raw_payload.get("level", 1))
        heal_amount = max(1, end_mod + level)
        current_hp = int(player.stats.get("hp", 0))
        max_hp = int(player.stats.get("max_hp", current_hp))
        player.stats["hp"] = min(max_hp, current_hp + heal_amount)
        # Restore partial spell points (quarter of max).
        max_sp = int(player.raw_payload.get("max_spell_points", 0))
        if max_sp > 0:
            current_sp = int(player.raw_payload.get("spell_points", 0))
            restore = max(1, max_sp // 4)
            player.raw_payload["spell_points"] = min(max_sp, current_sp + restore)
        logger.info("Short rest: %s healed %d hp", player.name, heal_amount)
        return (
            f"{player.name} takes a short rest. Healed {heal_amount} HP.",
            "rest", 1,
        )


# ---------------------------------------------------------------------------
# Handler 5: Spell (non-combat casting)
# ---------------------------------------------------------------------------

_CAST_RE = re.compile(r"^cast\s+(.+?)(?:\s+at\s+(.+))?$", re.IGNORECASE)


def maybe_handle_spell_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    player = _player(context)
    if player is None:
        return None

    match = _CAST_RE.match(command_text.strip())
    if not match:
        return None

    spell_name = match.group(1).strip()
    target_name = match.group(2).strip() if match.group(2) else None

    # Look up spell in registry (may be a map or need list-based fallback).
    registry = spells_registry()
    found = _fuzzy_match(spell_name, registry) if registry else None
    if found is None:
        # Fallback: load raw spell list (entries may lack id fields).
        spell_list = load_registry_list("spells.json", "spells")
        spell_raw = _fuzzy_match_list(spell_name, spell_list)
        if spell_raw is None:
            return (f"Unknown spell '{spell_name}'.", "spell", 0)
        spell_id = str(spell_raw.get("name", spell_name)).lower().replace(" ", "_")
    else:
        spell_id, spell_raw = found

    # Check player has spell points / cost.
    cost = int(spell_raw.get("cost", 0))
    current_sp = int(player.raw_payload.get("spell_points", 0))
    if cost > 0 and current_sp < cost:
        return (
            f"Not enough spell points to cast {spell_raw.get('name', spell_id)} "
            f"(need {cost}, have {current_sp}).",
            "spell", 0,
        )

    # Resolve target actor.
    target_actor = None
    if target_name:
        runtime = context.kernel_runtime or {}
        actors = runtime.get("actors", {})
        for actor in actors.values():
            if hasattr(actor, "identity") and target_name.lower() in actor.identity.display_name.lower():
                target_actor = actor
                break

    # Expend spell points.
    if cost > 0:
        player.raw_payload["spell_points"] = current_sp - cost

    # Build narrative from spell effects.
    effects = list(spell_raw.get("effects", []))
    effect_parts = []
    for effect in effects:
        etype = str(effect.get("type", ""))
        if etype == "damage":
            amount = effect.get("amount", "?")
            dtype = effect.get("damage_type", "")
            recipient = target_name or "the target"
            effect_parts.append(f"deals {amount} {dtype} damage to {recipient}")
        elif etype == "heal":
            amount = effect.get("amount", "?")
            effect_parts.append(f"heals for {amount}")
        elif etype == "buff":
            stat = effect.get("stat", "")
            amount = effect.get("amount", 0)
            effect_parts.append(f"grants +{amount} {stat}")
        else:
            effect_parts.append(f"applies {etype}")

    spell_label = str(spell_raw.get("name", spell_id))
    effect_summary = "; ".join(effect_parts) if effect_parts else "magical energy swirls"
    narrative = f"{player.name} casts {spell_label}. {effect_summary}."

    logger.info("Cast: %s cast %s (cost %d SP)", player.name, spell_label, cost)
    return (narrative, "spell", 1)

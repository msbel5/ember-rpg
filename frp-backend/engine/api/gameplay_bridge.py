"""Gameplay command handlers: equipment, inventory, crafting, rest, and spells.

Each handler follows the maybe_handle pattern — returns
(narrative, command_type, hours_advanced) or None when the
command text does not match.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Optional

from engine.data._shared import items_registry, load_registry_list, recipes_registry, spells_registry
from engine.kernel.gameplay import (
    cast_registry_spell,
    craft_recipe,
    drop_inventory_item,
    equip_inventory_item,
    pickup_ground_item,
    resolve_rest,
    unequip_actor_slot,
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
        slot = _slot_for_item_type(str(raw_def.get("type", "misc")))
        try:
            events = equip_inventory_item(player, item=item, slot=slot)
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
        events = unequip_actor_slot(player, slot=target_slot)
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
        pickup_result = pickup_ground_item(context.session, query=item_name)
        if not pickup_result["success"]:
            if pickup_result.get("reason") == "overweight":
                return (_inventory_add_failure_message(context, str(pickup_result.get("item_name", item_name))), "inventory", 0)
            return (f"There's nothing to pick up here matching '{item_name}'.", "inventory", 0)
        logger.info("Pickup: %s picked up %s", player.name, item_name)
        return (f"Picked up {pickup_result.get('item_name', item_name)}.", "inventory", 0)

    match = _DROP_RE.match(command_text.strip())
    if match:
        item_name = match.group(1).strip()
        if context.session.find_inventory_item(item_name.lower()) is None:
            return (f"You don't have '{item_name}' to drop.", "inventory", 0)
        drop_result = drop_inventory_item(context.session, query=item_name.lower())
        if not drop_result["success"]:
            return (f"You don't have '{item_name}' to drop.", "inventory", 0)
        logger.info("Drop: %s dropped %s", player.name, item_name)
        return (f"Dropped {drop_result.get('item_name', item_name)}.", "inventory", 0)

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

    crafted_result = craft_recipe(player, recipe=recipe, item_catalog=items_registry(), instance_prefix="craft")
    if not crafted_result.get("success", False):
        if crafted_result.get("reason") == "skill_too_low":
            return (
                f"Crafting {recipe.get('name', recipe_id)} requires {crafted_result['skill']} "
                f"{crafted_result['required']} (you have {crafted_result['actual']}).",
                "craft", 0,
            )
        if crafted_result.get("reason") == "missing_ingredient":
            return (
                f"Missing ingredient: need {crafted_result['required']}x {crafted_result['item_id']} "
                f"(have {crafted_result['available']}).",
                "craft", 0,
            )
        return (f"Cannot craft {recipe.get('name', recipe_id)}.", "craft", 0)
    products = list(recipe.get("products", []))
    product_names = [f"{int(product.get('quantity', 1))}x {str(product.get('item_id', recipe_id))}" for product in products]
    xp_reward = int(crafted_result["xp_reward"])

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

    rest_result = resolve_rest(player, long_rest=is_long, current_tick=current_tick)
    if not rest_result.get("success", False):
        return (
            "You cannot take a long rest yet. You must wait before resting again.",
            "rest", 0,
        )

    if is_long:
        logger.info("Long rest: %s fully restored", player.name)
        return (
            f"{player.name} takes a long rest. HP fully restored. Spell slots refreshed.",
            "rest", 8,
        )

    heal_amount = int(rest_result["healed"])
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

    # Resolve target actor.
    target_actor = _resolve_spell_target(context, target_name, spell_raw)

    cast_result = cast_registry_spell(
        player,
        spell_id=spell_id,
        spell_data=spell_raw,
        target=target_actor,
        current_tick=int(player.raw_payload.get("game_tick", 0)),
    )
    cost = int(cast_result.get("cost", spell_raw.get("cost", 0)))
    current_sp = player.spell_points
    if not cast_result.get("success", False) and cast_result.get("reason") == "insufficient_spell_points":
        return (
            f"Not enough spell points to cast {cast_result.get('spell_label', spell_raw.get('name', spell_id))} "
            f"(need {cost}, have {current_sp}).",
            "spell", 0,
        )
    if not cast_result.get("success", False) and cast_result.get("reason"):
        return (f"Cannot cast {cast_result.get('spell_label', spell_raw.get('name', spell_id))}: {cast_result['reason']}.", "spell", 0)
    effects = list(cast_result["applied"])
    effect_parts = []
    for effect in effects:
        etype = str(effect.get("type", ""))
        if etype == "damage":
            recipient = effect.get("target", target_name or "the target")
            effect_parts.append(f"deals {effect.get('amount', '?')} damage to {recipient}")
        elif etype == "heal":
            effect_parts.append(f"heals {effect.get('target', 'the target')} for {effect.get('amount', '?')}")
        elif etype == "buff":
            effect_parts.append(f"empowers {effect.get('target', 'the target')}")
        elif etype == "status":
            effect_parts.append(f"affects {effect.get('target', 'the target')} with a status effect")
        else:
            effect_parts.append(f"applies {etype}")

    spell_label = str(spell_raw.get("name", spell_id))
    effect_summary = "; ".join(effect_parts) if effect_parts else "magical energy swirls"
    narrative = f"{player.name} casts {spell_label}. {effect_summary}."

    logger.info("Cast: %s cast %s (cost %d SP)", player.name, spell_label, cost)
    return (narrative, "spell", 1)


def _resolve_spell_target(
    context: "CampaignContext",
    target_name: str | None,
    spell_raw: dict[str, Any],
):
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    normalized_target = str(target_name or "").strip().lower()
    if normalized_target in {"self", "me", "myself", context.session.player.name.lower()}:
        return _player(context)
    if normalized_target:
        for actor in actors.values():
            if not hasattr(actor, "identity"):
                continue
            display_name = str(actor.identity.display_name).lower()
            actor_id = str(actor.identity.actor_id).lower()
            if normalized_target in display_name or normalized_target == actor_id:
                return actor
    hostile = str(spell_raw.get("target_type", "single")).lower() != "self"
    if hostile:
        for actor_id, actor in actors.items():
            if actor_id == "player":
                continue
            if getattr(actor, "alive", True):
                return actor
    return _player(context) if str(spell_raw.get("target_type", "single")).lower() == "self" else None


def _inventory_add_failure_message(context: "CampaignContext", item_name: str) -> str:
    error = dict(context.session.narration_context.pop("_last_add_item_error", {}) or {})
    if error.get("reason") == "overweight":
        return (
            f"{item_name} is too heavy to carry right now. It would bring you to "
            f"{float(error.get('projected_weight', 0.0)):.1f}/{float(error.get('max_weight', 0.0)):.1f} kg. "
            "You wrench your back trying to lift it."
        )
    return f"No room for {item_name}. Your containers are full."

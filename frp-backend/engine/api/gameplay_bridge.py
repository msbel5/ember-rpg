"""Gameplay command handlers: equipment, inventory, item use, crafting, progression, rest, and spells.

Each handler follows the maybe_handle pattern — returns
(narrative, command_type, hours_advanced) or None when the
command text does not match.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Optional

from engine.data.classes import get_skill_stat_map
from engine.data._shared import items_registry, load_registry_list, recipes_registry, spells_registry
from engine.data.runtime import get_class_abilities
from engine.kernel.effects import EffectDef
from engine.kernel.gameplay import (
    cast_registry_spell,
    craft_recipe,
    drop_inventory_item,
    equip_inventory_item,
    pickup_ground_item,
    resolve_rest,
    unequip_actor_slot,
)
from engine.kernel.items import ItemDef as KernelItemDef, ItemInstance, use_item
from engine.kernel.progression import ProgressionState
from engine.world.crafting import CraftingSystem

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
        display_name = str(getattr(item, "payload", {}).get("name", def_id)).lower().replace(" ", "_")
        if (
            def_id == name_lower
            or name_lower in def_id.lower()
            or display_name == name_lower
            or name_lower in display_name
        ):
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


def _runtime_item_source(item: Any) -> dict[str, Any]:
    payload = dict(getattr(item, "payload", {}) or {})
    source = dict(_item_def_from_registry(getattr(item, "item_def_id", "")) or {})
    return {**source, **payload}


def _runtime_item_label(item: Any, source: dict[str, Any] | None = None) -> str:
    entry = source or _runtime_item_source(item)
    label = str(entry.get("name", getattr(item, "item_def_id", "item"))).strip()
    return label or str(getattr(item, "item_def_id", "item")).replace("_", " ").title()


def _runtime_item_type(item: Any, source: dict[str, Any] | None = None) -> str:
    entry = source or _runtime_item_source(item)
    raw_type = str(entry.get("type", "misc")).strip().lower()
    item_id = str(getattr(item, "item_def_id", entry.get("id", ""))).lower()
    label = _runtime_item_label(item, entry).lower()
    if "wand" in item_id or "wand" in label:
        return "wand"
    if "scroll" in item_id or "scroll" in label:
        return "scroll"
    if raw_type == "consumable":
        return "potion"
    if raw_type == "food":
        return "potion"
    return raw_type or "misc"


def _runtime_item_enchantment(item: Any, source: dict[str, Any] | None = None) -> int:
    entry = source or _runtime_item_source(item)
    if entry.get("enchantment") is not None:
        return int(entry.get("enchantment", 0) or 0)
    name = _runtime_item_label(item, entry).lower()
    match = re.search(r"\+(\d+)", name)
    if match is not None:
        return int(match.group(1))
    bonus_fields = (
        entry.get("attack_bonus"),
        entry.get("armor_bonus"),
        entry.get("damage_bonus"),
    )
    for value in bonus_fields:
        if value not in (None, ""):
            return max(0, int(value))
    return 0


def _runtime_item_magical(item: Any, source: dict[str, Any] | None = None) -> bool:
    entry = source or _runtime_item_source(item)
    item_id = str(getattr(item, "item_def_id", entry.get("id", ""))).lower()
    label = _runtime_item_label(item, entry).lower()
    if bool(entry.get("magical")):
        return True
    if _runtime_item_enchantment(item, entry) > 0:
        return True
    if entry.get("effects"):
        return True
    if any(keyword in item_id or keyword in label for keyword in ("wand", "amulet", "ring", "cloak")):
        return True
    return False


def _runtime_item_identified(item: Any, source: dict[str, Any] | None = None) -> bool:
    entry = source or _runtime_item_source(item)
    if "identified" in entry:
        return bool(entry.get("identified"))
    lore_to_identify = int(entry.get("lore_to_identify", 0) or 0)
    return lore_to_identify <= 0


def _runtime_item_charges(item: Any, source: dict[str, Any] | None = None) -> int | None:
    entry = source or _runtime_item_source(item)
    if entry.get("charges") is not None:
        return int(entry.get("charges", -1))
    if entry.get("uses") is not None:
        return int(entry.get("uses", -1))
    item_type = _runtime_item_type(item, entry)
    if item_type in {"potion", "scroll"}:
        return 1
    if item_type == "wand":
        return 7
    return None


def inventory_item_row(item: Any) -> dict[str, Any]:
    source = _runtime_item_source(item)
    charges = _runtime_item_charges(item, source)
    quantity = max(1, int(getattr(item, "quantity", source.get("quantity", source.get("qty", 1)) or 1)))
    return {
        "id": str(getattr(item, "item_def_id", source.get("id", ""))),
        "name": _runtime_item_label(item, source),
        "type": _runtime_item_type(item, source),
        "quantity": quantity,
        "qty": quantity,
        "identified": _runtime_item_identified(item, source),
        "charges": charges,
        "enchantment": _runtime_item_enchantment(item, source),
        "magical": _runtime_item_magical(item, source),
    }


def _is_usable_runtime_item(item: Any, source: dict[str, Any] | None = None) -> bool:
    item_type = _runtime_item_type(item, source)
    return item_type in {"potion", "scroll", "wand"}


def _item_effect_id(item_def_id: str, index: int, effect: dict[str, Any]) -> str:
    suffix = str(effect.get("id") or effect.get("type") or f"effect_{index}").strip().lower().replace(" ", "_")
    return f"{item_def_id}_{index}_{suffix}"


def _effect_def_from_item_effect(effect_id: str, effect: dict[str, Any]) -> EffectDef | None:
    effect_type = str(effect.get("type", "")).strip().lower()
    amount = _resolve_effect_amount(effect.get("amount", effect.get("bonus", 0)))
    if effect_type == "heal":
        return EffectDef(
            effect_def_id=effect_id,
            label="Healing",
            category="healing",
            healing_per_tick=amount,
            timing_mode="instant",
            base_duration_ticks=0,
        )
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
    if effect_type == "buff":
        duration = int(effect.get("duration", 3) or 3)
        return EffectDef(
            effect_def_id=effect_id,
            label=str(effect.get("stat", "buff")).upper(),
            category="stat_mod",
            target_stat=str(effect.get("stat", "")).upper(),
            modifier_type="flat",
            modifier_value=float(effect.get("bonus", effect.get("amount", 0)) or 0),
            timing_mode="duration",
            base_duration_ticks=max(1, duration),
        )
    return None


def _build_item_effect_registry(item: Any, source: dict[str, Any]) -> dict[str, EffectDef]:
    if not _is_usable_runtime_item(item, source):
        return {}
    effects: list[dict[str, Any]] = []
    for effect in source.get("effects", []):
        if isinstance(effect, dict):
            effects.append(dict(effect))
    if not effects and source.get("heal") is not None:
        effects.append({"type": "heal", "amount": int(source.get("heal", 0) or 0)})
    registry: dict[str, EffectDef] = {}
    item_def_id = str(getattr(item, "item_def_id", source.get("id", "item")))
    for index, effect in enumerate(effects):
        effect_def = _effect_def_from_item_effect(_item_effect_id(item_def_id, index, effect), effect)
        if effect_def is not None:
            registry[effect_def.effect_def_id] = effect_def
    return registry


def _kernel_item_def(item: Any) -> tuple[KernelItemDef, dict[str, EffectDef]]:
    source = _runtime_item_source(item)
    effect_registry = _build_item_effect_registry(item, source)
    flags = [str(flag) for flag in source.get("flags", [])]
    if _runtime_item_magical(item, source) and "magical" not in {flag.lower() for flag in flags}:
        flags.append("magical")
    item_def = KernelItemDef(
        item_def_id=str(getattr(item, "item_def_id", source.get("id", "item"))),
        label=_runtime_item_label(item, source),
        item_type=_runtime_item_type(item, source),
        item_category=str(source.get("type", _runtime_item_type(item, source))),
        weight=int(float(source.get("weight", 0) or 0)),
        base_price=int(source.get("value", 0) or 0),
        enchantment=_runtime_item_enchantment(item, source),
        use_effect_ids=list(effect_registry.keys()),
        lore_to_identify=int(source.get("lore_to_identify", 0) or 0),
        flags=flags,
        description=str(source.get("description", "")),
        identified_description=str(source.get("identified_description", source.get("description", ""))),
    )
    return item_def, effect_registry


def _kernel_item_instance(item: Any, item_def: KernelItemDef) -> ItemInstance:
    source = _runtime_item_source(item)
    charges = _runtime_item_charges(item, source)
    return ItemInstance(
        instance_id=str(getattr(item, "instance_id", getattr(item, "item_def_id", "item"))),
        item_def_id=str(getattr(item, "item_def_id", item_def.item_def_id)),
        material_id=str(getattr(item, "material_id", "iron") or "iron"),
        quality=int(getattr(item, "quality", 0) or 0),
        wear=int(getattr(item, "wear", 0) or 0),
        max_wear=100,
        identified=_runtime_item_identified(item, source),
        charges=int(charges) if charges is not None else -1,
        stack_count=max(1, int(getattr(item, "quantity", 1) or 1)),
        equipped_slot=str(getattr(item, "payload", {}).get("equipped_slot", "") or "") or None,
    )


def _resolve_item_target(context: "CampaignContext", target_name: str | None) -> Any:
    player = _player(context)
    if not str(target_name or "").strip():
        return player
    normalized_target = str(target_name).strip().lower()
    if player is not None and normalized_target in {"self", "me", "myself", player.name.lower()}:
        return player
    runtime = context.kernel_runtime or {}
    for actor in runtime.get("actors", {}).values():
        identity = getattr(actor, "identity", None)
        if identity is None:
            continue
        actor_id = str(identity.actor_id).lower()
        display_name = str(identity.display_name).lower()
        if normalized_target == actor_id or normalized_target in display_name:
            return actor
    return None


def _sync_runtime_item_after_use(player: "ActorRecord", item: Any, item_def: KernelItemDef, item_state: ItemInstance, *, destroyed: bool) -> None:
    payload = dict(getattr(item, "payload", {}) or {})
    payload["identified"] = bool(item_state.identified)
    payload["enchantment"] = int(item_def.enchantment)
    payload["magical"] = _runtime_item_magical(item, payload)
    if destroyed:
        current_quantity = max(1, int(getattr(item, "quantity", 1) or 1))
        if current_quantity <= 1:
            if item in player.inventory:
                player.inventory.remove(item)
            return
        item.quantity = current_quantity - 1
        payload["quantity"] = int(item.quantity)
        payload["qty"] = int(item.quantity)
        remaining_charges = _runtime_item_charges(item, payload)
        if remaining_charges is not None:
            payload["charges"] = int(remaining_charges)
    else:
        if item_state.charges >= 0:
            payload["charges"] = int(item_state.charges)
        elif "charges" in payload:
            payload.pop("charges", None)
        payload["quantity"] = max(1, int(getattr(item, "quantity", 1) or 1))
        payload["qty"] = payload["quantity"]
    item.payload = payload


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


def _progression_state(player: "ActorRecord") -> ProgressionState:
    class_id = str(player.raw_payload.get("class_name", "warrior")).lower()
    raw_progression = player.raw_payload.get("progression")
    state: ProgressionState | None = None
    if isinstance(raw_progression, dict):
        try:
            state = ProgressionState.from_dict(raw_progression)
        except Exception:  # pragma: no cover - corrupted save data should fall back safely
            state = None
    if state is None:
        state = ProgressionState(
            actor_id=player.identity.actor_id,
            xp=int(player.raw_payload.get("xp", 0)),
            level=int(player.raw_payload.get("level", 1)),
            classes=[class_id],
            class_levels={class_id: int(player.raw_payload.get("level", 1))},
            bab=int(player.raw_payload.get("bab", 0)),
            saves={str(key): int(value) for key, value in dict(player.raw_payload.get("saves", {})).items()},
        )
    state.actor_id = player.identity.actor_id
    state.xp = int(player.raw_payload.get("xp", state.xp))
    state.level = int(player.raw_payload.get("level", state.level or 1))
    state.bab = int(player.raw_payload.get("bab", state.bab))
    state.saves = {str(key): int(value) for key, value in dict(player.raw_payload.get("saves", state.saves)).items()}
    if not state.classes:
        state.classes = [class_id]
    elif class_id not in state.classes:
        state.classes.append(class_id)
    if not state.class_levels:
        state.class_levels = {class_id: state.level}
    else:
        state.class_levels.setdefault(class_id, state.level)
    return state


def _store_progression_state(player: "ActorRecord", state: ProgressionState) -> None:
    player.raw_payload["progression"] = state.to_dict()


def _class_ability_summary(player: "ActorRecord") -> list[dict[str, Any]]:
    class_id = str(player.raw_payload.get("class_name", "warrior")).lower()
    level = int(player.raw_payload.get("level", 1))
    abilities = []
    for ability in get_class_abilities().get(class_id, []):
        entry = dict(ability)
        entry["id"] = str(entry.get("name", "")).strip().lower().replace(" ", "_")
        entry["required_level"] = int(entry.get("required_level", 1) or 1)
        entry["unlocked"] = level >= entry["required_level"]
        abilities.append(entry)
    return abilities


def _resolve_skill_id(player: "ActorRecord", query: str) -> str | None:
    normalized = str(query).strip().lower().replace(" ", "_")
    if not normalized:
        return None
    candidates = {
        *get_skill_stat_map().keys(),
        *player.skills.keys(),
        *player.skill_proficiencies,
        *player.expertise_skills,
    }
    if normalized in candidates:
        return normalized
    for skill_id in sorted(candidates):
        label = skill_id.replace("_", " ")
        if normalized in skill_id or normalized in label:
            return skill_id
    return None


def _progression_summary(player: "ActorRecord") -> str:
    state = _progression_state(player)
    unlocked = [ability["name"] for ability in _class_ability_summary(player) if ability.get("unlocked")]
    unlocked_text = ", ".join(unlocked[:3]) if unlocked else "none yet"
    return (
        f"Level {int(player.raw_payload.get('level', 1))} {str(player.raw_payload.get('class_name', 'warrior')).title()}. "
        f"{state.skill_points_available} skill points, "
        f"{state.proficiency_points_available} proficiency points, "
        f"{state.ability_increases_available} ability increases available. "
        f"Unlocked class abilities: {unlocked_text}."
    )


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
        pickup_result = pickup_ground_item(context, query=item_name)
        if not pickup_result["success"]:
            if pickup_result.get("reason") == "overweight":
                return (_inventory_add_failure_message(context, str(pickup_result.get("item_name", item_name))), "inventory", 0)
            return (f"There's nothing to pick up here matching '{item_name}'.", "inventory", 0)
        logger.info("Pickup: %s picked up %s", player.name, item_name)
        return (f"Picked up {pickup_result.get('item_name', item_name)}.", "inventory", 0)

    match = _DROP_RE.match(command_text.strip())
    if match:
        item_name = match.group(1).strip()
        if context.find_inventory_item(item_name.lower()) is None:
            return (f"You don't have '{item_name}' to drop.", "inventory", 0)
        drop_result = drop_inventory_item(context, query=item_name.lower())
        if not drop_result["success"]:
            return (f"You don't have '{item_name}' to drop.", "inventory", 0)
        logger.info("Drop: %s dropped %s", player.name, item_name)
        return (f"Dropped {drop_result.get('item_name', item_name)}.", "inventory", 0)

    return None


# ---------------------------------------------------------------------------
# Handler 3: Item use
# ---------------------------------------------------------------------------

_USE_ITEM_RE = re.compile(r"^use\s+(.+?)(?:\s+on\s+(.+))?$", re.IGNORECASE)


def maybe_handle_item_use_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    player = _player(context)
    if player is None:
        return None

    match = _USE_ITEM_RE.match(command_text.strip())
    if not match:
        return None

    item_name = match.group(1).strip()
    target_name = match.group(2).strip() if match.group(2) else None
    item = _find_inventory_item_by_name(player, item_name)
    if item is None:
        known = _fuzzy_match(item_name, items_registry())
        if known is not None:
            return (f"You don't have '{item_name}' in your inventory.", "inventory", 0)
        return (f"Unknown item '{item_name}'.", "inventory", 0)

    item_def, effect_registry = _kernel_item_def(item)
    if not item_def.use_effect_ids:
        return (f"{item_def.label} cannot be used this way.", "inventory", 0)

    target = _resolve_item_target(context, target_name)
    if target is None:
        return (f"No valid target found for '{target_name}'.", "inventory", 0)

    item_state = _kernel_item_instance(item, item_def)
    if item_state.charges == 0:
        return (f"{item_def.label} has no charges remaining.", "inventory", 0)

    previous_registry = dict(player.raw_payload.get("effect_registry", {}))
    player.raw_payload["effect_registry"] = {**previous_registry, **effect_registry}
    try:
        result = use_item(player, item_state, item_def, target)
    except ValueError as exc:
        return (f"Cannot use {item_def.label}: {exc}.", "inventory", 0)
    finally:
        player.raw_payload["effect_registry"] = previous_registry

    _sync_runtime_item_after_use(player, item, item_def, item_state, destroyed=bool(result.get("destroyed", False)))
    effect_text = ", ".join(str(effect_id).replace("_", " ") for effect_id in result.get("effects", []))
    if not effect_text:
        effect_text = "arcane energy pulses through it"
    target_label = "yourself" if target is player else str(getattr(getattr(target, "identity", None), "display_name", "the target"))
    if bool(result.get("destroyed", False)):
        return (f"Used {item_def.label} on {target_label}. {effect_text}. It is consumed.", "inventory", 0)
    if int(result.get("charges_remaining", -1)) >= 0:
        return (
            f"Used {item_def.label} on {target_label}. {effect_text}. "
            f"{int(result.get('charges_remaining', 0))} charges remain.",
            "inventory",
            0,
        )
    return (f"Used {item_def.label} on {target_label}. {effect_text}.", "inventory", 0)


# ---------------------------------------------------------------------------
# Handler 4: Crafting
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

    workstation_type = str(recipe.get("workstation", "any"))
    workstation = CraftingSystem.find_nearby_workstation(
        getattr(context, "spatial_index", None),
        (int(context.position[0]), int(context.position[1])),
        workstation_type,
    )
    if not workstation:
        workstation_name = workstation_type.replace("_", " ")
        return (
            f"You need a nearby {workstation_name} to craft {recipe.get('name', recipe_id)}.",
            "craft",
            0,
        )

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
# Handler 5: Progression spending
# ---------------------------------------------------------------------------

_PROGRESSION_RE = re.compile(r"^(?:progression|character\s+progression)$", re.IGNORECASE)
_TRAIN_RE = re.compile(r"^train\s+(.+)$", re.IGNORECASE)
_PROFICIENCY_RE = re.compile(r"^proficiency\s+(.+)$", re.IGNORECASE)
_EXPERTISE_RE = re.compile(r"^expertise\s+(.+)$", re.IGNORECASE)
_RAISE_RE = re.compile(r"^raise\s+(mig|agi|end|mnd|ins|pre)$", re.IGNORECASE)


def maybe_handle_progression_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    player = _player(context)
    if player is None:
        return None

    text = command_text.strip()
    if _PROGRESSION_RE.match(text):
        return (_progression_summary(player), "progression", 0)

    state = _progression_state(player)

    match = _TRAIN_RE.match(text)
    if match:
        skill_id = _resolve_skill_id(player, match.group(1))
        if skill_id is None:
            return (f"Unknown skill '{match.group(1).strip()}'.", "progression", 0)
        if state.skill_points_available <= 0:
            return ("No skill points available to spend.", "progression", 0)
        player.skills[skill_id] = int(player.skills.get(skill_id, 0)) + 1
        state.skill_points_available -= 1
        state.skill_levels[skill_id] = int(player.skills.get(skill_id, 0))
        _store_progression_state(player, state)
        return (
            f"Trained {skill_id.replace('_', ' ').title()} to {player.skills[skill_id]}. "
            f"{state.skill_points_available} skill points remain.",
            "progression",
            0,
        )

    match = _PROFICIENCY_RE.match(text)
    if match:
        skill_id = _resolve_skill_id(player, match.group(1))
        if skill_id is None:
            return (f"Unknown skill '{match.group(1).strip()}'.", "progression", 0)
        if skill_id in player.skill_proficiencies:
            return (f"You are already proficient in {skill_id.replace('_', ' ')}.", "progression", 0)
        if state.proficiency_points_available <= 0:
            return ("No proficiency points available to spend.", "progression", 0)
        player.raw_payload["skill_proficiencies"] = sorted({*player.skill_proficiencies, skill_id})
        state.proficiency_points_available -= 1
        _store_progression_state(player, state)
        return (
            f"Gained proficiency in {skill_id.replace('_', ' ').title()}. "
            f"{state.proficiency_points_available} proficiency points remain.",
            "progression",
            0,
        )

    match = _EXPERTISE_RE.match(text)
    if match:
        skill_id = _resolve_skill_id(player, match.group(1))
        if skill_id is None:
            return (f"Unknown skill '{match.group(1).strip()}'.", "progression", 0)
        if skill_id in player.expertise_skills:
            return (f"You already have expertise in {skill_id.replace('_', ' ')}.", "progression", 0)
        if skill_id not in player.skill_proficiencies:
            return (f"You need proficiency in {skill_id.replace('_', ' ')} before gaining expertise.", "progression", 0)
        if state.proficiency_points_available <= 0:
            return ("No proficiency points available to spend.", "progression", 0)
        player.raw_payload["expertise_skills"] = sorted({*player.expertise_skills, skill_id})
        state.proficiency_points_available -= 1
        _store_progression_state(player, state)
        return (
            f"Gained expertise in {skill_id.replace('_', ' ').title()}. "
            f"{state.proficiency_points_available} proficiency points remain.",
            "progression",
            0,
        )

    match = _RAISE_RE.match(text)
    if match:
        ability = match.group(1).upper()
        if state.ability_increases_available <= 0:
            return ("No ability increases available to spend.", "progression", 0)
        player.stats[ability] = int(player.stats.get(ability, 10)) + 1
        state.ability_increases_available -= 1
        _store_progression_state(player, state)
        new_modifier = (int(player.stats.get(ability, 10)) - 10) // 2
        return (
            f"Raised {ability} to {int(player.stats.get(ability, 10))} "
            f"(modifier {new_modifier:+d}). {state.ability_increases_available} ability increases remain.",
            "progression",
            0,
        )

    return None


# ---------------------------------------------------------------------------
# Handler 6: Rest (short rest / long rest)
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
# Handler 7: Spell (non-combat casting)
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
    if normalized_target in {"self", "me", "myself", context.player.name.lower()}:
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
    error = dict(context.narration_context.pop("_last_add_item_error", {}) or {})
    if error.get("reason") == "overweight":
        return (
            f"{item_name} is too heavy to carry right now. It would bring you to "
            f"{float(error.get('projected_weight', 0.0)):.1f}/{float(error.get('max_weight', 0.0)):.1f} kg. "
            "You wrench your back trying to lift it."
        )
    return f"No room for {item_name}. Your containers are full."

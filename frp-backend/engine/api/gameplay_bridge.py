"""Gameplay command handlers: equipment, inventory, item use, crafting, progression, rest, and spells.

Each handler follows the maybe_handle pattern — returns
(narrative, command_type, hours_advanced) or None when the
command text does not match.
"""
from __future__ import annotations

import logging
import re
from random import Random
from typing import TYPE_CHECKING, Any, Optional

from engine.data.classes import get_skill_stat_map
from engine.data._shared import items_registry, load_registry_list, recipes_registry, spells_registry
from engine.data.runtime import get_class_abilities
from engine.api.campaign.actor_query import resolve_live_actor_query
from engine.kernel.effects import EffectDef
from engine.kernel.gameplay import (
    cast_registry_spell,
    craft_recipe,
    drop_inventory_item,
    equip_inventory_item,
    memorize_registry_spell,
    pickup_ground_item,
    resolve_rest,
    unequip_actor_slot,
)
from engine.kernel.actor_items import (
    candidate_canonical_slots_for_item_payload,
    canonical_equipment_slot,
    canonical_slot_for_item_payload,
    canonical_slot_query_aliases,
    preferred_storage_slot_for_item,
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


def _slot_for_item_type(item_def_id: str, raw_def: dict[str, Any], occupied_slots: set[str]) -> tuple[str | None, str | None]:
    payload = {"id": item_def_id, "item_def_id": item_def_id, **dict(raw_def or {})}
    canonical_slot = canonical_slot_for_item_payload(payload, occupied_slots=occupied_slots)
    if canonical_slot is None:
        return None, None
    storage_slot = preferred_storage_slot_for_item(canonical_slot, payload)
    return canonical_slot, storage_slot


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


def _resolve_item_target(context: "CampaignContext", target_name: str | None) -> tuple[Any, str | None]:
    player = _player(context)
    if not str(target_name or "").strip():
        return player, None
    normalized_target = str(target_name).strip().lower()
    if player is not None and normalized_target in {"self", "me", "myself", player.name.lower()}:
        return player, None
    runtime = context.kernel_runtime or {}
    resolved = resolve_live_actor_query(runtime.get("actors", {}), normalized_target, include_player=True)
    return resolved.actor, resolved.error


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
        display_slot = str(ev.get("canonical_slot") or ev.get("slot", "slot"))
        if ev_type == "equipped":
            parts.append(f"Equipped item to {display_slot}.")
        elif ev_type == "unequipped":
            parts.append(f"Unequipped item from {display_slot}.")
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


_IMPLEMENTED_ACTIVE_CLASS_ABILITIES = {
    "second_wind",
    "arcane_recovery",
    "channel_divinity",
    "greater_heal",
}
_LONG_REST_RESET_ABILITIES = {
    "second_wind",
    "arcane_recovery",
    "channel_divinity",
}


def _class_ability_id(ability: dict[str, Any]) -> str:
    return str(ability.get("name", "")).strip().lower().replace(" ", "_")


def _class_ability_state(player: "ActorRecord") -> dict[str, dict[str, Any]]:
    raw = player.raw_payload.get("class_ability_state", {})
    if not isinstance(raw, dict):
        return {}
    state: dict[str, dict[str, Any]] = {}
    for ability_id, entry in raw.items():
        if isinstance(entry, dict):
            state[str(ability_id)] = dict(entry)
    return state


def _store_class_ability_state(player: "ActorRecord", state: dict[str, dict[str, Any]]) -> None:
    player.raw_payload["class_ability_state"] = {str(key): dict(value) for key, value in state.items() if isinstance(value, dict)}


def _ability_restore_on_long_rest(player: "ActorRecord") -> None:
    state = _class_ability_state(player)
    for ability_id in _LONG_REST_RESET_ABILITIES:
        state.pop(ability_id, None)
    if state:
        _store_class_ability_state(player, state)
    else:
        player.raw_payload.pop("class_ability_state", None)


def _class_ability_summary(player: "ActorRecord") -> list[dict[str, Any]]:
    class_id = str(player.raw_payload.get("class_name", "warrior")).lower()
    level = int(player.raw_payload.get("level", 1))
    state = _class_ability_state(player)
    abilities = []
    for ability in get_class_abilities().get(class_id, []):
        entry = dict(ability)
        ability_id = _class_ability_id(entry)
        entry["id"] = ability_id
        entry["required_level"] = int(entry.get("required_level", 1) or 1)
        entry["unlocked"] = level >= entry["required_level"]
        entry["active"] = not bool(entry.get("passive", False))
        entry["implemented"] = ability_id in _IMPLEMENTED_ACTIVE_CLASS_ABILITIES
        entry["resource_cost"] = int(entry.get("cost", 0) or 0)
        if ability_id in _LONG_REST_RESET_ABILITIES:
            entry["uses_remaining"] = 0 if bool(state.get(ability_id, {}).get("used")) else 1
        else:
            entry["uses_remaining"] = None
        if not entry["unlocked"]:
            entry["runtime_status"] = "locked"
        elif not entry["active"]:
            entry["runtime_status"] = "passive_not_implemented"
        elif not entry["implemented"]:
            entry["runtime_status"] = "not_yet_implemented"
        elif ability_id in _LONG_REST_RESET_ABILITIES and entry["uses_remaining"] == 0:
            entry["runtime_status"] = "expended_until_long_rest"
        elif ability_id == "greater_heal" and int(player.spell_points) < entry["resource_cost"]:
            entry["runtime_status"] = "insufficient_spell_points"
        else:
            entry["runtime_status"] = "ready"
        abilities.append(entry)
    return abilities


def progression_class_abilities(player: "ActorRecord") -> list[dict[str, Any]]:
    return _class_ability_summary(player)


def _resolve_class_ability(player: "ActorRecord", query: str) -> dict[str, Any] | None:
    normalized = str(query).strip().lower().replace(" ", "_")
    if not normalized:
        return None
    for ability in _class_ability_summary(player):
        ability_id = str(ability.get("id", ""))
        ability_name = str(ability.get("name", "")).lower()
        if normalized == ability_id or normalized == ability_name.replace(" ", "_"):
            return ability
    for ability in _class_ability_summary(player):
        ability_id = str(ability.get("id", ""))
        ability_name = str(ability.get("name", "")).lower()
        if normalized in ability_id or normalized in ability_name:
            return ability
    return None


def _roll_dice(seed: int, count: int, sides: int, modifier: int = 0) -> int:
    rng = Random(int(seed))
    total = int(modifier)
    for _ in range(max(0, int(count))):
        total += rng.randint(1, max(1, int(sides)))
    return max(0, total)


def _heal_actor(actor: "ActorRecord", amount: int) -> int:
    before = int(actor.hp)
    actor.hp = min(int(actor.max_hp), int(actor.hp) + max(0, int(amount)))
    return max(0, int(actor.hp) - before)


def _active_party_targets(context: "CampaignContext") -> list["ActorRecord"]:
    from engine.api.campaign.party_bridge import party_member_ids

    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    targets: list["ActorRecord"] = []
    for actor_id in party_member_ids(context):
        actor = actors.get(actor_id)
        if actor is not None and getattr(actor, "alive", True):
            targets.append(actor)
    return targets


def _abilities_summary(player: "ActorRecord") -> str:
    unlocked = [ability for ability in _class_ability_summary(player) if ability.get("unlocked")]
    if not unlocked:
        return "No class abilities are unlocked yet."
    parts: list[str] = []
    for ability in unlocked:
        status = str(ability.get("runtime_status", "unknown")).replace("_", " ")
        parts.append(f"{ability['name']} ({status})")
    return "Unlocked abilities: " + "; ".join(parts) + "."


def _use_class_ability(
    context: "CampaignContext",
    player: "ActorRecord",
    ability: dict[str, Any],
    target_name: str | None,
) -> tuple[str, str, int]:
    ability_id = str(ability.get("id", ""))
    ability_name = str(ability.get("name", "That ability"))
    if not bool(ability.get("unlocked")):
        return (f"{ability_name} is not unlocked yet.", "progression", 0)
    if not bool(ability.get("active")):
        return (f"{ability_name} is passive and not directly usable.", "progression", 0)
    if not bool(ability.get("implemented")):
        return (f"{ability_name} is not yet implemented in runtime.", "progression", 0)

    state = _class_ability_state(player)
    if ability_id in _LONG_REST_RESET_ABILITIES and bool(state.get(ability_id, {}).get("used")):
        return (f"{ability_name} has already been used since your last long rest.", "progression", 0)

    seed = int(player.raw_payload.get("game_tick", 0)) + int(player.level)
    target, target_error = _resolve_item_target(context, target_name)
    if target_error:
        return (target_error, "progression", 0)

    if ability_id == "second_wind":
        healed = _heal_actor(player, _roll_dice(seed, 1, 10, int(player.level)))
        state[ability_id] = {"used": True}
        _store_class_ability_state(player, state)
        return (f"{player.name} uses Second Wind and regains {healed} HP.", "progression", 0)

    if ability_id == "arcane_recovery":
        restored = max(1, int(player.level) // 2)
        before = int(player.spell_points)
        player.spell_points = min(int(player.max_spell_points), int(player.spell_points) + restored)
        gained = max(0, int(player.spell_points) - before)
        state[ability_id] = {"used": True}
        _store_class_ability_state(player, state)
        return (f"{player.name} uses Arcane Recovery and restores {gained} spell points.", "progression", 0)

    if ability_id == "channel_divinity":
        allies = _active_party_targets(context)
        if not allies:
            return ("No active allies are available for Channel Divinity.", "progression", 0)
        amount = _roll_dice(seed, 2, 6)
        healed_parts: list[str] = []
        for ally in allies:
            healed_parts.append(f"{ally.name} +{_heal_actor(ally, amount)} HP")
        state[ability_id] = {"used": True}
        _store_class_ability_state(player, state)
        return (f"{player.name} invokes Channel Divinity. " + ", ".join(healed_parts) + ".", "progression", 0)

    if ability_id == "greater_heal":
        if target_name is None or target is None:
            return ("Greater Heal requires a valid target.", "progression", 0)
        cost = int(ability.get("resource_cost", 0) or 0)
        if int(player.spell_points) < cost:
            return (f"Not enough spell points for Greater Heal (need {cost}, have {int(player.spell_points)}).", "progression", 0)
        healed = _heal_actor(target, _roll_dice(seed, 4, 8, 5))
        player.spell_points = int(player.spell_points) - cost
        return (f"{player.name} uses Greater Heal on {target.name} and restores {healed} HP.", "progression", 0)

    return (f"{ability_name} is not yet implemented in runtime.", "progression", 0)


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
        occupied_slots = {
            canonical_equipment_slot(slot_name) or ""
            for slot_name, slot_items in player.equipment.slots.items()
            if slot_items
        }
        occupied_slots.discard("")
        canonical_slot, slot = _slot_for_item_type(item.item_def_id, raw_def, occupied_slots)
        if canonical_slot is None or slot is None:
            return (f"Cannot equip '{item_name}': not part of the canonical wearable topology.", "equipment", 0)
        try:
            events = equip_inventory_item(player, item=item, slot=slot)
        except ValueError as exc:
            return (f"Cannot equip '{item_name}': {exc}. Expected canonical slot `{canonical_slot}`.", "equipment", 0)
        narrative = _summarize_events(events)
        logger.info("Equip: %s equipped %s to %s", player.name, item_name, canonical_slot)
        return (narrative, "equipment", 0)

    match = _UNEQUIP_RE.match(command_text.strip())
    if match:
        item_name = match.group(1).strip().lower().replace(" ", "_")
        # Search equipped slots for matching item.
        target_slot = None
        slot_aliases = set(canonical_slot_query_aliases(item_name))
        for slot_name, slot_items in player.equipment.slots.items():
            normalized_slot_name = str(slot_name).strip().lower()
            if normalized_slot_name in slot_aliases or (canonical_equipment_slot(normalized_slot_name) or "") in slot_aliases:
                target_slot = slot_name
                break
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

    target, target_error = _resolve_item_target(context, target_name)
    if target_error:
        return (target_error, "inventory", 0)
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
_ABILITIES_RE = re.compile(r"^abilities$", re.IGNORECASE)
_USE_ABILITY_RE = re.compile(r"^use\s+ability\s+(.+?)(?:\s+on\s+(.+))?$", re.IGNORECASE)
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

    if _ABILITIES_RE.match(text):
        return (_abilities_summary(player), "progression", 0)

    match = _USE_ABILITY_RE.match(text)
    if match:
        ability = _resolve_class_ability(player, match.group(1))
        if ability is None:
            return (f"Unknown class ability '{match.group(1).strip()}'.", "progression", 0)
        target_name = match.group(2).strip() if match.group(2) else None
        return _use_class_ability(context, player, ability, target_name)

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
        _ability_restore_on_long_rest(player)
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
# Handler 7: Spell (casting / memorization)
# ---------------------------------------------------------------------------

_CAST_RE = re.compile(r"^cast\s+(.+?)(?:\s+at\s+(.+))?$", re.IGNORECASE)
_MEMORIZE_RE = re.compile(r"^memorize\s+(.+)$", re.IGNORECASE)
_PREPARE_RE = re.compile(r"^prepare\s+(.+)$", re.IGNORECASE)


def maybe_handle_structured_spell_command(
    context: "CampaignContext",
    args: dict[str, Any],
    *,
    allow_combat: bool = False,
) -> Optional[tuple[str, str, int]]:
    player = _player(context)
    if player is None:
        return None
    action_id = str(args.get("action_id", "")).strip().lower()
    if not action_id:
        return None
    if action_id not in {"cast", "memorize"}:
        return (f"Unsupported spell action '{action_id}'.", "spell", 0)
    spell_id = str(args.get("spell_id", "")).strip().lower()
    if not spell_id:
        return (f"{action_id.title()} requires a spell_id.", "spell", 0)
    resolved_spell = _resolve_spell_registry_entry(spell_id, exact=True)
    if resolved_spell is None:
        return (f"Unknown spell '{spell_id}'.", "spell", 0)
    canonical_spell_id, spell_raw = resolved_spell
    spellbook_id = str(args.get("spellbook_id", "")).strip() or None
    if action_id == "memorize":
        if allow_combat and context.in_combat():
            return ("You cannot memorize spells during combat.", "spell", 0)
        result = _memorize_spell_action(
            context,
            player,
            spell_id=canonical_spell_id,
            spell_raw=spell_raw,
            spellbook_id=spellbook_id,
        )
        return (result["narrative"], "spell", int(result["hours_advanced"]))
    target_id = str(args.get("target_id", "")).strip() or None
    raw_position = args.get("target_position")
    target_position = (
        (int(raw_position[0]), int(raw_position[1]))
        if isinstance(raw_position, (list, tuple)) and len(raw_position) >= 2
        else None
    )
    target_actor, resolved_position, target_error = _resolve_structured_spell_target(
        context,
        target_id=target_id,
        target_position=target_position,
        spell_raw=spell_raw,
    )
    if target_error:
        return (target_error, "spell", 0)
    if allow_combat and context.in_combat():
        return _run_combat_spell_action(
            context,
            lambda: _cast_spell_action(
                context,
                player,
                spell_id=canonical_spell_id,
                spell_raw=spell_raw,
                target_actor=target_actor,
                target_position=resolved_position,
                spellbook_id=spellbook_id,
                allow_combat=True,
            ),
        )
    result = _cast_spell_action(
        context,
        player,
        spell_id=canonical_spell_id,
        spell_raw=spell_raw,
        target_actor=target_actor,
        target_position=resolved_position,
        spellbook_id=spellbook_id,
        allow_combat=False,
    )
    return (result["narrative"], "spell", int(result["hours_advanced"]))


def maybe_handle_spell_command(
    context: "CampaignContext",
    command_text: str,
    *,
    allow_combat: bool = False,
) -> Optional[tuple[str, str, int]]:
    player = _player(context)
    if player is None:
        return None
    text = command_text.strip()
    memorize_match = _MEMORIZE_RE.match(text) or _PREPARE_RE.match(text)
    if memorize_match:
        if allow_combat and context.in_combat():
            return ("You cannot memorize spells during combat.", "spell", 0)
        spell_name = memorize_match.group(1).strip()
        resolved_spell = _resolve_spell_registry_entry(spell_name, exact=False)
        if resolved_spell is None:
            return (f"Unknown spell '{spell_name}'.", "spell", 0)
        spell_id, spell_raw = resolved_spell
        result = _memorize_spell_action(
            context,
            player,
            spell_id=spell_id,
            spell_raw=spell_raw,
            spellbook_id=None,
        )
        return (result["narrative"], "spell", int(result["hours_advanced"]))
    match = _CAST_RE.match(text)
    if not match:
        return None
    spell_name = match.group(1).strip()
    target_name = match.group(2).strip() if match.group(2) else None
    resolved_spell = _resolve_spell_registry_entry(spell_name, exact=False)
    if resolved_spell is None:
        return (f"Unknown spell '{spell_name}'.", "spell", 0)
    spell_id, spell_raw = resolved_spell
    target_actor, target_position, target_error = _resolve_spell_target(context, target_name, spell_raw)
    if target_error:
        return (target_error, "spell", 0)
    if allow_combat and context.in_combat():
        return _run_combat_spell_action(
            context,
            lambda: _cast_spell_action(
                context,
                player,
                spell_id=spell_id,
                spell_raw=spell_raw,
                target_actor=target_actor,
                target_position=target_position,
                spellbook_id=None,
                allow_combat=True,
            ),
        )
    result = _cast_spell_action(
        context,
        player,
        spell_id=spell_id,
        spell_raw=spell_raw,
        target_actor=target_actor,
        target_position=target_position,
        spellbook_id=None,
        allow_combat=False,
    )
    return (result["narrative"], "spell", int(result["hours_advanced"]))


def _cast_spell_action(
    context: "CampaignContext",
    player: "ActorRecord",
    *,
    spell_id: str,
    spell_raw: dict[str, Any],
    target_actor: "ActorRecord" | None,
    target_position: tuple[int, int] | None,
    spellbook_id: str | None,
    allow_combat: bool,
) -> dict[str, Any]:
    current_tick = _spell_current_tick(context, player, allow_combat=allow_combat)
    cast_result = cast_registry_spell(
        player,
        spell_id=spell_id,
        spell_data=spell_raw,
        target=target_actor,
        target_position=target_position,
        current_tick=current_tick,
        spellbook_id=spellbook_id,
    )
    spell_label = str(cast_result.get("spell_label", spell_raw.get("name", spell_id)))
    if not cast_result.get("success", False) and cast_result.get("reason") == "insufficient_spell_points":
        return {
            "success": False,
            "attempt_started": False,
            "hours_advanced": 0,
            "narrative": (
                f"Not enough spell points to cast {spell_label} "
                f"(need {int(cast_result.get('cost', spell_raw.get('cost', 0)))}, have {int(player.spell_points)})."
            ),
        }
    if not cast_result.get("success", False) and cast_result.get("reason") == "no_available_slot":
        return {
            "success": False,
            "attempt_started": False,
            "hours_advanced": 0,
            "narrative": f"No prepared slot is available for {spell_label}.",
        }
    if not cast_result.get("success", False) and cast_result.get("reason") == "aura cooldown":
        return {
            "success": False,
            "attempt_started": False,
            "hours_advanced": 0,
            "narrative": f"You cannot cast {spell_label} again yet. Your aura has not recovered.",
        }
    if not cast_result.get("success", False) and cast_result.get("reason") == "invalid target":
        return {
            "success": False,
            "attempt_started": False,
            "hours_advanced": 0,
            "narrative": f"{spell_label} does not have a valid target.",
        }
    if not cast_result.get("success", False) and cast_result.get("reason") and not cast_result.get("attempt_started", False):
        return {
            "success": False,
            "attempt_started": False,
            "hours_advanced": 0,
            "narrative": f"Cannot cast {spell_label}: {cast_result['reason']}.",
        }
    if not cast_result.get("success", False) and cast_result.get("reason") == "resisted":
        target_label = _spell_recipient_label(target_actor, spell_raw)
        return {
            "success": False,
            "attempt_started": bool(cast_result.get("attempt_started", False)),
            "hours_advanced": 0 if allow_combat else 1,
            "narrative": f"{player.name} casts {spell_label}, but {target_label} resists the magic.",
        }
    effects = list(cast_result.get("applied", []))
    effect_parts: list[str] = []
    for effect in effects:
        effect_type = str(effect.get("type", ""))
        if effect_type == "damage":
            effect_parts.append(f"deals {effect.get('amount', '?')} damage to {effect.get('target', 'the target')}")
        elif effect_type == "heal":
            effect_parts.append(f"heals {effect.get('target', 'the target')} for {effect.get('amount', '?')}")
        elif effect_type == "buff":
            effect_parts.append(f"empowers {effect.get('target', 'the target')}")
        elif effect_type == "status":
            effect_parts.append(f"affects {effect.get('target', 'the target')} with a status effect")
        else:
            effect_parts.append(f"applies {effect_type}")
    effect_summary = "; ".join(effect_parts) if effect_parts else "magical energy swirls"
    logger.info("Cast: %s cast %s", player.name, spell_label)
    return {
        "success": True,
        "attempt_started": bool(cast_result.get("attempt_started", False)),
        "hours_advanced": 0 if allow_combat else 1,
        "narrative": f"{player.name} casts {spell_label}. {effect_summary}.",
    }


def _memorize_spell_action(
    context: "CampaignContext",
    player: "ActorRecord",
    *,
    spell_id: str,
    spell_raw: dict[str, Any],
    spellbook_id: str | None,
) -> dict[str, Any]:
    del context
    result = memorize_registry_spell(
        player,
        spell_id=spell_id,
        spell_data=spell_raw,
        spellbook_id=spellbook_id,
    )
    spell_label = str(result.get("spell_label", spell_raw.get("name", spell_id)))
    if result.get("success", False) and result.get("reason") == "already_memorized":
        return {"narrative": f"{spell_label} is already prepared.", "hours_advanced": 0}
    if result.get("success", False):
        return {"narrative": f"Prepared {spell_label}.", "hours_advanced": 0}
    if result.get("reason") == "memorize_not_supported":
        return {
            "narrative": f"{player.name} uses spell points and cannot memorize {spell_label}.",
            "hours_advanced": 0,
        }
    if result.get("reason") == "no_available_slot":
        return {"narrative": f"No prepared slot is available for {spell_label}.", "hours_advanced": 0}
    return {"narrative": f"Cannot prepare {spell_label}.", "hours_advanced": 0}


def _resolve_spell_registry_entry(query: str, *, exact: bool) -> tuple[str, dict[str, Any]] | None:
    registry = spells_registry()
    normalized_query = str(query).strip().lower().replace(" ", "_")
    if exact:
        if normalized_query in registry:
            return normalized_query, dict(registry[normalized_query])
        for entry in load_registry_list("spells.json", "spells"):
            if not isinstance(entry, dict):
                continue
            entry_id = str(entry.get("id") or entry.get("name", "")).strip().lower().replace(" ", "_")
            if entry_id == normalized_query:
                return entry_id, dict(entry)
        return None
    found = _fuzzy_match(query, registry) if registry else None
    if found is not None:
        return found[0], dict(found[1])
    spell_list = load_registry_list("spells.json", "spells")
    spell_raw = _fuzzy_match_list(query, spell_list)
    if spell_raw is None:
        return None
    spell_id = str(spell_raw.get("id") or spell_raw.get("name", query)).lower().replace(" ", "_")
    return spell_id, dict(spell_raw)


def _resolve_spell_target(
    context: "CampaignContext",
    target_name: str | None,
    spell_raw: dict[str, Any],
) -> tuple["ActorRecord" | None, tuple[int, int] | None, str | None]:
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    normalized_target = str(target_name or "").strip().lower()
    raw_target_type = str(spell_raw.get("target_type", "single")).lower()
    if raw_target_type == "self":
        return _player(context), None, None
    if normalized_target in {"self", "me", "myself", context.player.name.lower()}:
        return _player(context), None, None
    if normalized_target:
        resolved = resolve_live_actor_query(actors, normalized_target, include_player=True)
        if resolved.error:
            return None, None, resolved.error
        if resolved.actor is not None:
            point = None
            if raw_target_type in {"area", "cone", "point"}:
                point = (int(resolved.actor.position.x), int(resolved.actor.position.y))
            return resolved.actor, point, None
    hostile = raw_target_type != "self"
    if hostile:
        for actor_id, actor in actors.items():
            if actor_id == "player":
                continue
            if getattr(actor, "alive", True):
                point = None
                if raw_target_type in {"area", "cone", "point"}:
                    point = (int(actor.position.x), int(actor.position.y))
                return actor, point, None
    default_target = _player(context) if raw_target_type == "self" else None
    return default_target, None, None


def _resolve_structured_spell_target(
    context: "CampaignContext",
    *,
    target_id: str | None,
    target_position: tuple[int, int] | None,
    spell_raw: dict[str, Any],
) -> tuple["ActorRecord" | None, tuple[int, int] | None, str | None]:
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    raw_target_type = str(spell_raw.get("target_type", "single")).lower()
    if raw_target_type == "self":
        return _player(context), None, None
    if target_id:
        target_actor = actors.get(target_id)
        if target_actor is None:
            return None, None, f"Target '{target_id}' is no longer present."
        resolved_position = target_position
        if resolved_position is None and raw_target_type in {"area", "cone", "point"}:
            resolved_position = (int(target_actor.position.x), int(target_actor.position.y))
        return target_actor, resolved_position, None
    if target_position is not None:
        for actor_id, actor in actors.items():
            if actor_id == "player" or not getattr(actor, "alive", True):
                continue
            if (int(actor.position.x), int(actor.position.y)) == target_position:
                return actor, target_position, None
        if raw_target_type in {"area", "cone", "point"}:
            return None, None, f"No spell target found at ({int(target_position[0])},{int(target_position[1])})."
    return _resolve_spell_target(context, None, spell_raw)


def _spell_current_tick(
    context: "CampaignContext",
    player: "ActorRecord",
    *,
    allow_combat: bool,
) -> int:
    base_tick = int(player.raw_payload.get("game_tick", 0))
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    world_time = getattr(game_state, "world_time", None)
    world_tick = int(getattr(world_time, "game_tick", base_tick))
    if allow_combat and context.in_combat():
        from engine.api import combat_bridge

        combat_state = combat_bridge._combat_state(context)
        if combat_state is not None:
            return world_tick + (int(combat_state.round_number) * 10) + int(combat_state.current_turn_index)
    return max(base_tick, world_tick)


def _run_combat_spell_action(
    context: "CampaignContext",
    resolver,
) -> tuple[str, str, int]:
    from engine.api import combat_bridge

    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    player = actors.get("player")
    if player is None:
        return ("No combatant is ready to act.", "spell", 0)
    combat_state = combat_bridge._combat_state(context)
    if combat_state is None:
        result = resolver()
        return (result["narrative"], "spell", int(result["hours_advanced"]))
    state_ready = combat_bridge._ensure_player_turn(context, combat_state, actors)
    if state_ready["resolved"]:
        return (state_ready["summary"] or "Combat is already over.", "combat", 0)
    if state_ready["blocked"]:
        return (state_ready["summary"], "combat", 0)
    result = resolver()
    if not bool(result.get("attempt_started", False)):
        return (result["narrative"], "spell", 0)
    follow_up = combat_bridge._end_player_turn_and_resolve(
        context,
        combat_state,
        actors,
        seed_offset=71,
    )
    narrative = str(result["narrative"]).strip()
    if follow_up:
        narrative = f"{narrative} {follow_up}".strip()
    return (narrative, "spell", 0)


def _spell_recipient_label(target_actor: "ActorRecord" | None, spell_raw: dict[str, Any]) -> str:
    if target_actor is not None:
        return target_actor.name
    if str(spell_raw.get("target_type", "single")).lower() == "self":
        return "the caster"
    return "the target"


def _inventory_add_failure_message(context: "CampaignContext", item_name: str) -> str:
    error = dict(context.narration_context.pop("_last_add_item_error", {}) or {})
    if error.get("reason") == "overweight":
        return (
            f"{item_name} is too heavy to carry right now. It would bring you to "
            f"{float(error.get('projected_weight', 0.0)):.1f}/{float(error.get('max_weight', 0.0)):.1f} kg. "
            "You wrench your back trying to lift it."
        )
    return f"No room for {item_name}. Your containers are full."

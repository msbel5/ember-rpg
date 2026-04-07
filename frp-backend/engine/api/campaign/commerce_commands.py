"""Commerce command ownership for the campaign runtime."""
from __future__ import annotations

import logging
from random import Random
from typing import TYPE_CHECKING, Any, Optional

from engine.api.campaign.runtime_common import stable_seed

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext

logger = logging.getLogger(__name__)


def maybe_handle_commerce_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle buy/sell/rent/identify via kernel store.py."""
    from engine.api.campaign.crime import record_theft_incident
    from engine.kernel.store import attempt_steal, buy_identification, buy_item, rent_room, sell_item

    lower = command_text.lower().strip()
    runtime = context.kernel_runtime or {}
    stores = runtime.get("stores", [])
    actors = runtime.get("actors", {})
    player = actors.get("player")
    if player is None:
        return None
    item_registry = _item_registry()
    if lower.startswith("steal "):
        item_name = command_text[6:].strip()
        npc_part = ""
        if " from " in item_name:
            item_name, npc_part = item_name.rsplit(" from ", 1)
        item_name = item_name.strip()
        store = _find_store(stores, npc_part.strip())
        if store is None:
            return (f"No merchant found to steal '{item_name}' from.", "commerce", 1)
        store_item_id = _find_store_item_id(store, item_name)
        if not store_item_id:
            return (f"'{item_name}' is not in stock there.", "commerce", 1)
        d100_roll = Random(
            _steal_roll_seed(
                context,
                store_id=str(getattr(store, "store_id", "") or ""),
                item_id=store_item_id,
            )
        ).randint(1, 100)
        success, msg = attempt_steal(player, store, store_item_id, d100_roll=d100_roll)
        _normalize_runtime_inventory_items(player, item_registry=item_registry)
        record_theft_incident(
            context,
            item_id=store_item_id,
            store=store,
            detected=not success,
        )
        if success:
            return (f"Stole {store_item_id}. {msg}.", "commerce", 1)
        return (f"Steal failed: {msg}.", "commerce", 1)
    if lower.startswith("buy "):
        item_name = command_text[4:].strip()
        npc_part = ""
        if " from " in item_name:
            item_name, npc_part = item_name.split(" from ", 1)
        item_name = item_name.strip()
        store = _find_store(stores, npc_part.strip())
        if store is None:
            return (f"No merchant found to buy '{item_name}' from.", "commerce", 1)
        ok, msg = buy_item(player, store, item_name, 1, item_registry)
        if not ok:
            return (msg, "commerce", 1)
        logger.info("Buy: %s bought %s", player.identity.display_name, item_name)
        return (f"Bought {item_name}. {msg}", "commerce", 1)
    if lower.startswith("sell "):
        item_name = command_text[5:].strip()
        npc_part = ""
        if " to " in item_name:
            item_name, npc_part = item_name.split(" to ", 1)
        item_name = item_name.strip()
        store = _find_store(stores, npc_part.strip())
        if store is None:
            return (f"No merchant found to sell '{item_name}' to.", "commerce", 1)
        item_instance = next((i for i in player.inventory if i.item_def_id == item_name), None)
        if item_instance is None:
            return (f"You don't have '{item_name}' to sell.", "commerce", 1)
        ok, msg = sell_item(player, store, item_instance, item_registry)
        if not ok:
            return (msg, "commerce", 1)
        logger.info("Sell: %s sold %s", player.identity.display_name, item_name)
        return (f"Sold {item_name}. {msg}", "commerce", 1)
    if lower.startswith("rent room") or lower.startswith("rent a room"):
        store = _find_store(stores, "")
        if store is None:
            return ("No inn found to rent a room.", "commerce", 1)
        ok, msg = rent_room(player, store, "room")
        if not ok:
            return (msg, "commerce", 8)
        return ("Rented a room. You rest for the night.", "commerce", 8)
    if lower.startswith("identify "):
        item_name = command_text[9:].strip()
        store = _find_store_with_service(stores, "identify")
        if store is None:
            return ("No merchant with identification services found.", "commerce", 1)
        item_instance = _find_inventory_item(player, item_name)
        if item_instance is None:
            return (f"You don't have '{item_name}' to identify.", "commerce", 1)
        item_def = _item_def_from_registry(item_instance.item_def_id, item_registry)
        if item_def is None:
            return (f"Unknown item definition for '{item_name}'.", "commerce", 1)
        ok, msg = buy_identification(player, store, item_instance, item_def)
        if not ok:
            return (f"Cannot identify: {msg}.", "commerce", 1)
        logger.info("Identify: %s identified %s", player.identity.display_name, item_name)
        return (f"Identified {item_name}. {msg}", "commerce", 1)
    return None


def _find_store(stores: list, npc_hint: str) -> Any:
    if not stores:
        return None
    if npc_hint:
        normalized_hint = npc_hint.lower().strip()
        for store in stores:
            store_id = str(getattr(store, "store_id", "") or "")
            label = str(getattr(store, "label", "") or "")
            npc_id = getattr(store, "npc_id", "") or ""
            if (
                normalized_hint in npc_id.lower()
                or normalized_hint in store_id.lower()
                or normalized_hint in label.lower()
            ):
                return store
    return stores[0] if stores else None


def _find_store_item_id(store: Any, item_name: str) -> str:
    normalized_query = str(item_name or "").strip().lower().replace(" ", "_")
    if not normalized_query:
        return ""
    item_ids = [
        str(getattr(item, "item_def_id", "") or "").strip()
        for item in list(getattr(store, "items", []) or [])
    ]
    for item_id in item_ids:
        if item_id.lower() == normalized_query:
            return item_id
    for item_id in item_ids:
        lowered = item_id.lower()
        if normalized_query in lowered or lowered in normalized_query:
            return item_id
    return ""


def _steal_roll_seed(context: "CampaignContext", *, store_id: str, item_id: str) -> int:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    world_time = getattr(game_state, "world_time", None) if game_state is not None else None
    game_tick = int(getattr(world_time, "game_tick", 0) or 0)
    return stable_seed(
        context.seed,
        context.campaign_id,
        "steal",
        store_id,
        item_id,
        game_tick,
    )


def _normalize_runtime_inventory_items(player: Any, *, item_registry: dict[str, Any]) -> None:
    from engine.kernel import item_stack_from_payload
    from engine.kernel.items import ItemInstance as KernelItemInstance

    inventory = list(getattr(player, "inventory", []) or [])
    normalized_inventory: list[Any] = []
    changed = False
    for index, item in enumerate(inventory):
        if not isinstance(item, KernelItemInstance):
            normalized_inventory.append(item)
            continue
        raw_item = dict(item_registry.get(item.item_def_id, {}) or {})
        raw_charges = getattr(item, "charges", -1)
        payload = {
            "id": item.item_def_id,
            "item_def_id": item.item_def_id,
            "name": str(raw_item.get("name", item.item_def_id)).strip() or item.item_def_id.replace("_", " ").title(),
            "type": str(raw_item.get("type", "misc")).strip() or "misc",
            "quantity": max(1, int(getattr(item, "stack_count", 1) or 1)),
            "charges": int(raw_charges) if raw_charges is not None else -1,
            "identified": bool(getattr(item, "identified", False)),
            "wear": int(getattr(item, "wear", 0) or 0),
        }
        if getattr(item, "equipped_slot", None):
            payload["equipped_slot"] = str(item.equipped_slot)
        normalized_inventory.append(item_stack_from_payload(payload, index=index))
        changed = True
    if changed:
        player.inventory[:] = normalized_inventory


def _item_registry() -> dict:
    try:
        from engine.data._shared import items_registry

        reg = items_registry()
        if isinstance(reg, dict):
            return reg
        return {item.get("id", ""): item for item in reg if isinstance(item, dict)}
    except Exception:
        return {}


def _find_store_with_service(stores: list, service_type: str) -> Any:
    for store in stores:
        if any(getattr(s, "service_type", "") == service_type for s in getattr(store, "services", [])):
            return store
    return None


def _find_inventory_item(player: Any, item_name: str) -> Any:
    name_lower = item_name.lower().replace(" ", "_")
    for item in player.inventory:
        def_id = getattr(item, "item_def_id", "")
        if def_id == name_lower or name_lower in def_id.lower():
            return item
    return None


def _item_def_from_registry(item_def_id: str, registry: dict) -> Any:
    raw = registry.get(item_def_id)
    if raw is None:
        return None
    try:
        from engine.kernel.items import ItemDef

        return ItemDef(
            item_def_id=str(raw.get("id", item_def_id)),
            label=str(raw.get("name", item_def_id)),
            item_type=str(raw.get("type", "misc")),
            rarity=str(raw.get("rarity", "common")).upper(),
            base_price=int(raw.get("value", 0)),
            weight=float(raw.get("weight", 0.0)),
            lore_to_identify=int(raw.get("lore_to_identify", 0)),
        )
    except Exception:
        return None


__all__ = ["maybe_handle_commerce_command"]

from __future__ import annotations

import copy
from typing import Any

from engine.kernel import (
    ProductionLedger,
    StoreDef,
    StoreItem,
    StoreService,
    WorldState,
    adjust_store_prices,
    colony_pressure_from_settlement,
    production_ledger_from_settlement,
)

from .runtime_common import active_site_id


_BARTER_BLOCKED_ROLES = {
    "commander",
    "guard",
    "jailer",
    "mayor",
    "quest_giver",
    "researcher",
    "sage",
    "scholar",
    "scribe",
    "warden",
}

_ROLE_SERVICE_LABELS = {
    "innkeeper": ("room", "Room for the night"),
    "priest": ("healing", "Temple healing"),
    "alchemist": ("healing", "Curative draught"),
    "apothecary": ("healing", "Curative draught"),
    "witch": ("healing", "Herbal restoration"),
    "blacksmith": ("repair", "Repair gear"),
    "smith": ("repair", "Repair gear"),
    "stablehand": ("mount_rental", "Rent a mount"),
    "quartermaster": ("weapon_training", "Drill and weapons practice"),
}

_ROLE_STORE_TYPES = {
    "merchant": "shop",
    "baker": "bakery",
    "innkeeper": "inn",
    "blacksmith": "smithy",
    "smith": "smithy",
    "priest": "temple",
    "alchemist": "apothecary",
    "apothecary": "apothecary",
    "witch": "apothecary",
    "stablehand": "stable",
    "quartermaster": "depot",
    "commoner": "barter",
    "resident": "barter",
    "bard": "barter",
}

_FOODISH_TOKENS = ("bread", "ale", "ration", "water", "meal", "fruit", "grain", "fish")


def macro_society_events(context, runtime: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    ledger: ProductionLedger = production_ledger_from_settlement(context.settlement_state)
    runtime["production_ledger"] = ledger
    pressure = colony_pressure_from_settlement(context.settlement_state)
    runtime["colony_pressure"] = pressure
    for store in runtime["stores"]:
        adjust_store_prices(store, ledger)
        if ledger.shortages:
            for item in store.items:
                item.price_multiplier = round(float(item.price_multiplier) * (1.0 + (0.05 * len(ledger.shortages))), 4)
        elif ledger.surpluses:
            discount = max(0.85, 1.0 - (0.03 * len(ledger.surpluses)))
            for item in store.items:
                item.price_multiplier = round(float(item.price_multiplier) * discount, 4)
        for item in store.items:
            context.settlement_state.setdefault("economy", {}).setdefault("prices", {})[item.item_def_id] = item.price_multiplier
    current_hour = int(context.world.simulation_snapshot.current_hour)
    caravan_events = context.caravan_manager.tick(current_hour)
    world_state: WorldState = runtime["world_state"]
    world_state.active_caravans = context.caravan_manager.get_active_caravans()
    for event in caravan_events:
        if event.get("type") != "arrival":
            continue
        goods = dict(event.get("goods_delivered", {}))
        for store in runtime["stores"]:
            restock_store(store, goods)
        resources = context.settlement_state.setdefault("economy", {}).setdefault("resources", {})
        for item_id, quantity in goods.items():
            resources[item_id] = int(resources.get(item_id, 0)) + int(quantity)
        events.append({"event_type": "caravan_arrival", "summary": f"A caravan arrived with {', '.join(goods.keys())}."})
    region = world_state.regions.get(context.region_snapshot.region_id)
    if region is not None:
        region.economy.setdefault("prices", {}).update(context.settlement_state.setdefault("economy", {}).get("prices", {}))
    for faction_id, faction in world_state.factions.items():
        for other_id in world_state.factions:
            if faction_id == other_id:
                continue
            faction.relations.setdefault(other_id, 0)
            delta = 1 if not ledger.shortages else -len(ledger.shortages)
            faction.relations[other_id] = max(-100, min(100, int(faction.relations[other_id]) + delta))
    if "migration_candidate" in pressure.pressure_tags:
        wave_id = f"{context.region_snapshot.region_id}:{context.world.simulation_snapshot.current_day}"
        if not any(wave.get("wave_id") == wave_id for wave in world_state.migration_waves):
            population_delta = max(1, int(context.settlement_state.get("population", 1)) // 10)
            world_state.migration_waves.append(
                {
                    "wave_id": wave_id,
                    "region_id": context.region_snapshot.region_id,
                    "settlement_id": active_site_id(context),
                    "population_delta": population_delta,
                    "reason": "prosperity",
                }
            )
            context.settlement_state["population"] = int(context.settlement_state.get("population", 0)) + population_delta
            settlement = world_state.settlements.get(active_site_id(context))
            if settlement is not None:
                settlement.population += population_delta
            events.append({"event_type": "migration_wave", "summary": "New settlers arrived at the frontier."})
    if pressure.unrest >= 60 and region is not None and region.controller_faction_id:
        change_id = f"{context.region_snapshot.region_id}:{context.world.simulation_snapshot.current_day}:unrest"
        if not any(change.get("change_id") == change_id for change in world_state.ownership_changes):
            world_state.ownership_changes.append(
                {
                    "change_id": change_id,
                    "region_id": context.region_snapshot.region_id,
                    "faction_id": region.controller_faction_id,
                    "reason": "unrest",
                }
            )
    return events


def load_stores(saved_payload: Any, context) -> list[StoreDef]:
    if isinstance(saved_payload, list):
        return [item if isinstance(item, StoreDef) else StoreDef.from_dict(dict(item)) for item in saved_payload]
    return default_stores(context)


def default_stores(context) -> list[StoreDef]:
    items = _base_store_items(context)
    stores = _resident_stores(context, items)
    if stores:
        return stores
    return [
        StoreDef(
            store_id=f"{active_site_id(context)}_market",
            label=f"{context.settlement_state.get('name', 'Frontier')} Market",
            store_type="market",
            items=copy.deepcopy(items),
            services=_default_services(),
        )
    ]


def _base_store_items(context) -> list[StoreItem]:
    resources = dict(context.settlement_state.get("economy", {}).get("resources", {}))
    items = [
        StoreItem(item_def_id=str(item_id), quantity=max(1, int(quantity)), price_multiplier=1.0)
        for item_id, quantity in sorted(resources.items())
        if int(quantity) > 0
    ]
    if items:
        return items
    from engine.data._shared import economy_config_registry

    eco = economy_config_registry()
    return [StoreItem(item_def_id=e["item_def_id"], quantity=e["quantity"]) for e in eco.get("default_store_inventory", [])]


def _default_services() -> list[StoreService]:
    from engine.data._shared import economy_config_registry

    svc_data = economy_config_registry().get("default_store_services", [])
    if svc_data:
        return [StoreService(**s) for s in svc_data]
    return [
        StoreService(service_id="rest", service_type="room", label="Room for the night", price=5, room_quality=1.0),
    ]


def _resident_stores(context, base_items: list[StoreItem]) -> list[StoreDef]:
    residents = list(context.settlement_state.get("residents", []))
    if not residents:
        return []
    stores: list[StoreDef] = []
    seen_npc_ids: set[str] = set()
    settlement_name = str(context.settlement_state.get("name", "Frontier")).strip() or "Frontier"
    for resident in residents:
        if not isinstance(resident, dict):
            continue
        npc_id = str(resident.get("id", "")).strip()
        npc_name = str(resident.get("name", npc_id)).strip() or npc_id
        role = _normalize_role(str(resident.get("role", resident.get("assignment", "resident"))))
        if not _supports_barter(role, npc_id) or npc_id in seen_npc_ids:
            continue
        seen_npc_ids.add(npc_id)
        services = _services_for_role(role)
        items = _items_for_role(base_items, role)
        if not items and not services:
            continue
        store_type = _ROLE_STORE_TYPES.get(role, "barter")
        stores.append(
            StoreDef(
                store_id=f"{active_site_id(context)}_{npc_id}_commerce",
                label=_store_label(npc_name, role, settlement_name),
                store_type=store_type,
                npc_id=npc_id,
                npc_name=npc_name,
                role=role,
                items=items,
                services=services,
                lore=50 if role in {"priest", "alchemist", "apothecary", "witch"} else 0,
            )
        )
    return stores


def _normalize_role(role: str) -> str:
    normalized = str(role or "resident").strip().lower()
    if normalized in {"smith", "blacksmith"}:
        return "blacksmith"
    if normalized in {"healer", "apothecary"}:
        return "apothecary"
    if normalized in {"villager", "civilian"}:
        return "resident"
    return normalized or "resident"


def _supports_barter(role: str, npc_id: str) -> bool:
    if not npc_id or npc_id == "player_commander":
        return False
    return role not in _BARTER_BLOCKED_ROLES


def _items_for_role(base_items: list[StoreItem], role: str) -> list[StoreItem]:
    if not base_items:
        return []
    if role in {"merchant", "quartermaster", "blacksmith", "smith", "apothecary", "priest", "stablehand", "alchemist", "witch"}:
        return copy.deepcopy(base_items)
    preferred = [
        item for item in base_items
        if any(token in str(item.item_def_id).lower() for token in _FOODISH_TOKENS)
    ]
    selection = preferred[:3] if preferred else list(base_items[:2])
    return copy.deepcopy(selection)


def _services_for_role(role: str) -> list[StoreService]:
    service_spec = _ROLE_SERVICE_LABELS.get(role)
    if service_spec is None:
        return [copy.deepcopy(service) for service in _default_services()] if role == "merchant" else []
    service_type, label = service_spec
    price = 5
    room_quality = 1.0
    if service_type == "repair":
        price = 8
    elif service_type == "healing":
        price = 12
    elif service_type == "mount_rental":
        price = 15
    elif service_type == "weapon_training":
        price = 10
    elif service_type == "room":
        price = 5
        room_quality = 1.1
    return [
        StoreService(
            service_id="room" if service_type == "room" else f"{role}_{service_type}",
            service_type=service_type,
            label=label,
            price=price,
            room_quality=room_quality,
        )
    ]


def _store_label(npc_name: str, role: str, settlement_name: str) -> str:
    if role == "innkeeper":
        return f"{npc_name}'s Rooms"
    if role == "blacksmith":
        return f"{npc_name}'s Smithy"
    if role in {"priest", "apothecary", "alchemist", "witch"}:
        return f"{npc_name}'s Remedies"
    if role == "stablehand":
        return f"{npc_name}'s Stable"
    if role == "quartermaster":
        return f"{npc_name}'s Depot"
    if role in {"merchant", "baker"}:
        return f"{npc_name}'s Stall"
    return f"{npc_name}'s Trade Pack"


def restock_store(store: StoreDef, goods: dict[str, Any]) -> None:
    for item_id, quantity in goods.items():
        existing = next((item for item in store.items if item.item_def_id == item_id), None)
        if existing is None:
            store.items.append(StoreItem(item_def_id=str(item_id), quantity=int(quantity), price_multiplier=1.0))
        else:
            existing.quantity = max(0, int(existing.quantity)) + int(quantity)


__all__ = ["default_stores", "load_stores", "macro_society_events", "restock_store"]

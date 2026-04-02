from __future__ import annotations

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
    caravan_events = context.session.caravan_manager.tick(current_hour)
    world_state: WorldState = runtime["world_state"]
    world_state.active_caravans = context.session.caravan_manager.get_active_caravans()
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
    resources = dict(context.settlement_state.get("economy", {}).get("resources", {}))
    items = [
        StoreItem(item_def_id=str(item_id), quantity=max(1, int(quantity)), price_multiplier=1.0)
        for item_id, quantity in sorted(resources.items())
        if int(quantity) > 0
    ]
    if not items:
        items = [StoreItem(item_def_id="food", quantity=10), StoreItem(item_def_id="materials", quantity=6)]
    services = [
        StoreService(service_id="rest", service_type="room", label="Room for the night", price=5, room_quality=1.0),
        StoreService(service_id="identify", service_type="identify", label="Identify item", price=10),
    ]
    return [
        StoreDef(
            store_id=f"{active_site_id(context)}_market",
            label=f"{context.settlement_state.get('name', 'Frontier')} Market",
            store_type="market",
            items=items,
            services=services,
        )
    ]


def restock_store(store: StoreDef, goods: dict[str, Any]) -> None:
    for item_id, quantity in goods.items():
        existing = next((item for item in store.items if item.item_def_id == item_id), None)
        if existing is None:
            store.items.append(StoreItem(item_def_id=str(item_id), quantity=int(quantity), price_multiplier=1.0))
        else:
            existing.quantity = max(0, int(existing.quantity)) + int(quantity)


__all__ = ["default_stores", "load_stores", "macro_society_events", "restock_store"]

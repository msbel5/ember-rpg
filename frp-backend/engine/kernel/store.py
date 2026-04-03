from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord
from engine.kernel.colony import ProductionLedger
from engine.kernel.common import serialize_value
from engine.kernel.effects import apply_effect
from engine.kernel.items import ItemDef, ItemInstance
from engine.kernel.spells import Spellbook, rest_refresh_spellbook


@dataclass
class StoreItem:
    item_def_id: str
    quantity: int = -1
    base_price_override: int | None = None
    sales_count: int = 0
    price_multiplier: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreItem":
        return cls(**data)


@dataclass
class StoreService:
    service_id: str
    service_type: str
    label: str
    price: int
    effect_id: str = ""
    room_quality: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreService":
        return cls(**data)


@dataclass
class StoreDef:
    store_id: str
    label: str
    store_type: str
    buy_markup: float = 1.5
    sell_markup: float = 0.5
    steal_difficulty: int = 50
    lore: int = 0
    capacity: int = 100
    items: list[StoreItem] = field(default_factory=list)
    services: list[StoreService] = field(default_factory=list)
    hostile: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreDef":
        payload = dict(data)
        payload["items"] = [
            item if isinstance(item, StoreItem) else StoreItem.from_dict(dict(item))
            for item in payload.get("items", [])
        ]
        payload["services"] = [
            item if isinstance(item, StoreService) else StoreService.from_dict(dict(item))
            for item in payload.get("services", [])
        ]
        return cls(**payload)


def compute_buy_price(item_def: ItemDef, store: StoreDef, buyer_pre: int, buyer_rep: int) -> int:
    store_item = _find_store_item(store, item_def.item_def_id)
    base_price = _resolve_base_price(item_def, store_item)
    multiplier = store.buy_markup * _pre_modifier(int(buyer_pre)) * _rep_modifier(int(buyer_rep))
    if store_item is not None:
        multiplier *= float(store_item.price_multiplier)
    return max(1, int(base_price * multiplier))


def compute_sell_price(
    item_def: ItemDef,
    store: StoreDef,
    store_item: StoreItem,
    seller_pre: int,
    seller_rep: int,
) -> int:
    base_price = _resolve_base_price(item_def, store_item)
    depreciation = 0.9 ** max(0, int(store_item.sales_count))
    multiplier = (
        store.sell_markup
        * _pre_modifier(int(seller_pre))
        * _rep_modifier(int(seller_rep))
        * depreciation
        * float(store_item.price_multiplier)
    )
    return max(1, int(base_price * multiplier))


def buy_item(
    buyer: ActorRecord,
    store: StoreDef,
    item_def_id: str,
    quantity: int,
    item_registry: dict[str, ItemDef],
) -> tuple[bool, str]:
    if int(quantity) <= 0:
        return False, "quantity must be positive"
    item_def = item_registry.get(item_def_id)
    if item_def is None:
        return False, "item not found"
    store_item = _find_store_item(store, item_def_id)
    if store_item is None:
        return False, "item not in stock"
    if store_item.quantity >= 0 and store_item.quantity < int(quantity):
        return False, "insufficient stock"

    price_each = compute_buy_price(item_def, store, _actor_pre(buyer), _actor_reputation(buyer))
    total_price = price_each * int(quantity)
    if _actor_gold(buyer) < total_price:
        return False, "insufficient gold"

    _set_actor_gold(buyer, _actor_gold(buyer) - total_price)
    _grant_item_instances(buyer, item_def, int(quantity))
    if store_item.quantity >= 0:
        store_item.quantity -= int(quantity)
    return True, f"bought {quantity} {item_def_id}"


def sell_item(
    seller: ActorRecord,
    store: StoreDef,
    item_instance: ItemInstance,
    item_registry: dict[str, ItemDef],
) -> tuple[bool, str, int]:
    item_def = item_registry.get(item_instance.item_def_id)
    if item_def is None:
        return False, "item not found", 0
    store_item = _find_store_item(store, item_instance.item_def_id)
    if store_item is None:
        store_item = StoreItem(item_def_id=item_instance.item_def_id, quantity=0)
        store.items.append(store_item)

    price = compute_sell_price(
        item_def,
        store,
        store_item,
        seller_pre=_actor_pre(seller),
        seller_rep=_actor_reputation(seller),
    )
    if item_instance in seller.inventory:
        seller.inventory.remove(item_instance)
    _set_actor_gold(seller, _actor_gold(seller) + price)

    if store_item.quantity >= 0:
        store_item.quantity += max(1, int(getattr(item_instance, "stack_count", 1)))
    store_item.sales_count += 1
    return True, f"sold {item_instance.item_def_id}", price


def attempt_steal(thief: ActorRecord, store: StoreDef, item_def_id: str, d100_roll: int) -> tuple[bool, str]:
    store_item = _find_store_item(store, item_def_id)
    if store_item is None or store_item.quantity == 0:
        return False, "item not in stock"
    total = int(d100_roll) + (int(thief.skills.get("pickpocket", 0)) * 5)
    if total >= int(store.steal_difficulty):
        _grant_item_instances(thief, ItemDef(item_def_id=item_def_id, label=item_def_id, item_type="misc", item_category="misc", weight=1, base_price=0), 1)
        if store_item.quantity > 0:
            store_item.quantity -= 1
        return True, "stolen"
    store.hostile = True
    _set_actor_reputation(thief, _actor_reputation(thief) - 2)
    return False, "caught stealing"


def buy_healing(buyer: ActorRecord, store: StoreDef, service_id: str) -> tuple[bool, str]:
    service = _find_service(store, service_id, "healing")
    if service is None:
        return False, "healing service unavailable"
    if _actor_gold(buyer) < int(service.price):
        return False, "insufficient gold"

    registry = dict(buyer.raw_payload.get("effect_registry", {}))
    effect_def = registry.get(service.effect_id)
    if effect_def is None:
        return False, "healing effect unavailable"

    _set_actor_gold(buyer, _actor_gold(buyer) - int(service.price))
    used, instance = apply_effect(
        buyer,
        effect_def,
        source_id=service.service_id,
        current_tick=int(buyer.raw_payload.get("current_tick", 0)),
    )
    if effect_def.category == "healing" and effect_def.timing_mode == "instant" and effect_def.healing_per_tick > 0:
        buyer.stats["hp"] = min(
            int(buyer.stats.get("max_hp", buyer.stats.get("hp", 0))),
            int(buyer.stats.get("hp", 0)) + int(effect_def.healing_per_tick),
        )
        if buyer.effect_queue is not None and instance is not None:
            buyer.effect_queue.instances = [
                current for current in buyer.effect_queue.instances if current.instance_id != instance.instance_id
            ]
            buyer.effect_queue.rebuild_condition_cache()
    return used, "healed" if used else "healing resisted"


def rent_room(actor: ActorRecord, store: StoreDef, service_id: str) -> tuple[bool, str]:
    service = _find_service(store, service_id, "room")
    if service is None:
        return False, "room unavailable"
    if _actor_gold(actor) < int(service.price):
        return False, "insufficient gold"

    _set_actor_gold(actor, _actor_gold(actor) - int(service.price))
    actor.stats["hp"] = int(actor.stats.get("max_hp", actor.stats.get("hp", 0)))

    spellbooks = actor.raw_payload.get("spellbooks", {})
    if isinstance(spellbooks, dict):
        for spellbook in spellbooks.values():
            if isinstance(spellbook, Spellbook):
                rest_refresh_spellbook(spellbook)

    actor.raw_payload["hours_rested"] = int(actor.raw_payload.get("hours_rested", 0)) + 8
    actor.raw_payload["last_room_quality"] = float(service.room_quality)
    return True, "rested"


def buy_identification(
    buyer: ActorRecord,
    store: StoreDef,
    item: ItemInstance,
    item_def: ItemDef,
) -> tuple[bool, str]:
    service = _first_service_of_type(store, "identify")
    if service is None:
        return False, "identification unavailable"
    if int(store.lore) < int(item_def.lore_to_identify):
        return False, "store lore insufficient"
    if _actor_gold(buyer) < int(service.price):
        return False, "insufficient gold"
    _set_actor_gold(buyer, _actor_gold(buyer) - int(service.price))
    item.identified = True
    return True, "identified"


def buy_repair(
    buyer: ActorRecord,
    store: StoreDef,
    item: ItemInstance,
    item_def: ItemDef,
) -> tuple[bool, int]:
    service = _first_service_of_type(store, "repair")
    if service is None:
        return False, 0
    max_wear = max(1, int(item.max_wear))
    wear_ratio = max(0.0, float(item.wear) / float(max_wear))
    cost = int(int(item_def.base_price) * wear_ratio * 0.5)
    if _actor_gold(buyer) < cost:
        return False, cost
    _set_actor_gold(buyer, _actor_gold(buyer) - cost)
    item.wear = 0
    return True, cost


def adjust_store_prices(store: StoreDef, colony_ledger: ProductionLedger) -> None:
    surplus = set(str(entry) for entry in colony_ledger.surpluses)
    shortage = set(str(entry) for entry in colony_ledger.shortages)
    for store_item in store.items:
        if store_item.item_def_id in surplus:
            store_item.price_multiplier = round(float(store_item.price_multiplier) * 0.8, 4)
        if store_item.item_def_id in shortage:
            store_item.price_multiplier = round(float(store_item.price_multiplier) * 1.3, 4)


def _find_store_item(store: StoreDef, item_def_id: str) -> StoreItem | None:
    return next((item for item in store.items if item.item_def_id == item_def_id), None)


def _find_service(store: StoreDef, service_id: str, service_type: str) -> StoreService | None:
    return next(
        (
            service
            for service in store.services
            if service.service_id == service_id and service.service_type == service_type
        ),
        None,
    )


def _first_service_of_type(store: StoreDef, service_type: str) -> StoreService | None:
    return next((service for service in store.services if service.service_type == service_type), None)


def _resolve_base_price(item_def: ItemDef, store_item: StoreItem | None) -> int:
    if store_item is not None and store_item.base_price_override is not None:
        return int(store_item.base_price_override)
    return int(item_def.base_price)


def _grant_item_instances(actor: ActorRecord, item_def: ItemDef, quantity: int) -> None:
    if int(quantity) <= 0:
        return
    remaining = int(quantity)
    if int(item_def.max_stack) > 1:
        stack_size = min(int(item_def.max_stack), remaining)
        actor.inventory.append(
            ItemInstance(
                instance_id=_next_instance_id(actor, item_def.item_def_id),
                item_def_id=item_def.item_def_id,
                stack_count=stack_size,
            )
        )
        remaining -= stack_size
    while remaining > 0:
        actor.inventory.append(
            ItemInstance(
                instance_id=_next_instance_id(actor, item_def.item_def_id),
                item_def_id=item_def.item_def_id,
            )
        )
        remaining -= 1


def _next_instance_id(actor: ActorRecord, item_def_id: str) -> str:
    existing = sum(1 for item in actor.inventory if getattr(item, "item_def_id", "") == item_def_id)
    return f"{item_def_id}_{existing + 1}"


def _actor_gold(actor: ActorRecord) -> int:
    return int(actor.stats.get("gold", actor.raw_payload.get("gold", 0)))


def _set_actor_gold(actor: ActorRecord, gold: int) -> None:
    actor.stats["gold"] = int(gold)


def _actor_pre(actor: ActorRecord) -> int:
    """Return the actor's presence (PRE) stat for social checks."""
    return int(actor.stats.get("PRE", 10))


def _actor_reputation(actor: ActorRecord) -> int:
    if "reputation" in actor.raw_payload:
        return int(actor.raw_payload["reputation"])
    return int(actor.stats.get("reputation", 10))


def _set_actor_reputation(actor: ActorRecord, reputation: int) -> None:
    actor.raw_payload["reputation"] = int(reputation)


def _pre_modifier(pre: int) -> float:
    return 1.0 - ((int(pre) - 10) * 0.025)


def _rep_modifier(reputation: int) -> float:
    return 1.0 - ((int(reputation) - 10) * 0.02)

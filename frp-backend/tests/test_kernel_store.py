from __future__ import annotations

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.colony import ProductionLedger, QuestSeed
from engine.kernel.effects import EffectDef, EffectQueue
from engine.kernel.items import ItemDef, ItemInstance
from engine.kernel.spells import SpellSlot, Spellbook
from engine.kernel.store import (
    StoreDef,
    StoreItem,
    StoreService,
    adjust_store_prices,
    attempt_steal,
    buy_healing,
    buy_identification,
    buy_item,
    buy_repair,
    compute_buy_price,
    compute_sell_price,
    rent_room,
    sell_item,
)


def _actor(
    actor_id: str,
    *,
    gold: int = 0,
    cha: int = 10,
    reputation: int = 10,
    pickpocket: int = 0,
    hp: int = 20,
    max_hp: int = 20,
    effect_registry: dict[str, EffectDef] | None = None,
    spellbook: Spellbook | None = None,
) -> ActorRecord:
    raw_payload = {"reputation": reputation}
    if effect_registry is not None:
        raw_payload["effect_registry"] = effect_registry
    if spellbook is not None:
        raw_payload["spellbooks"] = {"wizard": spellbook}
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="pc"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"gold": gold, "PRE": cha, "hp": hp, "max_hp": max_hp},
        skills={"pickpocket": pickpocket},
        inventory=[],
        effect_queue=EffectQueue(actor_id=actor_id),
        raw_payload=raw_payload,
    )


def _item_def(item_def_id: str, *, base_price: int, lore_to_identify: int = 0) -> ItemDef:
    return ItemDef(
        item_def_id=item_def_id,
        label=item_def_id.replace("_", " ").title(),
        item_type="misc",
        item_category="trade_good",
        weight=1,
        base_price=base_price,
        lore_to_identify=lore_to_identify,
    )


def test_ac01_compute_buy_price_uses_markup_cha_and_reputation():
    item_def = _item_def("iron_ore", base_price=100)
    store = StoreDef(store_id="smithy", label="Smithy", store_type="shop", buy_markup=1.5)

    assert compute_buy_price(item_def, store, buyer_pre=18, buyer_rep=15) == 108


def test_ac02_compute_sell_price_uses_markup_cha_and_reputation():
    item_def = _item_def("iron_ore", base_price=100)
    store = StoreDef(store_id="smithy", label="Smithy", store_type="shop", sell_markup=0.5)
    store_item = StoreItem(item_def_id="iron_ore")

    assert compute_sell_price(item_def, store, store_item, seller_pre=8, seller_rep=10) == 52


def test_ac03_compute_sell_price_applies_depreciation_chain():
    item_def = _item_def("iron_ore", base_price=100)
    store = StoreDef(store_id="smithy", label="Smithy", store_type="shop", sell_markup=0.5)
    store_item = StoreItem(item_def_id="iron_ore", sales_count=3)

    assert compute_sell_price(item_def, store, store_item, seller_pre=10, seller_rep=10) == 36


def test_ac04_buy_item_succeeds_and_reduces_gold():
    buyer = _actor("buyer", gold=200)
    item_def = _item_def("iron_ore", base_price=100)
    store = StoreDef(
        store_id="smithy",
        label="Smithy",
        store_type="shop",
        buy_markup=1.5,
        items=[StoreItem(item_def_id="iron_ore", quantity=1)],
    )

    success, _message = buy_item(buyer, store, "iron_ore", 1, {"iron_ore": item_def})

    assert success is True
    assert buyer.stats["gold"] == 50
    assert len(buyer.inventory) == 1
    assert store.items[0].quantity == 0


def test_ac05_buy_item_fails_with_insufficient_gold():
    buyer = _actor("buyer", gold=100)
    item_def = _item_def("iron_ore", base_price=100)
    store = StoreDef(
        store_id="smithy",
        label="Smithy",
        store_type="shop",
        buy_markup=1.5,
        items=[StoreItem(item_def_id="iron_ore", quantity=1)],
    )

    success, _message = buy_item(buyer, store, "iron_ore", 1, {"iron_ore": item_def})

    assert success is False
    assert buyer.stats["gold"] == 100
    assert buyer.inventory == []
    assert store.items[0].quantity == 1


def test_ac06_attempt_steal_succeeds_when_roll_plus_skill_meets_dc():
    thief = _actor("thief", pickpocket=10)
    store = StoreDef(
        store_id="market",
        label="Market",
        store_type="shop",
        steal_difficulty=60,
        items=[StoreItem(item_def_id="gem", quantity=1)],
    )

    success, _message = attempt_steal(thief, store, "gem", d100_roll=15)

    assert success is True
    assert len(thief.inventory) == 1
    assert thief.inventory[0].item_def_id == "gem"


def test_ac07_attempt_steal_failure_makes_store_hostile_and_reduces_reputation():
    thief = _actor("thief", reputation=10, pickpocket=10)
    store = StoreDef(
        store_id="market",
        label="Market",
        store_type="shop",
        steal_difficulty=60,
        items=[StoreItem(item_def_id="gem", quantity=1)],
    )

    success, _message = attempt_steal(thief, store, "gem", d100_roll=5)

    assert success is False
    assert store.hostile is True
    assert thief.raw_payload["reputation"] == 8


def test_ac08_buy_identification_succeeds_when_store_lore_is_sufficient():
    buyer = _actor("buyer", gold=100)
    service = StoreService(service_id="identify_basic", service_type="identify", label="Identify", price=25)
    store = StoreDef(store_id="temple", label="Temple", store_type="temple", lore=50, services=[service])
    item_def = _item_def("mystery_ring", base_price=100, lore_to_identify=40)
    item = ItemInstance(instance_id="ring_1", item_def_id="mystery_ring")

    success, _message = buy_identification(buyer, store, item, item_def)

    assert success is True
    assert item.identified is True
    assert buyer.stats["gold"] == 75


def test_ac09_buy_repair_uses_wear_ratio_cost_formula():
    buyer = _actor("buyer", gold=100)
    repair_service = StoreService(service_id="repair_basic", service_type="repair", label="Repair", price=0)
    store = StoreDef(store_id="smithy", label="Smithy", store_type="shop", services=[repair_service])
    item_def = _item_def("mail_armor", base_price=200)
    item = ItemInstance(instance_id="mail_1", item_def_id="mail_armor", wear=50, max_wear=100)

    success, cost = buy_repair(buyer, store, item, item_def)

    assert success is True
    assert cost == 50
    assert item.wear == 0
    assert buyer.stats["gold"] == 50


def test_ac10_adjust_store_prices_lowers_surplus_markup():
    store = StoreDef(
        store_id="smithy",
        label="Smithy",
        store_type="shop",
        items=[StoreItem(item_def_id="iron_ore", quantity=5)],
    )
    ledger = ProductionLedger(
        economy={"stockpile_value": 100},
        surpluses=["iron_ore"],
        shortages=[],
        quest_seeds=[QuestSeed(quest_id="q1", kind="trade", title="Trade")],
    )

    adjust_store_prices(store, ledger)

    assert store.items[0].price_multiplier == 0.8


def test_sell_item_increments_store_stock_and_sales_count():
    seller = _actor("seller", gold=0)
    item_def = _item_def("iron_ore", base_price=100)
    item = ItemInstance(instance_id="ore_1", item_def_id="iron_ore")
    seller.inventory.append(item)
    store = StoreDef(store_id="smithy", label="Smithy", store_type="shop", sell_markup=0.5)

    success, _message, gold_received = sell_item(seller, store, item, {"iron_ore": item_def})

    assert success is True
    assert gold_received == 50
    assert seller.stats["gold"] == 50
    assert seller.inventory == []
    assert store.items[0].quantity == 1
    assert store.items[0].sales_count == 1


def test_healing_and_rest_services_apply_effects_and_refresh_spellbook():
    heal_effect = EffectDef(
        effect_def_id="heal_8",
        label="Heal 8",
        category="healing",
        healing_per_tick=8,
        timing_mode="instant",
    )
    spellbook = Spellbook(
        actor_id="buyer",
        spell_type="wizard",
        slots={1: [SpellSlot(spell_level=1, spell_id="magic_missile", memorized=True, expended=True)]},
    )
    buyer = _actor(
        "buyer",
        gold=100,
        hp=5,
        max_hp=20,
        effect_registry={"heal_8": heal_effect},
        spellbook=spellbook,
    )
    store = StoreDef(
        store_id="temple_inn",
        label="Temple Inn",
        store_type="temple",
        services=[
            StoreService(service_id="cure", service_type="healing", label="Cure", price=20, effect_id="heal_8"),
            StoreService(service_id="room_basic", service_type="room", label="Room", price=15, room_quality=1.0),
        ],
    )

    healing_success, _ = buy_healing(buyer, store, "cure")
    room_success, _ = rent_room(buyer, store, "room_basic")

    assert healing_success is True
    assert room_success is True
    assert buyer.stats["hp"] == 20
    assert buyer.stats["gold"] == 65
    assert spellbook.slots[1][0].expended is False
    assert buyer.raw_payload["hours_rested"] == 8

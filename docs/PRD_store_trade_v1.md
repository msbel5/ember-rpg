# PRD: Store & Trade System V1
**Project:** Ember RPG
**Phase:** 3
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the store/trade system synthesizing GemRB M13 (Store — buy/sell/steal/identify/repair, CHA-based pricing, store types) with DF M11 (Trade caravans, import/export, price fluctuation from supply/demand). Stores are typed (shop, tavern, inn, temple) with CHA+reputation pricing, depreciation for repeated sales, and integration with colony economy.

## 2. Scope

### In scope
- `StoreDef`: static store template (type, markup, items, services)
- Store types: SHOP (buy/sell), TAVERN (drinks, rumors), INN (rooms, rest), TEMPLE (healing, identify)
- Buy/sell pricing: `final_price = base_price * store_markup * cha_modifier * reputation_modifier`
- CHA effect: higher CHA → better prices
- Reputation effect: higher reputation → better prices
- Depreciation: selling same item repeatedly reduces buy price
- Steal attempt: thief skill vs steal_difficulty
- Identification service: temple/sage identifies items for gold
- Repair service: blacksmith repairs worn items for gold
- Temple healing: cure spells available for gold
- Inn rest: rent room type, trigger rest/memorization refresh
- Colony trade integration: caravans arrive with goods, prices fluctuate by supply/demand

### Out of scope
- Barter between players
- Auction house
- Store inventory generation (data files)

## 3. Functional Requirements (FR)

**FR-01 (StoreDef):** Defines: store_id, store_type (shop/tavern/inn/temple), buy_markup (%), sell_markup (%), steal_difficulty, lore (for identification), capacity, inventory (list of item_def_ids with quantities and prices), services (healing spells, rooms, drinks).

**FR-02 (Pricing):** Buy price: `item.base_price * buy_markup * cha_modifier(buyer.CHA) * rep_modifier(buyer.reputation)`. Sell price: `item.base_price * sell_markup * cha_modifier(seller.CHA) * rep_modifier(seller.reputation)`. CHA modifier: `1.0 - (CHA - 10) * 0.025` (CHA 18 → 0.8, CHA 6 → 1.1). Rep modifier: `1.0 - (reputation - 10) * 0.02`.

**FR-03 (Depreciation):** When the same item_def_id is sold to the same store repeatedly, each subsequent sale reduces the store's buy price by 10% (multiplicative). Track sales_count per item_def_id per store.

**FR-04 (Buy Transaction):** `buy_item(buyer, store, item_def_id, quantity)`: check buyer has enough gold → remove gold → add item to buyer inventory → remove from store stock. Fail if insufficient gold or item not in stock.

**FR-05 (Sell Transaction):** `sell_item(seller, store, item_instance_id)`: compute sell price with depreciation → add gold to seller → remove item from seller → add to store stock.

**FR-06 (Steal):** `attempt_steal(thief, store, item_def_id, d100_roll)`: success if `d100_roll + thief.skills["pickpocket"] * 5 >= steal_difficulty`. Success: item added to thief inventory silently. Failure: store becomes hostile, reputation -2.

**FR-07 (Temple Healing):** Temple offers cure spells at fixed prices. `buy_healing(buyer, store, cure_id)`: check gold → apply healing effect → deduct gold.

**FR-08 (Inn Rest):** Inn offers room types at prices. `rent_room(actor, store, room_type)`: check gold → deduct → trigger rest (spell slot refresh, HP recovery, 8-hour time advance).

**FR-09 (Identification Service):** `buy_identification(buyer, store, item_instance_id)`: check gold → check store.lore >= item.lore_to_identify → identify item → deduct gold. Fail if store lore insufficient.

**FR-10 (Repair Service):** `buy_repair(buyer, store, item_instance_id)`: repair cost = `base_price * (wear / max_wear) * 0.5`. Reset item.wear to 0.

**FR-11 (Colony Trade):** Caravan arrival adds items to local store. Prices adjust: items in surplus → lower markup. Items in shortage → higher markup. `adjust_prices(store, colony_ledger)`: surplus item markup *= 0.8, shortage item markup *= 1.3.

## 4. Data Structures

```python
@dataclass
class StoreItem:
    item_def_id: str
    quantity: int = -1       # -1 = infinite stock
    base_price_override: int | None = None  # None = use ItemDef.base_price
    sales_count: int = 0     # For depreciation tracking

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class StoreService:
    service_id: str
    service_type: str        # "healing" | "room" | "drink" | "identify" | "repair"
    label: str
    price: int
    effect_id: str = ""      # For healing: EffectDef ID
    room_quality: float = 1.0  # For inn: rest quality multiplier

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class StoreDef:
    store_id: str
    label: str
    store_type: str          # "shop" | "tavern" | "inn" | "temple"
    buy_markup: float = 1.5  # 150% of base for buying
    sell_markup: float = 0.5 # 50% of base for selling
    steal_difficulty: int = 50
    lore: int = 0            # For identification service
    capacity: int = 100
    items: list[StoreItem] = field(default_factory=list)
    services: list[StoreService] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreDef": ...
```

## 5. Public API

```python
def compute_buy_price(item_def: ItemDef, store: StoreDef, buyer_cha: int, buyer_rep: int) -> int:
    """Compute price for buyer to purchase item from store."""

def compute_sell_price(item_def: ItemDef, store: StoreDef, store_item: StoreItem, seller_cha: int, seller_rep: int) -> int:
    """Compute price store will pay for item, including depreciation."""

def buy_item(buyer: ActorRecord, store: StoreDef, item_def_id: str, quantity: int, item_registry: dict) -> tuple[bool, str]:
    """Execute purchase. Returns (success, message)."""

def sell_item(seller: ActorRecord, store: StoreDef, item_instance: ItemInstance, item_registry: dict) -> tuple[bool, str, int]:
    """Execute sale. Returns (success, message, gold_received)."""

def attempt_steal(thief: ActorRecord, store: StoreDef, item_def_id: str, d100_roll: int) -> tuple[bool, str]:
    """Attempt theft. Returns (success, message). Failure triggers hostility."""

def buy_healing(buyer: ActorRecord, store: StoreDef, service_id: str) -> tuple[bool, str]:
    """Purchase healing service from temple."""

def rent_room(actor: ActorRecord, store: StoreDef, service_id: str) -> tuple[bool, str]:
    """Rent inn room. Triggers rest cycle."""

def buy_identification(buyer: ActorRecord, store: StoreDef, item: ItemInstance, item_def: ItemDef) -> tuple[bool, str]:
    """Purchase identification service."""

def buy_repair(buyer: ActorRecord, store: StoreDef, item: ItemInstance, item_def: ItemDef) -> tuple[bool, int]:
    """Repair item. Returns (success, cost)."""

def adjust_store_prices(store: StoreDef, colony_ledger: "ProductionLedger") -> None:
    """Adjust store markups based on colony supply/demand."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-02]: Given item base_price=100, buy_markup=1.5, buyer CHA=18 (mod=0.8), rep=15 (mod=0.9), then buy price = int(100 * 1.5 * 0.8 * 0.9) = 108.

AC-02 [FR-02]: Given same item, sell_markup=0.5, seller CHA=8 (mod=1.05), rep=10 (mod=1.0), then sell price = int(100 * 0.5 * 1.05 * 1.0) = 52.

AC-03 [FR-03]: Given item sold 3 times, depreciation = 0.9^3 = 0.729, sell price reduced accordingly.

AC-04 [FR-04]: Given buyer with 200 gold and item buy_price=150, when buy_item called, then success and buyer gold=50.

AC-05 [FR-04]: Given buyer with 100 gold and buy_price=150, then buy fails.

AC-06 [FR-06]: Given thief pickpocket=10 (bonus=50) and steal_difficulty=60, d100_roll=15 (total=65), then steal succeeds.

AC-07 [FR-06]: Given d100_roll=5 (total=55 < 60), then steal fails and reputation decreases.

AC-08 [FR-09]: Given store lore=50 and item lore_to_identify=40, then identification succeeds.

AC-09 [FR-10]: Given item base_price=200, wear=50, max_wear=100, repair cost = int(200 * 0.5 * 0.5) = 50.

AC-10 [FR-11]: Given colony surplus of "iron_ore", when adjust_store_prices called, then iron_ore store markup *= 0.8.

## 7-10. (Performance, Errors, Integration, Tests)
- All transactions < 0.1 ms
- Insufficient gold: return (False, message), no state change
- Integration: Item System for inventory, Colony for supply/demand, Effect System for healing, Actor for gold/CHA/rep
- Tests: buy/sell at boundary gold, depreciation chain, steal success/failure, all service types, serialization round-trip

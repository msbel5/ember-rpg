"""
Recipe-driven economy for Ember RPG.
FR-33..FR-38: Crafting recipes, location stock tracking, scarcity pricing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Recipe definitions ───────────────────────────────────────────────

@dataclass(frozen=True)
class Recipe:
    """A crafting recipe: inputs → output."""
    name: str
    inputs: Dict[str, int]       # item_id → quantity required
    output: str                  # item_id produced
    output_qty: int = 1
    craft_hours: float = 1.0     # in-game hours to craft
    skill_required: Optional[str] = None
    skill_level: int = 0
    base_price: float = 10.0     # gold value of one output unit


RECIPES: Dict[str, Recipe] = {
    "iron_bar": Recipe(
        name="Iron Bar",
        inputs={"iron_ore": 2, "coal": 1},
        output="iron_bar",
        craft_hours=2.0,
        skill_required="smithing",
        skill_level=1,
        base_price=8.0,
    ),
    "steel_bar": Recipe(
        name="Steel Bar",
        inputs={"iron_bar": 1, "coal": 2},
        output="steel_bar",
        craft_hours=3.0,
        skill_required="smithing",
        skill_level=3,
        base_price=20.0,
    ),
    "iron_sword": Recipe(
        name="Iron Sword",
        inputs={"iron_bar": 3, "leather": 1},
        output="iron_sword",
        craft_hours=4.0,
        skill_required="smithing",
        skill_level=2,
        base_price=35.0,
    ),
    "ale": Recipe(
        name="Ale",
        inputs={"grain": 3, "water": 2},
        output="ale",
        output_qty=4,
        craft_hours=6.0,
        skill_required="brewing",
        skill_level=1,
        base_price=3.0,
    ),
    "bread": Recipe(
        name="Bread",
        inputs={"grain": 2, "water": 1},
        output="bread",
        output_qty=3,
        craft_hours=1.5,
        skill_required="cooking",
        skill_level=0,
        base_price=2.0,
    ),
    "healing_potion": Recipe(
        name="Healing Potion",
        inputs={"herb": 3, "water": 1, "glass_vial": 1},
        output="healing_potion",
        craft_hours=2.0,
        skill_required="alchemy",
        skill_level=2,
        base_price=25.0,
    ),
    "leather_armor": Recipe(
        name="Leather Armor",
        inputs={"leather": 5, "thread": 2},
        output="leather_armor",
        craft_hours=5.0,
        skill_required="leatherworking",
        skill_level=2,
        base_price=40.0,
    ),
    "arrow_bundle": Recipe(
        name="Arrow Bundle",
        inputs={"wood": 2, "iron_bar": 1, "feather": 3},
        output="arrow_bundle",
        output_qty=12,
        craft_hours=1.0,
        skill_required="fletching",
        skill_level=1,
        base_price=5.0,
    ),
    "silver_ring": Recipe(
        name="Silver Ring",
        inputs={"silver_bar": 1},
        output="silver_ring",
        craft_hours=2.0,
        skill_required="jeweler",
        skill_level=2,
        base_price=50.0,
    ),
    "torch": Recipe(
        name="Torch",
        inputs={"wood": 1, "cloth": 1},
        output="torch",
        output_qty=2,
        craft_hours=0.5,
        base_price=1.0,
    ),
}


# ── Location stock & pricing ─────────────────────────────────────────

# Scarcity thresholds (fraction of baseline stock → price multiplier).
_SCARCITY_RULES: List[Tuple[float, float]] = [
    (0.0, 3.0),    # out of stock → 3×
    (0.2, 2.0),    # < 20 % → 2×
    (0.5, 1.3),    # < 50 % → 1.3×
    (1.5, 0.7),    # > 150 % → 0.7× (oversupply)
]


class LocationStock:
    """Manages item stock for a single location (town, outpost, etc.)."""

    def __init__(
        self,
        location_id: str,
        baseline: Optional[Dict[str, int]] = None,
    ):
        self.location_id = location_id
        # baseline = "normal" stock level for each item
        self.baseline: Dict[str, int] = dict(baseline or {})
        # current quantities
        self.stock: Dict[str, int] = dict(self.baseline)

    # ── stock helpers ────────────────────────────────────────────────
    def add_stock(self, item: str, qty: int) -> None:
        self.stock[item] = self.stock.get(item, 0) + qty
        if item not in self.baseline:
            self.baseline[item] = qty

    def remove_stock(self, item: str, qty: int) -> int:
        """Remove up to *qty* units. Returns amount actually removed."""
        available = self.stock.get(item, 0)
        removed = min(available, qty)
        self.stock[item] = available - removed
        return removed

    def get_stock(self, item: str) -> int:
        return self.stock.get(item, 0)

    # ── crafting ─────────────────────────────────────────────────────
    def produce(self, recipe_key: str) -> bool:
        """Attempt to craft using a recipe. Consumes inputs, adds output.

        Returns ``True`` on success, ``False`` if inputs are insufficient.
        """
        recipe = RECIPES.get(recipe_key)
        if recipe is None:
            raise KeyError(f"Unknown recipe: {recipe_key}")

        # check inputs
        for item, needed in recipe.inputs.items():
            if self.stock.get(item, 0) < needed:
                return False

        # consume inputs
        for item, needed in recipe.inputs.items():
            self.stock[item] -= needed

        # add output
        self.stock[recipe.output] = (
            self.stock.get(recipe.output, 0) + recipe.output_qty
        )
        return True

    # ── pricing ──────────────────────────────────────────────────────
    def get_price_modifier(self, item: str) -> float:
        """Return a price multiplier based on current vs baseline stock.

        If the item has no baseline entry the modifier is 1.0.

        Scarcity tiers:
        - stock == 0        → 3.0x
        - stock < 20%       → 2.0x
        - stock < 50%       → 1.3x
        - stock 50%-150%    → 1.0x (normal)
        - stock > 150%      → 0.7x (oversupply)
        """
        base = self.baseline.get(item, 0)
        if base <= 0:
            return 1.0
        ratio = self.stock.get(item, 0) / base

        if ratio <= 0.0:
            return 3.0
        if ratio < 0.2:
            return 2.0
        if ratio < 0.5:
            return 1.3
        if ratio > 1.5:
            return 0.7
        return 1.0

    def get_effective_price(self, item: str) -> float:
        """Return the effective gold price for *item* at this location."""
        # Find a recipe that produces this item for its base_price.
        base = 10.0
        for recipe in RECIPES.values():
            if recipe.output == item:
                base = recipe.base_price
                break
        return round(base * self.get_price_modifier(item), 2)

    def to_dict(self) -> dict:
        """Serialize location stock for save/load."""
        return {
            "location_id": self.location_id,
            "baseline": dict(self.baseline),
            "stock": dict(self.stock),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LocationStock":
        """Deserialize location stock from a dict."""
        ls = cls(
            location_id=data.get("location_id", "default"),
            baseline=data.get("baseline", {}),
        )
        ls.stock = dict(data.get("stock", ls.baseline))
        return ls

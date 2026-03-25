"""
Crafting system for Ember RPG — Sprint 4.
FR-19..FR-24: Data-driven recipes, workstation detection, skill-check quality,
40+ recipes across 5 disciplines (Smithing, Alchemy, Cooking, Carpentry,
Leatherworking).

Design references: DF reactions, Rimworld bills, PRD Section 6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ── Quality system ──────────────────────────────────────────────────────

class QualityTier(Enum):
    """Result quality determined by skill-check margin (PRD 6.3)."""
    RUINED = "ruined"
    SHODDY = "shoddy"
    NORMAL = "normal"
    FINE = "fine"
    SUPERIOR = "superior"
    MASTERWORK = "masterwork"


def determine_quality(roll: int, dc: int) -> QualityTier:
    """Map a d20+modifier *roll* against *dc* to a quality tier.

    PRD 6.3 thresholds:
      fail by 5+  → RUINED
      fail by 1-4 → SHODDY
      meet DC     → NORMAL
      beat by 3-5 → FINE
      beat by 6-9 → SUPERIOR
      beat by 10+ → MASTERWORK
    """
    margin = roll - dc
    if margin <= -5:
        return QualityTier.RUINED
    if margin < 0:
        return QualityTier.SHODDY
    if margin < 3:
        return QualityTier.NORMAL
    if margin < 6:
        return QualityTier.FINE
    if margin < 10:
        return QualityTier.SUPERIOR
    return QualityTier.MASTERWORK


QUALITY_MODIFIERS: Dict[QualityTier, Dict[str, float]] = {
    QualityTier.RUINED:     {"damage_mod": 0,  "armor_mod": 0,  "value_mult": 0.0},
    QualityTier.SHODDY:     {"damage_mod": -2, "armor_mod": -2, "value_mult": 0.7},
    QualityTier.NORMAL:     {"damage_mod": 0,  "armor_mod": 0,  "value_mult": 1.0},
    QualityTier.FINE:       {"damage_mod": 1,  "armor_mod": 1,  "value_mult": 1.5},
    QualityTier.SUPERIOR:   {"damage_mod": 2,  "armor_mod": 2,  "value_mult": 2.0},
    QualityTier.MASTERWORK: {"damage_mod": 3,  "armor_mod": 3,  "value_mult": 3.0},
}


# ── Recipe data structures ──────────────────────────────────────────────

@dataclass(frozen=True)
class Ingredient:
    """One ingredient line in a recipe."""
    item_id: str
    quantity: int
    material_class: Optional[str] = None  # polymorphic match (e.g. "metal_bar")


@dataclass(frozen=True)
class Product:
    """One output line in a recipe."""
    item_id: str
    quantity: int = 1
    inherit_material: bool = False  # product inherits primary ingredient material


@dataclass(frozen=True)
class CraftingRecipe:
    """A complete crafting recipe."""
    id: str
    name: str
    workstation: str          # "forge", "alchemy_bench", "workbench", "kitchen", "campfire", "any"
    skill: str                # "smithing", "alchemy", "cooking", "carpentry", "leatherworking"
    skill_dc: int             # difficulty class
    ap_cost: int              # action points
    ingredients: Tuple[Ingredient, ...]
    products: Tuple[Product, ...]
    tools: Tuple[str, ...] = ()
    failure_result: Optional[str] = None  # item_id produced on ruined result, None = nothing
    xp_reward: int = 10


@dataclass
class CraftResult:
    """Outcome returned by ``CraftingSystem.attempt_craft``."""
    success: bool
    quality: QualityTier
    products: List[Tuple[str, int]]   # (item_id, quantity) pairs produced
    xp_gained: int
    narrative: str


# ── Helper: build Ingredient/Product tuples concisely ────────────────────

def _ing(item_id: str, qty: int, mat_class: Optional[str] = None) -> Ingredient:
    return Ingredient(item_id=item_id, quantity=qty, material_class=mat_class)


def _prod(item_id: str, qty: int = 1, inherit: bool = False) -> Product:
    return Product(item_id=item_id, quantity=qty, inherit_material=inherit)


# ── 51 Recipes ───────────────────────────────────────────────────────────

# ---------- SMITHING (forge) ----------

_SMITHING_RECIPES: List[CraftingRecipe] = [
    CraftingRecipe(
        id="iron_bar", name="Iron Bar", workstation="forge",
        skill="smithing", skill_dc=10, ap_cost=5,
        ingredients=(_ing("iron_ore", 2), _ing("coal", 1)),
        products=(_prod("iron_bar"),),
        tools=("hammer", "tongs"),
        failure_result="slag", xp_reward=8,
    ),
    CraftingRecipe(
        id="steel_bar", name="Steel Bar", workstation="forge",
        skill="smithing", skill_dc=14, ap_cost=8,
        ingredients=(_ing("iron_bar", 1), _ing("coal", 1), _ing("flux", 1)),
        products=(_prod("steel_bar"),),
        tools=("hammer", "tongs"),
        failure_result="slag", xp_reward=15,
    ),
    CraftingRecipe(
        id="iron_sword", name="Iron Sword", workstation="forge",
        skill="smithing", skill_dc=12, ap_cost=10,
        ingredients=(_ing("iron_bar", 2),),
        products=(_prod("iron_sword", inherit=True),),
        tools=("hammer", "tongs"),
        failure_result="ruined_blade", xp_reward=20,
    ),
    CraftingRecipe(
        id="steel_sword", name="Steel Sword", workstation="forge",
        skill="smithing", skill_dc=16, ap_cost=15,
        ingredients=(_ing("steel_bar", 2),),
        products=(_prod("steel_sword", inherit=True),),
        tools=("hammer", "tongs"),
        failure_result="ruined_blade", xp_reward=30,
    ),
    CraftingRecipe(
        id="iron_shield", name="Iron Shield", workstation="forge",
        skill="smithing", skill_dc=13, ap_cost=12,
        ingredients=(_ing("iron_bar", 3), _ing("leather", 1)),
        products=(_prod("iron_shield", inherit=True),),
        tools=("hammer",),
        failure_result="scrap_metal", xp_reward=22,
    ),
    CraftingRecipe(
        id="chain_mail", name="Chain Mail", workstation="forge",
        skill="smithing", skill_dc=15, ap_cost=20,
        ingredients=(_ing("iron_bar", 5),),
        products=(_prod("chain_mail", inherit=True),),
        tools=("hammer", "tongs", "wire_draw"),
        failure_result="scrap_metal", xp_reward=35,
    ),
    CraftingRecipe(
        id="plate_armor", name="Plate Armor", workstation="forge",
        skill="smithing", skill_dc=18, ap_cost=25,
        ingredients=(_ing("steel_bar", 4), _ing("leather", 2)),
        products=(_prod("plate_armor", inherit=True),),
        tools=("hammer", "tongs"),
        failure_result="scrap_metal", xp_reward=50,
    ),
    CraftingRecipe(
        id="arrowheads", name="Arrowheads", workstation="forge",
        skill="smithing", skill_dc=10, ap_cost=3,
        ingredients=(_ing("iron_bar", 1),),
        products=(_prod("iron_arrowhead", 10),),
        tools=("hammer",),
        failure_result="slag", xp_reward=6,
    ),
    CraftingRecipe(
        id="iron_nails", name="Iron Nails", workstation="forge",
        skill="smithing", skill_dc=8, ap_cost=2,
        ingredients=(_ing("iron_bar", 1),),
        products=(_prod("iron_nail", 20),),
        tools=("hammer",),
        failure_result=None, xp_reward=4,
    ),
    CraftingRecipe(
        id="horseshoe", name="Horseshoe", workstation="forge",
        skill="smithing", skill_dc=10, ap_cost=4,
        ingredients=(_ing("iron_bar", 1),),
        products=(_prod("horseshoe", 2),),
        tools=("hammer", "tongs"),
        failure_result=None, xp_reward=6,
    ),
    CraftingRecipe(
        id="iron_helm", name="Iron Helm", workstation="forge",
        skill="smithing", skill_dc=13, ap_cost=10,
        ingredients=(_ing("iron_bar", 2), _ing("leather", 1)),
        products=(_prod("iron_helm", inherit=True),),
        tools=("hammer",),
        failure_result="scrap_metal", xp_reward=18,
    ),
    CraftingRecipe(
        id="steel_dagger", name="Steel Dagger", workstation="forge",
        skill="smithing", skill_dc=14, ap_cost=8,
        ingredients=(_ing("steel_bar", 1),),
        products=(_prod("steel_dagger", inherit=True),),
        tools=("hammer", "tongs"),
        failure_result="ruined_blade", xp_reward=18,
    ),
    CraftingRecipe(
        id="mace", name="Mace", workstation="forge",
        skill="smithing", skill_dc=13, ap_cost=10,
        ingredients=(_ing("iron_bar", 2), _ing("wood_plank", 1)),
        products=(_prod("mace", inherit=True),),
        tools=("hammer",),
        failure_result="scrap_metal", xp_reward=20,
    ),
    CraftingRecipe(
        id="war_hammer", name="War Hammer", workstation="forge",
        skill="smithing", skill_dc=15, ap_cost=14,
        ingredients=(_ing("steel_bar", 2), _ing("wood_plank", 1)),
        products=(_prod("war_hammer", inherit=True),),
        tools=("hammer", "tongs"),
        failure_result="scrap_metal", xp_reward=28,
    ),
]

# ---------- ALCHEMY (alchemy_bench) ----------

_ALCHEMY_RECIPES: List[CraftingRecipe] = [
    CraftingRecipe(
        id="healing_potion", name="Healing Potion", workstation="alchemy_bench",
        skill="alchemy", skill_dc=12, ap_cost=5,
        ingredients=(_ing("herb_heal", 1), _ing("water", 1), _ing("glass_vial", 1)),
        products=(_prod("healing_potion"),),
        tools=("mortar",),
        failure_result="failed_mixture", xp_reward=12,
    ),
    CraftingRecipe(
        id="mana_potion", name="Mana Potion", workstation="alchemy_bench",
        skill="alchemy", skill_dc=14, ap_cost=5,
        ingredients=(_ing("moonflower", 1), _ing("spring_water", 1), _ing("glass_vial", 1)),
        products=(_prod("mana_potion"),),
        tools=("mortar",),
        failure_result="failed_mixture", xp_reward=15,
    ),
    CraftingRecipe(
        id="poison_vial", name="Poison Vial", workstation="alchemy_bench",
        skill="alchemy", skill_dc=15, ap_cost=5,
        ingredients=(_ing("nightshade", 1), _ing("venom_sac", 1), _ing("glass_vial", 1)),
        products=(_prod("poison_vial"),),
        tools=("mortar",),
        failure_result="failed_mixture", xp_reward=18,
    ),
    CraftingRecipe(
        id="antidote", name="Antidote", workstation="alchemy_bench",
        skill="alchemy", skill_dc=13, ap_cost=5,
        ingredients=(_ing("herb_cure", 1), _ing("honey", 1), _ing("glass_vial", 1)),
        products=(_prod("antidote"),),
        tools=("mortar",),
        failure_result="failed_mixture", xp_reward=14,
    ),
    CraftingRecipe(
        id="fire_bomb", name="Fire Bomb", workstation="alchemy_bench",
        skill="alchemy", skill_dc=16, ap_cost=8,
        ingredients=(_ing("oil", 1), _ing("sulfur", 1), _ing("glass_vial", 1)),
        products=(_prod("fire_bomb"),),
        tools=("mortar",),
        failure_result="failed_mixture", xp_reward=20,
    ),
    CraftingRecipe(
        id="smoke_bomb", name="Smoke Bomb", workstation="alchemy_bench",
        skill="alchemy", skill_dc=12, ap_cost=5,
        ingredients=(_ing("charcoal", 1), _ing("saltpeter", 1), _ing("cloth", 1)),
        products=(_prod("smoke_bomb"),),
        tools=(),
        failure_result=None, xp_reward=10,
    ),
    CraftingRecipe(
        id="strength_elixir", name="Strength Elixir", workstation="alchemy_bench",
        skill="alchemy", skill_dc=17, ap_cost=8,
        ingredients=(_ing("ogre_moss", 1), _ing("iron_dust", 1), _ing("glass_vial", 1)),
        products=(_prod("strength_elixir"),),
        tools=("mortar",),
        failure_result="failed_mixture", xp_reward=22,
    ),
    CraftingRecipe(
        id="speed_potion", name="Speed Potion", workstation="alchemy_bench",
        skill="alchemy", skill_dc=15, ap_cost=6,
        ingredients=(_ing("windleaf", 1), _ing("spring_water", 1), _ing("glass_vial", 1)),
        products=(_prod("speed_potion"),),
        tools=("mortar",),
        failure_result="failed_mixture", xp_reward=18,
    ),
    CraftingRecipe(
        id="invisibility_potion", name="Invisibility Potion", workstation="alchemy_bench",
        skill="alchemy", skill_dc=20, ap_cost=10,
        ingredients=(_ing("ghost_lichen", 1), _ing("moonflower", 1), _ing("glass_vial", 1)),
        products=(_prod("invisibility_potion"),),
        tools=("mortar", "alembic"),
        failure_result="failed_mixture", xp_reward=30,
    ),
    CraftingRecipe(
        id="resistance_potion", name="Resistance Potion", workstation="alchemy_bench",
        skill="alchemy", skill_dc=14, ap_cost=6,
        ingredients=(_ing("stonecap", 1), _ing("water", 1), _ing("glass_vial", 1)),
        products=(_prod("resistance_potion"),),
        tools=("mortar",),
        failure_result="failed_mixture", xp_reward=15,
    ),
]

# ---------- COOKING (kitchen / campfire) ----------

_COOKING_RECIPES: List[CraftingRecipe] = [
    CraftingRecipe(
        id="bread", name="Bread", workstation="kitchen",
        skill="cooking", skill_dc=8, ap_cost=3,
        ingredients=(_ing("flour", 2), _ing("water", 1)),
        products=(_prod("bread", 2),),
        tools=(),
        failure_result="burnt_food", xp_reward=5,
    ),
    CraftingRecipe(
        id="stew", name="Stew", workstation="kitchen",
        skill="cooking", skill_dc=10, ap_cost=5,
        ingredients=(_ing("meat", 1), _ing("vegetable", 1), _ing("water", 1)),
        products=(_prod("stew", 2),),
        tools=(),
        failure_result="burnt_food", xp_reward=8,
    ),
    CraftingRecipe(
        id="ale", name="Ale", workstation="kitchen",
        skill="cooking", skill_dc=12, ap_cost=10,
        ingredients=(_ing("grain", 3), _ing("water", 1), _ing("yeast", 1)),
        products=(_prod("ale", 3),),
        tools=(),
        failure_result="spoiled_brew", xp_reward=12,
    ),
    CraftingRecipe(
        id="dried_meat", name="Dried Meat", workstation="campfire",
        skill="cooking", skill_dc=8, ap_cost=8,
        ingredients=(_ing("meat", 2), _ing("salt", 1)),
        products=(_prod("dried_meat", 3),),
        tools=(),
        failure_result=None, xp_reward=6,
    ),
    CraftingRecipe(
        id="trail_rations", name="Trail Rations", workstation="kitchen",
        skill="cooking", skill_dc=10, ap_cost=5,
        ingredients=(_ing("bread", 1), _ing("dried_meat", 1), _ing("fruit", 1)),
        products=(_prod("trail_rations", 3),),
        tools=(),
        failure_result=None, xp_reward=8,
    ),
    CraftingRecipe(
        id="fish_fillet", name="Fish Fillet", workstation="campfire",
        skill="cooking", skill_dc=9, ap_cost=4,
        ingredients=(_ing("raw_fish", 1), _ing("salt", 1)),
        products=(_prod("fish_fillet", 2),),
        tools=(),
        failure_result="burnt_food", xp_reward=7,
    ),
    CraftingRecipe(
        id="mushroom_soup", name="Mushroom Soup", workstation="kitchen",
        skill="cooking", skill_dc=10, ap_cost=5,
        ingredients=(_ing("mushroom", 2), _ing("water", 1), _ing("salt", 1)),
        products=(_prod("mushroom_soup", 2),),
        tools=(),
        failure_result="burnt_food", xp_reward=8,
    ),
    CraftingRecipe(
        id="honey_cake", name="Honey Cake", workstation="kitchen",
        skill="cooking", skill_dc=12, ap_cost=6,
        ingredients=(_ing("flour", 2), _ing("honey", 1), _ing("egg", 1)),
        products=(_prod("honey_cake", 2),),
        tools=(),
        failure_result="burnt_food", xp_reward=10,
    ),
    CraftingRecipe(
        id="herbal_tea", name="Herbal Tea", workstation="campfire",
        skill="cooking", skill_dc=6, ap_cost=2,
        ingredients=(_ing("herb_heal", 1), _ing("water", 1)),
        products=(_prod("herbal_tea", 2),),
        tools=(),
        failure_result=None, xp_reward=4,
    ),
    CraftingRecipe(
        id="roast_boar", name="Roast Boar", workstation="campfire",
        skill="cooking", skill_dc=14, ap_cost=10,
        ingredients=(_ing("boar_meat", 1), _ing("salt", 1), _ing("herb_heal", 1)),
        products=(_prod("roast_boar", 3),),
        tools=(),
        failure_result="burnt_food", xp_reward=15,
    ),
]

# ---------- CARPENTRY (workbench) ----------

_CARPENTRY_RECIPES: List[CraftingRecipe] = [
    CraftingRecipe(
        id="wooden_shield", name="Wooden Shield", workstation="workbench",
        skill="carpentry", skill_dc=10, ap_cost=8,
        ingredients=(_ing("wood_plank", 3), _ing("iron_nail", 5)),
        products=(_prod("wooden_shield"),),
        tools=("saw",),
        failure_result="scrap_wood", xp_reward=12,
    ),
    CraftingRecipe(
        id="bow", name="Bow", workstation="workbench",
        skill="carpentry", skill_dc=12, ap_cost=8,
        ingredients=(_ing("wood_plank", 1), _ing("sinew", 1)),
        products=(_prod("bow"),),
        tools=(),
        failure_result="scrap_wood", xp_reward=14,
    ),
    CraftingRecipe(
        id="arrows", name="Arrows", workstation="workbench",
        skill="carpentry", skill_dc=8, ap_cost=2,
        ingredients=(_ing("wood_stick", 1), _ing("iron_arrowhead", 1), _ing("feather", 1)),
        products=(_prod("arrow", 5),),
        tools=(),
        failure_result=None, xp_reward=4,
    ),
    CraftingRecipe(
        id="lockpick", name="Lockpick", workstation="workbench",
        skill="carpentry", skill_dc=14, ap_cost=3,
        ingredients=(_ing("iron_bar", 1),),
        products=(_prod("lockpick"),),
        tools=(),
        failure_result=None, xp_reward=10,
    ),
    CraftingRecipe(
        id="torch", name="Torch", workstation="workbench",
        skill="carpentry", skill_dc=6, ap_cost=2,
        ingredients=(_ing("wood_stick", 1), _ing("cloth", 1), _ing("oil", 1)),
        products=(_prod("torch", 3),),
        tools=(),
        failure_result=None, xp_reward=3,
    ),
    CraftingRecipe(
        id="wooden_chest", name="Wooden Chest", workstation="workbench",
        skill="carpentry", skill_dc=12, ap_cost=10,
        ingredients=(_ing("wood_plank", 4), _ing("iron_nail", 10)),
        products=(_prod("wooden_chest"),),
        tools=("saw",),
        failure_result="scrap_wood", xp_reward=15,
    ),
    CraftingRecipe(
        id="bed", name="Bed", workstation="workbench",
        skill="carpentry", skill_dc=10, ap_cost=8,
        ingredients=(_ing("wood_plank", 3), _ing("cloth", 2)),
        products=(_prod("bed"),),
        tools=("saw",),
        failure_result="scrap_wood", xp_reward=12,
    ),
    CraftingRecipe(
        id="table", name="Table", workstation="workbench",
        skill="carpentry", skill_dc=10, ap_cost=6,
        ingredients=(_ing("wood_plank", 3), _ing("iron_nail", 4)),
        products=(_prod("table"),),
        tools=("saw",),
        failure_result="scrap_wood", xp_reward=10,
    ),
    CraftingRecipe(
        id="chair", name="Chair", workstation="workbench",
        skill="carpentry", skill_dc=8, ap_cost=4,
        ingredients=(_ing("wood_plank", 2), _ing("iron_nail", 4)),
        products=(_prod("chair"),),
        tools=("saw",),
        failure_result="scrap_wood", xp_reward=6,
    ),
    CraftingRecipe(
        id="door", name="Door", workstation="workbench",
        skill="carpentry", skill_dc=10, ap_cost=6,
        ingredients=(_ing("wood_plank", 3), _ing("iron_nail", 6)),
        products=(_prod("door"),),
        tools=("saw",),
        failure_result="scrap_wood", xp_reward=10,
    ),
    CraftingRecipe(
        id="ladder", name="Ladder", workstation="workbench",
        skill="carpentry", skill_dc=8, ap_cost=4,
        ingredients=(_ing("wood_plank", 2), _ing("iron_nail", 4)),
        products=(_prod("ladder"),),
        tools=(),
        failure_result=None, xp_reward=6,
    ),
    CraftingRecipe(
        id="wooden_fence", name="Wooden Fence", workstation="workbench",
        skill="carpentry", skill_dc=6, ap_cost=3,
        ingredients=(_ing("wood_plank", 2), _ing("iron_nail", 3)),
        products=(_prod("wooden_fence", 2),),
        tools=(),
        failure_result=None, xp_reward=4,
    ),
]

# ---------- LEATHERWORKING (workbench) ----------

_LEATHERWORKING_RECIPES: List[CraftingRecipe] = [
    CraftingRecipe(
        id="leather", name="Leather", workstation="workbench",
        skill="leatherworking", skill_dc=10, ap_cost=8,
        ingredients=(_ing("hide", 1), _ing("tanning_agent", 1)),
        products=(_prod("leather"),),
        tools=(),
        failure_result="ruined_hide", xp_reward=8,
    ),
    CraftingRecipe(
        id="leather_armor", name="Leather Armor", workstation="workbench",
        skill="leatherworking", skill_dc=13, ap_cost=15,
        ingredients=(_ing("leather", 4), _ing("sinew", 2)),
        products=(_prod("leather_armor"),),
        tools=("needle",),
        failure_result="scrap_leather", xp_reward=25,
    ),
    CraftingRecipe(
        id="backpack", name="Backpack", workstation="workbench",
        skill="leatherworking", skill_dc=11, ap_cost=8,
        ingredients=(_ing("leather", 2), _ing("sinew", 1)),
        products=(_prod("backpack"),),
        tools=("needle",),
        failure_result=None, xp_reward=12,
    ),
    CraftingRecipe(
        id="waterskin", name="Waterskin", workstation="workbench",
        skill="leatherworking", skill_dc=8, ap_cost=3,
        ingredients=(_ing("leather", 1),),
        products=(_prod("waterskin"),),
        tools=("needle",),
        failure_result=None, xp_reward=5,
    ),
    CraftingRecipe(
        id="quiver", name="Quiver", workstation="workbench",
        skill="leatherworking", skill_dc=8, ap_cost=3,
        ingredients=(_ing("leather", 1),),
        products=(_prod("quiver"),),
        tools=("needle",),
        failure_result=None, xp_reward=5,
    ),
    CraftingRecipe(
        id="boots", name="Boots", workstation="workbench",
        skill="leatherworking", skill_dc=11, ap_cost=8,
        ingredients=(_ing("leather", 2), _ing("sinew", 1)),
        products=(_prod("boots"),),
        tools=("needle",),
        failure_result=None, xp_reward=10,
    ),
    CraftingRecipe(
        id="gloves", name="Gloves", workstation="workbench",
        skill="leatherworking", skill_dc=10, ap_cost=5,
        ingredients=(_ing("leather", 1), _ing("sinew", 1)),
        products=(_prod("gloves"),),
        tools=("needle",),
        failure_result=None, xp_reward=8,
    ),
    CraftingRecipe(
        id="belt", name="Belt", workstation="workbench",
        skill="leatherworking", skill_dc=8, ap_cost=3,
        ingredients=(_ing("leather", 1),),
        products=(_prod("belt"),),
        tools=(),
        failure_result=None, xp_reward=4,
    ),
    CraftingRecipe(
        id="satchel", name="Satchel", workstation="workbench",
        skill="leatherworking", skill_dc=10, ap_cost=5,
        ingredients=(_ing("leather", 1), _ing("sinew", 1)),
        products=(_prod("satchel"),),
        tools=("needle",),
        failure_result=None, xp_reward=8,
    ),
]

# ── Master registry ──────────────────────────────────────────────────────

ALL_RECIPES: Dict[str, CraftingRecipe] = {}
for _recipe_list in (
    _SMITHING_RECIPES,
    _ALCHEMY_RECIPES,
    _COOKING_RECIPES,
    _CARPENTRY_RECIPES,
    _LEATHERWORKING_RECIPES,
):
    for _r in _recipe_list:
        ALL_RECIPES[_r.id] = _r

DISCIPLINE_MAP: Dict[str, str] = {r.id: r.skill for r in ALL_RECIPES.values()}


def recipes_by_discipline(discipline: str) -> List[CraftingRecipe]:
    """Return all recipes belonging to a crafting discipline."""
    return [r for r in ALL_RECIPES.values() if r.skill == discipline]


# ── Crafting system ──────────────────────────────────────────────────────

class CraftingSystem:
    """Stateless crafting engine.

    Operates on plain dicts for inventory and simple protocol objects for
    spatial lookup, so it stays decoupled from the entity system.
    """

    # -- Ingredient helpers ------------------------------------------------

    @staticmethod
    def check_ingredients(
        recipe: CraftingRecipe,
        inventory: Dict[str, int],
    ) -> bool:
        """Return True when *inventory* contains all ingredients for *recipe*."""
        for ing in recipe.ingredients:
            if inventory.get(ing.item_id, 0) < ing.quantity:
                return False
        return True

    @staticmethod
    def consume_ingredients(
        recipe: CraftingRecipe,
        inventory: Dict[str, int],
    ) -> None:
        """Remove ingredient quantities from *inventory* **in place**.

        Raises ``ValueError`` if any ingredient is insufficient (caller
        should have checked with :meth:`check_ingredients` first).
        """
        for ing in recipe.ingredients:
            avail = inventory.get(ing.item_id, 0)
            if avail < ing.quantity:
                raise ValueError(
                    f"Not enough {ing.item_id}: need {ing.quantity}, have {avail}"
                )
            inventory[ing.item_id] = avail - ing.quantity

    # -- Workstation lookup ------------------------------------------------

    @staticmethod
    def find_nearby_workstation(
        spatial_index: Any,
        player_pos: Tuple[int, int],
        workstation_type: str,
    ) -> Any:
        """Search *spatial_index* for a workstation within 2 tiles.

        ``spatial_index`` must support ``.in_radius(x, y, radius)``
        returning an iterable of objects with ``.entity_type`` and ``.name``
        (or ``.id``) attributes.

        Returns the first matching entity or ``None``.
        """
        if workstation_type == "any":
            return True  # sentinel: no workstation needed
        px, py = player_pos
        for entity in spatial_index.in_radius(px, py, 2):
            etype = getattr(entity, "entity_type", None)
            ename = getattr(entity, "name", getattr(entity, "id", ""))
            etype_value = getattr(etype, "value", str(etype)).lower()
            if etype_value in ("building", "furniture", "workstation"):
                if workstation_type.lower() in ename.lower():
                    return entity
        return None

    # -- Main craft attempt -----------------------------------------------

    def attempt_craft(
        self,
        roll: int,
        recipe: CraftingRecipe,
        inventory: Dict[str, int],
        *,
        workstation_ok: bool = True,
    ) -> CraftResult:
        """Execute a full crafting attempt.

        Parameters
        ----------
        roll:
            The total d20 + skill modifier result.
        recipe:
            Which recipe to craft.
        inventory:
            Player inventory as ``{item_id: qty}`` dict. Modified in place
            on success or ruined result.
        workstation_ok:
            Whether the player is near the correct workstation. Caller is
            responsible for checking via :meth:`find_nearby_workstation`.

        Returns
        -------
        CraftResult
        """
        # Pre-flight: workstation
        if not workstation_ok:
            return CraftResult(
                success=False,
                quality=QualityTier.RUINED,
                products=[],
                xp_gained=0,
                narrative=f"You need a {recipe.workstation} to craft {recipe.name}.",
            )

        # Pre-flight: ingredients
        if not self.check_ingredients(recipe, inventory):
            return CraftResult(
                success=False,
                quality=QualityTier.RUINED,
                products=[],
                xp_gained=0,
                narrative=f"You lack the materials to craft {recipe.name}.",
            )

        # Consume ingredients (always consumed once we start)
        self.consume_ingredients(recipe, inventory)

        # Determine quality
        quality = determine_quality(roll, recipe.skill_dc)

        # Ruined → ingredients lost, optional failure product
        if quality == QualityTier.RUINED:
            products: List[Tuple[str, int]] = []
            if recipe.failure_result:
                products.append((recipe.failure_result, 1))
                inventory[recipe.failure_result] = (
                    inventory.get(recipe.failure_result, 0) + 1
                )
            return CraftResult(
                success=False,
                quality=quality,
                products=products,
                xp_gained=recipe.xp_reward // 4,  # partial XP for attempt
                narrative=(
                    f"Your attempt to craft {recipe.name} fails catastrophically! "
                    f"The materials are ruined."
                ),
            )

        # Success (shoddy through masterwork)
        produced: List[Tuple[str, int]] = []
        for prod in recipe.products:
            produced.append((prod.item_id, prod.quantity))
            inventory[prod.item_id] = (
                inventory.get(prod.item_id, 0) + prod.quantity
            )

        quality_label = quality.value.capitalize()
        xp = recipe.xp_reward
        if quality in (QualityTier.FINE, QualityTier.SUPERIOR):
            xp = int(xp * 1.5)
        elif quality == QualityTier.MASTERWORK:
            xp = xp * 2

        return CraftResult(
            success=True,
            quality=quality,
            products=produced,
            xp_gained=xp,
            narrative=(
                f"You craft a {quality_label} {recipe.name}! "
                f"(+{xp} XP)"
            ),
        )

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

from engine.data_loader import list_recipes


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


# ── JSON-backed registry builders ────────────────────────────────────────

def _ingredient_from_dict(data: Dict[str, Any]) -> Ingredient:
    return Ingredient(
        item_id=str(data.get("item_id", "")),
        quantity=int(data.get("quantity", 1)),
        material_class=data.get("material_class"),
    )


def _product_from_dict(data: Dict[str, Any]) -> Product:
    return Product(
        item_id=str(data.get("item_id", "")),
        quantity=int(data.get("quantity", 1)),
        inherit_material=bool(data.get("inherit_material", False)),
    )


def _recipe_from_dict(data: Dict[str, Any]) -> CraftingRecipe:
    return CraftingRecipe(
        id=str(data["id"]),
        name=str(data["name"]),
        workstation=str(data.get("workstation", "any")),
        skill=str(data.get("skill", "")),
        skill_dc=int(data.get("skill_dc", 10)),
        ap_cost=int(data.get("ap_cost", 1)),
        ingredients=tuple(_ingredient_from_dict(entry) for entry in data.get("ingredients", [])),
        products=tuple(_product_from_dict(entry) for entry in data.get("products", [])),
        tools=tuple(str(tool) for tool in data.get("tools", [])),
        failure_result=data.get("failure_result"),
        xp_reward=int(data.get("xp_reward", 10)),
    )


def _load_recipe_registry() -> Dict[str, CraftingRecipe]:
    recipes: Dict[str, CraftingRecipe] = {}
    for recipe_data in list_recipes():
        recipe = _recipe_from_dict(recipe_data)
        recipes[recipe.id] = recipe
    return recipes


ALL_RECIPES: Dict[str, CraftingRecipe] = _load_recipe_registry()

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

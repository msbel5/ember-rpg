"""Crafting handler methods."""
from __future__ import annotations

from typing import Optional

from engine.api.action_parser import ParsedAction
from engine.api.game_session import GameSession
from engine.world.crafting import ALL_RECIPES, CraftingRecipe, CraftingSystem


class InventoryCraftingMixin:
    """Focused handlers for recipe listing and crafting attempts."""

    def _handle_craft(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = (action.target or "").lower().strip()
        if not target:
            inv_dict = {}
            for item in session.inventory:
                item_id = item.get("id", "")
                inv_dict[item_id] = inv_dict.get(item_id, 0) + item.get("qty", 1)
            crafting = CraftingSystem()
            can_craft = []
            other_recipes = []
            for recipe in ALL_RECIPES.values():
                if crafting.check_ingredients(recipe, dict(inv_dict)):
                    can_craft.append(f"  [*] {recipe.name} ({recipe.skill} DC {recipe.skill_dc}, {recipe.ap_cost} AP)")
                else:
                    other_recipes.append(recipe.name)
            parts = ["== Crafting Recipes =="]
            if can_craft:
                parts.append("You can craft:")
                parts.extend(can_craft)
            else:
                parts.append("You don't have ingredients for any recipe right now.")
            if other_recipes:
                parts.append(f"\nOther recipes: {', '.join(other_recipes[:15])}...")
            return ActionResult(narrative="\n".join(parts), scene_type=session.dm_context.scene_type)

        recipe: Optional[CraftingRecipe] = None
        for candidate in ALL_RECIPES.values():
            if target in candidate.name.lower() or target in candidate.id.lower():
                recipe = candidate
                break
        if recipe is None:
            return ActionResult(
                narrative=f"No recipe found for '{target}'. Try 'craft' to see available recipes.",
                scene_type=session.dm_context.scene_type,
            )

        crafting = CraftingSystem()
        workstation_ok = True
        if recipe.workstation != "any" and session.spatial_index:
            workstation = crafting.find_nearby_workstation(
                session.spatial_index,
                (session.position[0], session.position[1]),
                recipe.workstation,
            )
            workstation_ok = workstation is not None

        inv_dict: dict[str, int] = {}
        for item in session.inventory:
            item_id = item.get("id", item.get("name", "unknown")).lower().replace(" ", "_")
            inv_dict[item_id] = inv_dict.get(item_id, 0) + item.get("qty", 1)
        inventory_before = dict(inv_dict)

        if not workstation_ok:
            return ActionResult(
                narrative=f"You need a {recipe.workstation} to craft {recipe.name}.",
                scene_type=session.dm_context.scene_type,
            )
        if not crafting.check_ingredients(recipe, inv_dict):
            return ActionResult(
                narrative=f"You lack the materials to craft {recipe.name}.",
                scene_type=session.dm_context.scene_type,
            )

        world_minutes = 15
        ap_after_world_tick = None
        if session.ap_tracker:
            world_minutes, ap_after_world_tick = self._simulate_long_action_ap(session, recipe.ap_cost)

        skill_ability_map = {
            "smithing": "MIG",
            "alchemy": "MND",
            "cooking": "INS",
            "carpentry": "AGI",
            "leatherworking": "AGI",
        }
        ability = skill_ability_map.get(recipe.skill, "MND")
        check_result = self._roll_ability_check(session, ability, recipe.skill_dc)
        check_text = self._format_skill_check(check_result, ability, recipe.skill_dc)
        craft_result = crafting.attempt_craft(
            roll=check_result.total,
            recipe=recipe,
            inventory=inv_dict,
            workstation_ok=workstation_ok,
        )

        crafted_material = None
        for ingredient in recipe.ingredients:
            ingredient_item = session.find_inventory_item(ingredient.item_id)
            if ingredient_item and ingredient_item.get("material"):
                crafted_material = ingredient_item.get("material")
                break
            if any(token in ingredient.item_id for token in ("iron", "steel", "leather", "cloth", "wood")):
                crafted_material = ingredient.item_id.split("_")[0]
                break

        dropped_products: list[str] = []
        if craft_result.success or craft_result.quality.value == "ruined":
            for item_id, before_qty in inventory_before.items():
                delta = before_qty - inv_dict.get(item_id, 0)
                if delta > 0:
                    session.remove_item(item_id, delta)
            for product_id, qty in craft_result.products:
                product_record = {
                    "id": product_id,
                    "name": product_id.replace("_", " ").title(),
                    "qty": qty,
                    "quality": craft_result.quality.value,
                }
                if crafted_material:
                    product_record["material"] = crafted_material
                if not self._add_or_drop_item(session, product_record):
                    dropped_products.append(product_record["name"])
                if getattr(session, "location_stock", None) is not None:
                    session.location_stock.add_stock(product_id, qty)
        narrative_parts = [check_text, craft_result.narrative]
        if dropped_products:
            narrative_parts.append(
                f"No room to carry {', '.join(dropped_products)}. The item lands on the ground instead."
            )
        if craft_result.xp_gained > 0:
            self.progression.add_xp(session.player, craft_result.xp_gained)

        return ActionResult(
            narrative="\n".join(narrative_parts),
            scene_type=session.dm_context.scene_type,
            state_changes={
                "xp_gained": craft_result.xp_gained,
                "crafted": craft_result.products,
                "_world_minutes": world_minutes,
                "_ap_after_world_tick": ap_after_world_tick,
            },
        )

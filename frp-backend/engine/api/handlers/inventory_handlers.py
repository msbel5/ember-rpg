"""Inventory handler methods for GameEngine — mixin class."""
from __future__ import annotations

import copy
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from engine.api.game_session import GameSession
from engine.api.action_parser import ParsedAction
from engine.core.dm_agent import DMEvent, EventType, SceneType
from engine.world.entity import Entity, EntityType
from engine.world.action_points import ACTION_COSTS
from engine.world.crafting import CraftingSystem, ALL_RECIPES, CraftingRecipe, determine_quality

if TYPE_CHECKING:
    from engine.api.game_engine import ActionResult


class InventoryMixin:
    """Inventory/equipment handler methods."""

    def _handle_inventory(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Show the player's inventory with containers, weight, and equipment."""
        from engine.api.game_engine import ActionResult
        lines = []
        pi = session.physical_inventory

        # Equipment
        equipped_items = {slot: item for slot, item in session.equipment.items() if item is not None}
        if equipped_items:
            lines.append("== Equipped ==")
            for slot, item in equipped_items.items():
                extra = ""
                if item.get("damage"):
                    extra += f" (dmg: {item['damage']})"
                if item.get("ac_bonus"):
                    extra += f" (AC+{item['ac_bonus']})"
                lines.append(f"  [{slot}] {item['name']}{extra}")

        # Containers
        if pi:
            for container in pi.all_containers():
                items = container.all_items()
                if items:
                    lines.append(f"== {container.container_id.replace('_', ' ').title()} ({container.used_slots()}/{container.slot_count()} slots, {container.total_weight():.1f}/{container.max_weight:.1f} kg) ==")
                    for i, stack in enumerate(items):
                        qty_str = f" x{stack.quantity}" if stack.quantity > 1 else ""
                        lines.append(f"  {i+1}. {stack.name}{qty_str} ({stack.weight:.1f} kg)")
            # Hidden stashes (only show non-empty ones)
            for stash_name, stash in pi.hidden_stashes.items():
                items = stash.all_items()
                if items:
                    lines.append(f"== {stash_name.replace('_', ' ').title()} (hidden) ==")
                    for stack in items:
                        lines.append(f"  - {stack.name}")

        if not equipped_items and not session.inventory:
            lines.append("Your inventory is empty.")

        # Weight
        if pi:
            str_mod = session._get_strength_modifier()
            total = pi.total_carried_weight()
            max_w = pi.max_carry_weight(str_mod)
            enc = pi.encumbrance_ap_penalty(str_mod)
            enc_str = f" [ENCUMBERED +{enc} AP/move]" if enc > 0 and enc < 999 else (" [CANNOT MOVE]" if enc >= 999 else "")
            lines.append(f"\nWeight: {total:.1f}/{max_w:.1f} kg{enc_str}")

        # AP status
        if session.ap_tracker:
            lines.append(f"AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap}")

        return ActionResult(
            narrative="\n".join(lines),
            scene_type=session.dm_context.scene_type,
        )

    def _handle_pickup(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Pick up an item entity at the player's position."""
        from engine.api.game_engine import ActionResult
        target = action.target or ""
        px, py = session.position[0], session.position[1]

        match = None
        if session.spatial_index:
            entities_here = session.spatial_index.at(px, py)
            items_here = [e for e in entities_here if e.entity_type == EntityType.ITEM]
            if target:
                target_lower = target.lower()
                match = next((e for e in items_here if target_lower in e.name.lower()), None)
            else:
                match = items_here[0] if items_here else None

        if not match:
            return ActionResult(
                narrative=f"There's nothing to pick up here{' matching that name' if target else ''}.",
                scene_type=session.dm_context.scene_type,
            )

        item_dict = {"id": match.id, "name": match.name, "type": "item", "entity_id": match.id}
        if match.inventory:
            item_dict.update(copy.deepcopy(match.inventory[0]))
        item_dict["ground_instance_id"] = match.id

        status = session.assess_item_addition(item_dict, merge=True)
        if not status["allowed"]:
            if status["reason"] == "overweight":
                session._record_add_item_failure(status)
            return ActionResult(
                narrative=self._inventory_add_failure_message(session, match.name),
                scene_type=session.dm_context.scene_type,
            )

        if session.ap_tracker:
            cost = ACTION_COSTS.get("pick_up", 1)
            if not session.ap_tracker.spend(cost):
                return ActionResult(
                    narrative=f"Not enough AP to pick up items. (AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap})",
                    scene_type=session.dm_context.scene_type,
                )

        if session.spatial_index:
            session.spatial_index.remove(match)
        added = session.add_item(item_dict, merge=True)
        if added is None:
            if session.spatial_index:
                session.spatial_index.add(match)
            return ActionResult(
                narrative=self._inventory_add_failure_message(session, match.name),
                scene_type=session.dm_context.scene_type,
            )
        if session.ap_tracker and session.ap_tracker.current_ap <= 0 and not session.in_combat():
            session.narration_context["_auto_refresh_after_action"] = True
        return ActionResult(
            narrative=f"You pick up {match.name}.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_drop(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Drop an item from inventory onto the ground."""
        from engine.api.game_engine import ActionResult
        target = (action.target or "").lower()
        if not target:
            return ActionResult(
                narrative="Drop what? Specify an item name.",
                scene_type=session.dm_context.scene_type,
            )

        # Validate item exists before spending AP
        candidate = session.find_inventory_item(target)
        if candidate is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )

        # Spend AP
        ap_fail = self._check_ap(session, "pick_up")  # drop costs same as pick_up (1 AP)
        if ap_fail:
            return ap_fail

        # Remove item from inventory
        item = session.remove_item(target)
        if item is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )
        px, py = session.position[0], session.position[1]

        # Create an item Entity at the player's position
        item_entity = Entity(
            id=item.get("ground_instance_id") or item.get("instance_id") or Entity.generate_id(),
            entity_type=EntityType.ITEM,
            name=item.get("name", "Unknown Item"),
            position=(px, py),
            glyph="!",
            color="yellow",
            blocking=False,
            inventory=[copy.deepcopy(item)],
        )
        if session.spatial_index:
            session.spatial_index.add(item_entity)

        return ActionResult(
            narrative=f"You drop {item['name']} on the ground.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_equip(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Equip an item from inventory, or unequip if target starts with 'un'."""
        from engine.api.game_engine import ActionResult
        raw = (action.raw_input or "").lower()
        target = (action.target or "").lower()

        # Check for unequip intent
        is_unequip = any(w in raw for w in ["unequip", "remove", "take off", "doff"])

        if is_unequip:
            return self._handle_unequip_item(session, target)

        if not target:
            return ActionResult(
                narrative="Equip what? Specify an item name.",
                scene_type=session.dm_context.scene_type,
            )

        # Check if already equipped
        for slot, eq_item in session.equipment.items():
            if eq_item and (target in eq_item.get("name", "").lower() or target in eq_item.get("id", "").lower()):
                return ActionResult(
                    narrative=f"{eq_item['name']} is already equipped in your {slot} slot.",
                    scene_type=session.dm_context.scene_type,
                )

        # Find item in inventory
        candidate = session.find_inventory_item(target)
        if candidate is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )
        old_item = session.equipment.get(session._infer_slot(candidate))
        item = session.equip_item(target)
        if item is None:
            return ActionResult(
                narrative=f"{target} cannot be equipped.",
                scene_type=session.dm_context.scene_type,
            )

        narrative = f"You equip {item['name']}."
        if old_item:
            narrative += f" (Unequipped {old_item['name']})"
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_unequip(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Unequip handler (delegates to _handle_unequip_item)."""
        target = (action.target or "").lower()
        return self._handle_unequip_item(session, target)

    def _handle_unequip_item(self, session: GameSession, target: str) -> "ActionResult":
        """Unequip an item from an equipment slot back to inventory."""
        from engine.api.game_engine import ActionResult
        if not target:
            return ActionResult(
                narrative="Unequip what? Specify an item or slot name.",
                scene_type=session.dm_context.scene_type,
            )

        # Try to match by slot name or item name
        matched_slot = None
        for slot, item in session.equipment.items():
            if item is None:
                continue
            if target in slot or target in item.get("name", "").lower() or target in item.get("id", "").lower():
                matched_slot = slot
                break

        if matched_slot is None:
            return ActionResult(
                narrative=f"Nothing equipped matching '{target}'.",
                scene_type=session.dm_context.scene_type,
            )

        item = session.unequip_item(target)
        if item is None:
            return ActionResult(
                narrative=f"Nothing equipped matching '{target}'.",
                scene_type=session.dm_context.scene_type,
            )

        return ActionResult(
            narrative=f"You unequip {item['name']}.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_use_item(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        target = (action.target or "").lower()
        if not target:
            return ActionResult(
                narrative="Use what? Specify an item name.",
                scene_type=session.dm_context.scene_type,
            )

        item = session.find_inventory_item(target)
        if not item:
            return ActionResult(
                narrative=f"You don't have '{action.target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )
        ap_fail = self._check_ap(session, "use")
        if ap_fail:
            return ap_fail

        item_type = item.get("type", "")
        item_name = item.get("name", target)

        # Consumable: heal, restore SP, apply effects
        if item_type == "consumable" or item.get("heal") or item.get("hp_restore"):
            heal_amount = item.get("heal", 0) or item.get("hp_restore", 0)
            sp_restore = item.get("sp_restore", 0)
            effects = []

            if heal_amount > 0:
                old_hp = session.player.hp
                if old_hp >= session.player.max_hp:
                    return ActionResult(
                        narrative=f"You're already at full health ({session.player.hp}/{session.player.max_hp}). No need to use {item_name}.",
                        scene_type=session.dm_context.scene_type,
                    )
                session.player.hp = min(session.player.max_hp, session.player.hp + heal_amount)
                actual_heal = session.player.hp - old_hp
                effects.append(f"restored {actual_heal} HP")

            if sp_restore > 0:
                old_sp = session.player.spell_points
                session.player.spell_points = min(
                    getattr(session.player, "max_spell_points", session.player.spell_points + sp_restore),
                    session.player.spell_points + sp_restore,
                )
                actual_sp = session.player.spell_points - old_sp
                effects.append(f"restored {actual_sp} SP")

            # Consume the item
            session.remove_item(item.get("id", target), 1)

            effect_str = " and ".join(effects) if effects else "had a mysterious effect"
            return ActionResult(
                narrative=f"You use {item_name} — {effect_str}. (HP: {session.player.hp}/{session.player.max_hp})",
                scene_type=session.dm_context.scene_type,
            )

        # Tool with uses
        if item.get("uses") is not None:
            uses = item.get("uses", 0)
            if uses <= 0:
                return ActionResult(
                    narrative=f"Your {item_name} is spent — no uses remaining.",
                    scene_type=session.dm_context.scene_type,
                )
            item["uses"] = uses - 1
            remaining = item["uses"]
            narrative = f"You use {item_name}. ({remaining} uses remaining)"
            if remaining <= 0:
                session.remove_item(item.get("id", target), 1)
                narrative += f" The {item_name} is now spent."
            return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

        # Generic fallback for untyped items -> DM narration
        desc = f"{session.player.name} uses {item_name}."
        event = DMEvent(type=EventType.DISCOVERY, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_fill(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Fill a liquid container (waterskin, bottle) at a water source."""
        from engine.api.game_engine import ActionResult
        target = (action.target or "").lower()
        if not target:
            return ActionResult(
                narrative="Fill what? Specify a container name (e.g., 'fill waterskin').",
                scene_type=session.dm_context.scene_type,
            )
        # Check if near water source
        has_water = False
        if session.map_data:
            px, py = session.position
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    from engine.map import TileType
                    if session.map_data.get_tile(px + dx, py + dy) == TileType.WATER:
                        has_water = True
                        break
        # Also check for well/fountain entities
        if not has_water and session.spatial_index:
            nearby = session.spatial_index.in_radius(session.position[0], session.position[1], 2)
            for e in nearby:
                if any(w in e.name.lower() for w in ["well", "fountain", "spring"]):
                    has_water = True
                    break
        if not has_water:
            return ActionResult(
                narrative="There's no water source nearby. Move closer to water, a well, or a fountain.",
                scene_type=session.dm_context.scene_type,
            )
        ap_fail = self._check_ap(session, "fill")
        if ap_fail:
            return ap_fail
        if session.physical_inventory:
            success, msg = session.physical_inventory.fill_liquid_container(target, "water", 500)
            if success:
                return ActionResult(narrative=msg, scene_type=session.dm_context.scene_type)
            return ActionResult(narrative=msg, scene_type=session.dm_context.scene_type)
        return ActionResult(
            narrative="You don't have a container to fill.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_pour(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Pour liquid out of a container, or transfer between containers."""
        from engine.api.game_engine import ActionResult
        target = (action.target or "").lower()
        destination = (action.direction or action.action_detail or "").lower().strip()
        if not target:
            return ActionResult(
                narrative="Pour what? Specify a container (e.g., 'pour waterskin' or 'pour water into bottle').",
                scene_type=session.dm_context.scene_type,
            )
        if not session.physical_inventory:
            return ActionResult(
                narrative=f"You don't have '{target}' or it doesn't contain any liquid.",
                scene_type=session.dm_context.scene_type,
            )

        # Try to find source container by name
        source = session.physical_inventory.find_item(target)
        if source and source.contained_matter:
            ap_fail = self._check_ap(session, "pour")
            if ap_fail:
                return ap_fail
            liquid_id = source.contained_matter.get("item_id", "liquid")
            amount = source.contained_matter.get("amount_ml", 0)

            # If destination specified, transfer to another container
            if destination:
                dest_stack = session.physical_inventory.find_item(destination)
                if dest_stack is None:
                    return ActionResult(
                        narrative=f"You don't have a '{destination}' to pour into.",
                        scene_type=session.dm_context.scene_type,
                    )
                if dest_stack.contained_matter is not None:
                    return ActionResult(
                        narrative=f"The {dest_stack.name} already contains something.",
                        scene_type=session.dm_context.scene_type,
                    )
                # Check if dest can hold liquid
                from engine.world.matter_state import MatterState
                if hasattr(dest_stack, 'allowed_matter') and dest_stack.allowed_matter:
                    if MatterState.LIQUID not in dest_stack.allowed_matter:
                        return ActionResult(
                            narrative=f"The {dest_stack.name} can't hold liquids.",
                            scene_type=session.dm_context.scene_type,
                        )
                dest_stack.contained_matter = dict(source.contained_matter)
                source.contained_matter = None
                return ActionResult(
                    narrative=f"You pour {amount}ml of {liquid_id} from the {source.name} into the {dest_stack.name}.",
                    scene_type=session.dm_context.scene_type,
                )
            else:
                # Dump on ground
                source.contained_matter = None
                return ActionResult(
                    narrative=f"You pour out {amount}ml of {liquid_id} from the {source.name}.",
                    scene_type=session.dm_context.scene_type,
                )

        # Maybe target is the liquid name, not the container
        # Search all containers for liquid matching target
        for container in session.physical_inventory.all_containers():
            for stack in container.all_items():
                if stack.contained_matter and target in stack.contained_matter.get("item_id", "").lower():
                    ap_fail = self._check_ap(session, "pour")
                    if ap_fail:
                        return ap_fail
                    liquid_id = stack.contained_matter.get("item_id", "liquid")
                    amount = stack.contained_matter.get("amount_ml", 0)
                    if destination:
                        dest_stack = session.physical_inventory.find_item(destination)
                        if dest_stack and dest_stack.contained_matter is None:
                            dest_stack.contained_matter = dict(stack.contained_matter)
                            stack.contained_matter = None
                            return ActionResult(
                                narrative=f"You pour {amount}ml of {liquid_id} from the {stack.name} into the {dest_stack.name}.",
                                scene_type=session.dm_context.scene_type,
                            )
                    stack.contained_matter = None
                    return ActionResult(
                        narrative=f"You pour out {amount}ml of {liquid_id} from the {stack.name}.",
                        scene_type=session.dm_context.scene_type,
                    )

        return ActionResult(
            narrative=f"You don't have '{target}' or it doesn't contain any liquid.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_stash(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Hide an item in a hidden stash (sock, boot lining)."""
        from engine.api.game_engine import ActionResult
        target = (action.target or "").lower()
        location = (action.direction or action.action_detail or "").lower().strip()
        if not target:
            return ActionResult(
                narrative="Stash what? Specify an item (e.g., 'stash gem in sock').",
                scene_type=session.dm_context.scene_type,
            )
        if session.find_inventory_item(target) is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )
        ap_fail = self._check_ap(session, "stash")
        if ap_fail:
            return ap_fail
        # Remove from inventory
        removed = session.remove_item(target)
        if removed is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )
        from engine.world.inventory import ItemStack as _IS
        stack = _IS.from_legacy_dict(removed)
        # Pick stash location
        if not location:
            location = "sock_left"
        # Normalize location name
        location = location.replace(" ", "_")
        if session.physical_inventory:
            success, msg = session.physical_inventory.stash_in(location, stack)
            if success:
                return ActionResult(narrative=msg, scene_type=session.dm_context.scene_type)
            # Failed -- put item back
            session.add_item(removed)
            return ActionResult(narrative=msg, scene_type=session.dm_context.scene_type)
        session.add_item(removed)
        return ActionResult(
            narrative="No stash locations available.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_rotate_item(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Rotate an item in the grid (90 degrees)."""
        from engine.api.game_engine import ActionResult
        target = (action.target or "").lower()
        if not target:
            return ActionResult(
                narrative="Rotate what? Specify an item name.",
                scene_type=session.dm_context.scene_type,
            )
        if session.physical_inventory:
            stack = session.physical_inventory.find_item(target)
            if stack:
                stack.orientation = (stack.orientation + 90) % 360
                return ActionResult(
                    narrative=f"You rotate {stack.name} to {stack.orientation} degrees.",
                    scene_type=session.dm_context.scene_type,
                )
        return ActionResult(
            narrative=f"You don't have '{target}' in your inventory.",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_craft(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Handle crafting attempts using the CraftingSystem."""
        from engine.api.game_engine import ActionResult
        target = (action.target or "").lower().strip()
        if not target:
            # Show recipes grouped by what player can craft now vs what exists
            inv_dict = {}
            for item in session.inventory:
                iid = item.get("id", "")
                inv_dict[iid] = inv_dict.get(iid, 0) + item.get("qty", 1)
            crafting = CraftingSystem()
            can_craft = []
            other_recipes = []
            for r in ALL_RECIPES.values():
                if crafting.check_ingredients(r, dict(inv_dict)):
                    can_craft.append(f"  [*] {r.name} ({r.skill} DC {r.skill_dc}, {r.ap_cost} AP)")
                else:
                    other_recipes.append(r.name)
            parts = ["== Crafting Recipes =="]
            if can_craft:
                parts.append("You can craft:")
                parts.extend(can_craft)
            else:
                parts.append("You don't have ingredients for any recipe right now.")
            if other_recipes:
                parts.append(f"\nOther recipes: {', '.join(other_recipes[:15])}...")
            return ActionResult(
                narrative="\n".join(parts),
                scene_type=session.dm_context.scene_type,
            )

        # Find recipe by name match
        recipe: Optional[CraftingRecipe] = None
        for r in ALL_RECIPES.values():
            if target in r.name.lower() or target in r.id.lower():
                recipe = r
                break

        if recipe is None:
            return ActionResult(
                narrative=f"No recipe found for '{target}'. Try 'craft' to see available recipes.",
                scene_type=session.dm_context.scene_type,
            )

        # Check for nearby workstation
        crafting = CraftingSystem()
        workstation_ok = True
        if recipe.workstation != "any" and session.spatial_index:
            ws = crafting.find_nearby_workstation(
                session.spatial_index,
                (session.position[0], session.position[1]),
                recipe.workstation,
            )
            workstation_ok = ws is not None

        # Build inventory dict from session.inventory list
        inv_dict: dict = {}
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

        # Map crafting skill to ability
        skill_ability_map = {
            "smithing": "MIG", "alchemy": "MND", "cooking": "INS",
            "carpentry": "AGI", "leatherworking": "AGI",
        }
        ability = skill_ability_map.get(recipe.skill, "MND")
        ability_score = self._get_player_ability(session, ability)

        # Roll skill check
        check_result = self._roll_ability_check(session, ability, recipe.skill_dc)
        check_text = self._format_skill_check(check_result, ability, recipe.skill_dc)

        # Attempt craft
        craft_result = crafting.attempt_craft(
            roll=check_result.total,
            recipe=recipe,
            inventory=inv_dict,
            workstation_ok=workstation_ok,
        )

        # Detect material BEFORE consuming ingredients (so items still exist)
        crafted_material = None
        for ingredient in recipe.ingredients:
            ingredient_item = session.find_inventory_item(ingredient.item_id)
            if ingredient_item and ingredient_item.get("material"):
                crafted_material = ingredient_item.get("material")
                break
            if any(token in ingredient.item_id for token in ("iron", "steel", "leather", "cloth", "wood")):
                crafted_material = ingredient.item_id.split("_")[0]
                break

        dropped_products: List[str] = []
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

    # --- Inventory helpers ---

    def _spawn_ground_item(self, session: GameSession, item: Dict[str, Any]) -> Entity:
        payload = copy.deepcopy(item)
        px, py = session.position[0], session.position[1]
        item_entity = Entity(
            id=payload.get("ground_instance_id") or payload.get("instance_id") or Entity.generate_id(),
            entity_type=EntityType.ITEM,
            name=payload.get("name", "Unknown Item"),
            position=(px, py),
            glyph="!",
            color="yellow",
            blocking=False,
            inventory=[payload],
        )
        if session.spatial_index:
            session.spatial_index.add(item_entity)
        return item_entity

    def _add_or_drop_item(self, session: GameSession, item: Dict[str, Any], merge: bool = True) -> bool:
        added = session.add_item(item, merge=merge)
        if added is not None:
            return True
        self._spawn_ground_item(session, item)
        return False

    def _inventory_add_failure_message(self, session: GameSession, item_name: str) -> str:
        error = dict(session.narration_context.pop("_last_add_item_error", {}) or {})
        if error.get("reason") == "overweight":
            return (
                f"{item_name} is too heavy to carry right now. It would bring you to "
                f"{float(error.get('projected_weight', 0.0)):.1f}/{float(error.get('max_weight', 0.0)):.1f} kg. "
                "You wrench your back trying to lift it."
            )
        return f"No room for {item_name}. Your containers are full."

    def _count_inventory_item(self, session: GameSession, item_id: str) -> int:
        total = 0
        for item in session.inventory:
            if item.get("id") == item_id:
                total += int(item.get("qty", 1))
        return total

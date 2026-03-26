"""Inventory equipment, consumable, and liquid handlers."""
from __future__ import annotations

from engine.api.action_parser import ParsedAction
from engine.api.game_session import GameSession
from engine.core.dm_agent import DMEvent, EventType


class InventoryEquipmentMixin:
    """Focused handlers for equipping, using, and filling/pouring items."""

    def _handle_equip(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        raw = (action.raw_input or "").lower()
        target = (action.target or "").lower()
        if any(word in raw for word in ["unequip", "remove", "take off", "doff"]):
            return self._handle_unequip_item(session, target)
        if not target:
            return ActionResult(
                narrative="Equip what? Specify an item name.",
                scene_type=session.dm_context.scene_type,
            )

        for slot, equipped_item in session.equipment.items():
            if equipped_item and (target in equipped_item.get("name", "").lower() or target in equipped_item.get("id", "").lower()):
                return ActionResult(
                    narrative=f"{equipped_item['name']} is already equipped in your {slot} slot.",
                    scene_type=session.dm_context.scene_type,
                )

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

    def _handle_unequip(self, session: GameSession, action: ParsedAction):
        target = (action.target or "").lower()
        return self._handle_unequip_item(session, target)

    def _handle_unequip_item(self, session: GameSession, target: str):
        from engine.api.game_engine import ActionResult

        if not target:
            return ActionResult(
                narrative="Unequip what? Specify an item or slot name.",
                scene_type=session.dm_context.scene_type,
            )
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
        return ActionResult(narrative=f"You unequip {item['name']}.", scene_type=session.dm_context.scene_type)

    def _handle_use_item(self, session: GameSession, action: ParsedAction):
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

            session.remove_item(item.get("id", target), 1)
            effect_str = " and ".join(effects) if effects else "had a mysterious effect"
            return ActionResult(
                narrative=f"You use {item_name} — {effect_str}. (HP: {session.player.hp}/{session.player.max_hp})",
                scene_type=session.dm_context.scene_type,
            )

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

        event = DMEvent(type=EventType.DISCOVERY, description=f"{session.player.name} uses {item_name}.")
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_fill(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = (action.target or "").lower()
        if not target:
            return ActionResult(
                narrative="Fill what? Specify a container name (e.g., 'fill waterskin').",
                scene_type=session.dm_context.scene_type,
            )
        has_water = False
        if session.map_data:
            from engine.map import TileType

            px, py = session.position
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    if session.map_data.get_tile(px + dx, py + dy) == TileType.WATER:
                        has_water = True
                        break
        if not has_water and session.spatial_index:
            nearby = session.spatial_index.in_radius(session.position[0], session.position[1], 2)
            for entity in nearby:
                if any(word in entity.name.lower() for word in ["well", "fountain", "spring"]):
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
            success, message = session.physical_inventory.fill_liquid_container(target, "water", 500)
            return ActionResult(narrative=message, scene_type=session.dm_context.scene_type)
        return ActionResult(narrative="You don't have a container to fill.", scene_type=session.dm_context.scene_type)

    def _handle_pour(self, session: GameSession, action: ParsedAction):
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

        source = session.physical_inventory.find_item(target)
        if source and source.contained_matter:
            ap_fail = self._check_ap(session, "pour")
            if ap_fail:
                return ap_fail
            liquid_id = source.contained_matter.get("item_id", "liquid")
            amount = source.contained_matter.get("amount_ml", 0)
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
                from engine.world.matter_state import MatterState

                if hasattr(dest_stack, "allowed_matter") and dest_stack.allowed_matter and MatterState.LIQUID not in dest_stack.allowed_matter:
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
            source.contained_matter = None
            return ActionResult(
                narrative=f"You pour out {amount}ml of {liquid_id} from the {source.name}.",
                scene_type=session.dm_context.scene_type,
            )

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

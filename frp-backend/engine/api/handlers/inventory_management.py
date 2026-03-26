"""Inventory listing and transfer handlers."""
from __future__ import annotations

import copy
from typing import Any

from engine.api.action_parser import ParsedAction
from engine.api.game_session import GameSession
from engine.world.action_points import ACTION_COSTS
from engine.world.entity import Entity, EntityType


class InventoryManagementMixin:
    """Focused handlers for inventory listing, transfer, stash, and drop flows."""

    def _handle_inventory(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        lines = []
        pi = session.physical_inventory
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

        if pi:
            for container in pi.all_containers():
                items = container.all_items()
                if items:
                    lines.append(f"== {container.container_id.replace('_', ' ').title()} ({container.used_slots()}/{container.slot_count()} slots, {container.total_weight():.1f}/{container.max_weight:.1f} kg) ==")
                    for index, stack in enumerate(items):
                        qty_str = f" x{stack.quantity}" if stack.quantity > 1 else ""
                        lines.append(f"  {index + 1}. {stack.name}{qty_str} ({stack.weight:.1f} kg)")
            for stash_name, stash in pi.hidden_stashes.items():
                items = stash.all_items()
                if items:
                    lines.append(f"== {stash_name.replace('_', ' ').title()} (hidden) ==")
                    for stack in items:
                        lines.append(f"  - {stack.name}")

        if not equipped_items and not session.inventory:
            lines.append("Your inventory is empty.")

        if pi:
            str_mod = session._get_strength_modifier()
            total = pi.total_carried_weight()
            max_weight = pi.max_carry_weight(str_mod)
            enc = pi.encumbrance_ap_penalty(str_mod)
            enc_str = f" [ENCUMBERED +{enc} AP/move]" if enc > 0 and enc < 999 else (" [CANNOT MOVE]" if enc >= 999 else "")
            lines.append(f"\nWeight: {total:.1f}/{max_weight:.1f} kg{enc_str}")

        if session.ap_tracker:
            lines.append(f"AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap}")

        return ActionResult(narrative="\n".join(lines), scene_type=session.dm_context.scene_type)

    def _handle_pickup(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = action.target or ""
        px, py = session.position[0], session.position[1]
        match = None
        if session.spatial_index:
            entities_here = session.spatial_index.at(px, py)
            items_here = [entity for entity in entities_here if entity.entity_type == EntityType.ITEM]
            if target:
                target_lower = target.lower()
                match = next((entity for entity in items_here if target_lower in entity.name.lower()), None)
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
        return ActionResult(narrative=f"You pick up {match.name}.", scene_type=session.dm_context.scene_type)

    def _handle_drop(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = (action.target or "").lower()
        if not target:
            return ActionResult(
                narrative="Drop what? Specify an item name.",
                scene_type=session.dm_context.scene_type,
            )
        if session.find_inventory_item(target) is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )
        ap_fail = self._check_ap(session, "pick_up")
        if ap_fail:
            return ap_fail

        item = session.remove_item(target)
        if item is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )
        self._spawn_ground_item(session, item)
        return ActionResult(narrative=f"You drop {item['name']} on the ground.", scene_type=session.dm_context.scene_type)

    def _handle_stash(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult
        from engine.world.inventory import ItemStack as _ItemStack

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
        removed = session.remove_item(target)
        if removed is None:
            return ActionResult(
                narrative=f"You don't have '{target}' in your inventory.",
                scene_type=session.dm_context.scene_type,
            )
        stack = _ItemStack.from_legacy_dict(removed)
        location = (location or "sock_left").replace(" ", "_")
        if session.physical_inventory:
            success, message = session.physical_inventory.stash_in(location, stack)
            if success:
                return ActionResult(narrative=message, scene_type=session.dm_context.scene_type)
            session.add_item(removed)
            return ActionResult(narrative=message, scene_type=session.dm_context.scene_type)
        session.add_item(removed)
        return ActionResult(narrative="No stash locations available.", scene_type=session.dm_context.scene_type)

    def _handle_rotate_item(self, session: GameSession, action: ParsedAction):
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

    def _spawn_ground_item(self, session: GameSession, item: dict[str, Any]) -> Entity:
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

    def _add_or_drop_item(self, session: GameSession, item: dict[str, Any], merge: bool = True) -> bool:
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

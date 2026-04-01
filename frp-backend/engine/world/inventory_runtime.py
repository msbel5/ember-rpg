"""Physical inventory runtime."""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .inventory_layouts import (
    DEFAULT_EQUIPMENT_SLOTS,
    container_kwargs,
    default_backpack_kwargs,
    default_belt_kwargs,
    default_hidden_stash_specs,
    default_pocket_specs,
    default_stash_tiers,
)
from .inventory_models import Container, ItemStack
from .inventory_types import StashTier


def _build_container(spec: Dict[str, object]) -> Container:
    return Container(**container_kwargs(spec))


def _default_pockets() -> List[Container]:
    return [_build_container(spec) for spec in default_pocket_specs()]


def _default_hidden_stashes() -> Dict[str, Container]:
    return {
        stash_id: _build_container(spec)
        for stash_id, spec in default_hidden_stash_specs().items()
    }


@dataclass
class PhysicalInventory:
    """Complete physical inventory for any entity."""

    equipment: Dict[str, Optional[ItemStack]] = field(
        default_factory=lambda: {slot: None for slot in DEFAULT_EQUIPMENT_SLOTS}
    )
    backpack: Optional[Container] = None
    belt: Optional[Container] = None
    pockets: List[Container] = field(default_factory=list)
    held_left: Optional[ItemStack] = None
    held_right: Optional[ItemStack] = None
    hidden_stashes: Dict[str, Container] = field(default_factory=dict)
    _stash_tiers: Dict[str, StashTier] = field(default_factory=dict)

    def __post_init__(self):
        if self.backpack is None:
            self.backpack = Container(**default_backpack_kwargs())
        if self.belt is None:
            self.belt = Container(**default_belt_kwargs())
        if not self.pockets:
            self.pockets = _default_pockets()
        if not self.hidden_stashes:
            self.hidden_stashes = _default_hidden_stashes()
            self._stash_tiers = default_stash_tiers()

    def total_carried_weight(self) -> float:
        total = 0.0
        if self.backpack:
            total += self.backpack.total_weight()
        if self.belt:
            total += self.belt.total_weight()
        total += sum(pocket.total_weight() for pocket in self.pockets)
        total += sum(stash.total_weight() for stash in self.hidden_stashes.values())
        if self.held_left:
            total += self.held_left.weight
        if self.held_right:
            total += self.held_right.weight
        total += sum(stack.weight for stack in self.equipment.values() if stack)
        return total

    def max_carry_weight(self, strength_modifier: int = 0) -> float:
        return 10.0 + (strength_modifier * 5.0)

    def is_overencumbered(self, strength_modifier: int = 0) -> bool:
        return self.total_carried_weight() > self.max_carry_weight(strength_modifier)

    def encumbrance_ratio(self, strength_modifier: int = 0) -> float:
        max_weight = self.max_carry_weight(strength_modifier)
        return 999.0 if max_weight <= 0 else self.total_carried_weight() / max_weight

    def encumbrance_ap_penalty(self, strength_modifier: int = 0) -> int:
        ratio = self.encumbrance_ratio(strength_modifier)
        if ratio <= 0.75:
            return 0
        if ratio <= 1.0:
            return 1
        if ratio <= 1.25:
            return 2
        return 999

    def all_containers(self) -> List[Container]:
        result: List[Container] = []
        if self.belt:
            result.append(self.belt)
        result.extend(self.pockets)
        if self.backpack:
            result.append(self.backpack)
        return result

    def can_add_item_auto(self, item: ItemStack, merge: bool = True) -> bool:
        preview = copy.deepcopy(self)
        preview_stack = copy.deepcopy(item)
        success, _message = preview.add_item_auto(preview_stack, merge=merge)
        return success

    def add_item_auto(self, item: ItemStack, merge: bool = True) -> Tuple[bool, str]:
        for container in self.all_containers():
            if merge and item.stackable:
                for existing in container.placed_items.values():
                    if existing.stack_signature() == item.stack_signature() and existing.quantity < existing.max_stack:
                        space = existing.max_stack - existing.quantity
                        per_unit_weight = float(existing.item_data.get("weight", 0.5))
                        weight_space = int(container.remaining_weight() // per_unit_weight) if per_unit_weight > 0 else item.quantity
                        added = min(space, item.quantity, max(0, weight_space))
                        if added <= 0:
                            continue
                        existing.quantity += added
                        item.quantity -= added
                        if item.quantity <= 0:
                            return True, f"Added {item.name} to stack."

        for container in self.all_containers():
            if item.matter_state not in container.accepted_states:
                continue
            fit = container.auto_fit(item)
            if fit:
                row, col, shape = fit
                container.place_item(item, row, col, shape)
                return True, f"Placed {item.name} in {container.container_id}."
        return False, f"No room for {item.name}. Your containers are full."

    def remove_item(self, query: str, quantity: int = 1) -> Optional[ItemStack]:
        for container in self.all_containers():
            stack = container.find_item(query)
            if stack:
                if stack.quantity <= quantity:
                    return container.remove_item(stack.instance_id)
                stack.quantity -= quantity
                return ItemStack(
                    item_id=stack.item_id,
                    quantity=quantity,
                    item_data=copy.deepcopy(stack.item_data),
                    instance_id=str(uuid.uuid4())[:8],
                    shape=stack.shape,
                )
        for stash in self.hidden_stashes.values():
            stack = stash.find_item(query)
            if stack:
                if stack.quantity <= quantity:
                    return stash.remove_item(stack.instance_id)
                stack.quantity -= quantity
                return ItemStack(
                    item_id=stack.item_id,
                    quantity=quantity,
                    item_data=copy.deepcopy(stack.item_data),
                    instance_id=str(uuid.uuid4())[:8],
                    shape=stack.shape,
                )
        return None

    def find_item(self, query: str) -> Optional[ItemStack]:
        for container in self.all_containers():
            found = container.find_item(query)
            if found:
                return found
        for stash in self.hidden_stashes.values():
            found = stash.find_item(query)
            if found:
                return found
        return None

    def all_items(self) -> List[ItemStack]:
        items: List[ItemStack] = []
        for container in self.all_containers():
            items.extend(container.all_items())
        return items

    def all_items_flat(self) -> List[Dict]:
        return [stack.to_legacy_dict() for stack in self.all_items()]

    def stash_in(self, location: str, item: ItemStack) -> Tuple[bool, str]:
        stash = self.hidden_stashes.get(location)
        if not stash:
            return False, f"No stash location '{location}'."
        fit = stash.auto_fit(item)
        if not fit:
            return False, f"The {location} stash is full."
        row, col, shape = fit
        stash.place_item(item, row, col, shape)
        return True, f"You secretly stash {item.name} in your {location.replace('_', ' ')}."

    def get_stash_tier(self, location: str) -> StashTier:
        return self._stash_tiers.get(location, StashTier.SIMPLE)

    def fill_liquid_container(self, container_query: str, liquid_id: str, amount_ml: int) -> Tuple[bool, str]:
        for container in self.all_containers():
            stack = container.find_item(container_query)
            if stack and stack.item_data.get("container_type", {}).get("liquid_capacity_ml"):
                capacity = stack.item_data["container_type"]["liquid_capacity_ml"]
                current = (stack.contained_matter or {}).get("amount_ml", 0)
                space = capacity - current
                filled = min(space, amount_ml)
                if filled <= 0:
                    return False, f"The {stack.name} is already full."
                stack.contained_matter = {"item_id": liquid_id, "amount_ml": current + filled}
                return True, f"You fill the {stack.name} with {filled}ml of {liquid_id}."
        return False, "You don't have a container for liquids."

    def to_dict(self) -> Dict:
        return {
            "equipment": {slot: stack.to_dict() if stack else None for slot, stack in self.equipment.items()},
            "backpack": self.backpack.to_dict() if self.backpack else None,
            "belt": self.belt.to_dict() if self.belt else None,
            "pockets": [pocket.to_dict() for pocket in self.pockets],
            "held_left": self.held_left.to_dict() if self.held_left else None,
            "held_right": self.held_right.to_dict() if self.held_right else None,
            "hidden_stashes": {key: value.to_dict() for key, value in self.hidden_stashes.items()},
            "stash_tiers": {key: value.value for key, value in self._stash_tiers.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PhysicalInventory":
        inventory = cls.__new__(cls)
        inventory.equipment = {
            slot: ItemStack.from_dict(value) if value else None
            for slot, value in data.get("equipment", {}).items()
        }
        for slot in DEFAULT_EQUIPMENT_SLOTS:
            inventory.equipment.setdefault(slot, None)
        inventory.backpack = Container.from_dict(data["backpack"]) if data.get("backpack") else None
        inventory.belt = Container.from_dict(data["belt"]) if data.get("belt") else None
        inventory.pockets = [Container.from_dict(pocket) for pocket in data.get("pockets", [])]
        inventory.held_left = ItemStack.from_dict(data["held_left"]) if data.get("held_left") else None
        inventory.held_right = ItemStack.from_dict(data["held_right"]) if data.get("held_right") else None
        inventory.hidden_stashes = {
            key: Container.from_dict(value)
            for key, value in data.get("hidden_stashes", {}).items()
        }
        inventory._stash_tiers = {
            key: StashTier(value)
            for key, value in data.get("stash_tiers", {}).items()
        }
        if inventory.backpack is None:
            inventory.backpack = Container(**default_backpack_kwargs())
        if inventory.belt is None:
            inventory.belt = Container(**default_belt_kwargs())
        if not inventory.pockets:
            inventory.pockets = _default_pockets()
        if not inventory.hidden_stashes:
            inventory.hidden_stashes = _default_hidden_stashes()
            inventory._stash_tiers = default_stash_tiers()
        return inventory

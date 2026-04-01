"""Inventory item and container models."""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set, Tuple

from engine.world.matter_state import MatterState, get_matter_state

from .inventory_layouts import SHAPES, get_item_shape
from .inventory_types import ItemShape

_STACK_EXCLUDED_ITEM_KEYS = {"qty", "quantity", "instance_id", "ground_instance_id", "entity_id"}


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze_value(val)) for key, val in value.items()))
    if isinstance(value, list):
        return tuple(_freeze_value(entry) for entry in value)
    return value


@dataclass
class ItemStack:
    """One item or stack of identical items placed in a container."""

    item_id: str
    quantity: int
    item_data: Dict[str, Any]
    instance_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    shape: ItemShape = field(default_factory=lambda: SHAPES["tiny"])
    orientation: int = 0
    contained_matter: Optional[Dict] = None

    @property
    def name(self) -> str:
        return self.item_data.get("name", self.item_id)

    @property
    def weight(self) -> float:
        return float(self.item_data.get("weight", 0.5)) * self.quantity

    @property
    def matter_state(self) -> MatterState:
        return get_matter_state(self.item_data)

    @property
    def stackable(self) -> bool:
        if self.item_data.get("slot") or self.item_data.get("uses") is not None:
            return False
        return self.item_data.get("stackable", True)

    @property
    def max_stack(self) -> int:
        return self.item_data.get("max_stack", 20 if self.stackable else 1)

    def active_shape(self) -> ItemShape:
        return self.shape.rotated(self.orientation) if self.shape.rigid else self.shape

    def stack_signature(self) -> Tuple[Any, ...]:
        metadata = tuple(
            sorted(
                (str(key), _freeze_value(value))
                for key, value in self.item_data.items()
                if key not in _STACK_EXCLUDED_ITEM_KEYS
            )
        )
        contained = _freeze_value(self.contained_matter) if self.contained_matter is not None else None
        return (self.item_id, metadata, contained)

    def to_dict(self) -> Dict:
        payload = {
            "item_id": self.item_id,
            "quantity": self.quantity,
            "item_data": self.item_data,
            "instance_id": self.instance_id,
            "shape": self.shape.to_dict(),
            "orientation": self.orientation,
        }
        if self.contained_matter:
            payload["contained_matter"] = self.contained_matter
        return payload

    @classmethod
    def from_dict(cls, data: Dict) -> "ItemStack":
        shape = ItemShape.from_dict(data["shape"]) if "shape" in data else SHAPES["tiny"]
        return cls(
            item_id=data["item_id"],
            quantity=data.get("quantity", 1),
            item_data=data.get("item_data", {}),
            instance_id=data.get("instance_id", str(uuid.uuid4())[:8]),
            shape=shape,
            orientation=data.get("orientation", 0),
            contained_matter=data.get("contained_matter"),
        )

    @classmethod
    def from_legacy_dict(cls, item: Dict) -> "ItemStack":
        item_data = copy.deepcopy(dict(item))
        item_id = item_data.pop("id", item_data.get("item_id", "unknown"))
        quantity = item_data.pop("qty", 1)
        instance_id = item_data.pop("instance_id", None) or item_data.pop("ground_instance_id", None) or str(uuid.uuid4())[:8]
        contained_matter = item_data.pop("contained_matter", None)
        shape = get_item_shape(item_data)
        return cls(
            item_id=item_id,
            quantity=quantity,
            item_data={**item_data, "id": item_id},
            instance_id=instance_id,
            shape=shape,
            contained_matter=copy.deepcopy(contained_matter),
        )

    def to_legacy_dict(self) -> Dict:
        payload = dict(self.item_data)
        payload["id"] = self.item_id
        payload["qty"] = self.quantity
        payload["instance_id"] = self.instance_id
        if self.contained_matter:
            payload["contained_matter"] = self.contained_matter
        return payload


@dataclass
class Container:
    """A grid-based container such as a backpack or stash."""

    container_id: str
    rows: int
    cols: int
    max_weight: float = 999.0
    accepted_states: list[MatterState] = field(default_factory=lambda: [MatterState.SOLID])
    sealed: bool = False
    liquid_capacity_ml: int = 0
    current_liquid: Optional[Dict] = None
    grid: list[list[Optional[str]]] = field(default=None)
    placed_items: Dict[str, ItemStack] = field(default_factory=dict)

    def __post_init__(self):
        if self.grid is None:
            self.grid = [[None] * self.cols for _ in range(self.rows)]

    def total_weight(self) -> float:
        return sum(stack.weight for stack in self.placed_items.values())

    def remaining_weight(self) -> float:
        return max(0.0, self.max_weight - self.total_weight())

    def slot_count(self) -> int:
        return self.rows * self.cols

    def used_slots(self) -> int:
        return sum(1 for row in self.grid for cell in row if cell is not None)

    def free_slots(self) -> int:
        return self.slot_count() - self.used_slots()

    def all_items(self) -> list[ItemStack]:
        return list(self.placed_items.values())

    def find_item(self, query: str) -> Optional[ItemStack]:
        query_lower = query.lower()
        for stack in self.placed_items.values():
            if query_lower == stack.item_id.lower() or query_lower == stack.instance_id.lower():
                return stack
            if query_lower in stack.name.lower():
                return stack
        return None

    def can_place(self, item: ItemStack, row: int, col: int, shape: Optional[ItemShape] = None) -> bool:
        active = shape or item.active_shape()
        if item.weight + self.total_weight() > self.max_weight or item.matter_state not in self.accepted_states:
            return False
        for delta_row, delta_col in active.cells:
            target_row, target_col = row + delta_row, col + delta_col
            if target_row < 0 or target_row >= self.rows or target_col < 0 or target_col >= self.cols:
                return False
            if self.grid[target_row][target_col] is not None:
                return False
        return True

    def place_item(self, item: ItemStack, row: int, col: int, shape: Optional[ItemShape] = None) -> bool:
        if not self.can_place(item, row, col, shape):
            return False
        active = shape or item.active_shape()
        for delta_row, delta_col in active.cells:
            self.grid[row + delta_row][col + delta_col] = item.instance_id
        self.placed_items[item.instance_id] = item
        return True

    def remove_item(self, instance_id: str) -> Optional[ItemStack]:
        stack = self.placed_items.pop(instance_id, None)
        if stack is None:
            return None
        for row in range(self.rows):
            for col in range(self.cols):
                if self.grid[row][col] == instance_id:
                    self.grid[row][col] = None
        return stack

    def auto_fit(self, item: ItemStack) -> Optional[Tuple[int, int, ItemShape]]:
        shapes_to_try = item.shape.all_orientations() if item.shape.rigid else [item.shape]
        for shape in shapes_to_try:
            for row in range(self.rows):
                for col in range(self.cols):
                    if self.can_place(item, row, col, shape):
                        return (row, col, shape)
        return None

    def to_dict(self) -> Dict:
        return {
            "container_id": self.container_id,
            "rows": self.rows,
            "cols": self.cols,
            "max_weight": self.max_weight,
            "accepted_states": [state.value for state in self.accepted_states],
            "sealed": self.sealed,
            "liquid_capacity_ml": self.liquid_capacity_ml,
            "current_liquid": self.current_liquid,
            "grid": [list(row) for row in self.grid],
            "placed_items": {key: value.to_dict() for key, value in self.placed_items.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Container":
        container = cls(
            container_id=data["container_id"],
            rows=data["rows"],
            cols=data["cols"],
            max_weight=data.get("max_weight", 999.0),
            accepted_states=[MatterState(value) for value in data.get("accepted_states", ["solid"])],
            sealed=data.get("sealed", False),
            liquid_capacity_ml=data.get("liquid_capacity_ml", 0),
            current_liquid=data.get("current_liquid"),
        )
        container.grid = [list(row) for row in data.get("grid", container.grid)]
        for key, value in data.get("placed_items", {}).items():
            container.placed_items[key] = ItemStack.from_dict(value)
        return container

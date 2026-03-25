"""
Physical Inventory System — RE4-style grid + Dark Souls passive management.

Every entity (player, NPC, merchant, caravan) uses the same system.
Items have physical shapes, weight, volume, and matter state.
Containers enforce capacity, weight limits, and matter state rules.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from engine.world.matter_state import MatterState, get_matter_state, validate_storage


# ---------------------------------------------------------------------------
# Item Shape (RE4-style multi-cell footprint)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ItemShape:
    """Grid footprint of an item. cells = list of (row_offset, col_offset) from anchor."""
    cells: Tuple[Tuple[int, int], ...]
    rigid: bool = True  # rigid=fixed shape (sword), non-rigid=reshapeable (scroll)

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def rotated(self, degrees: int) -> "ItemShape":
        """Rotate shape by 90/180/270 degrees. Only meaningful for rigid items."""
        if degrees == 0:
            return self
        rotated_cells = list(self.cells)
        for _ in range(degrees // 90):
            rotated_cells = [(-c, r) for r, c in rotated_cells]
        # Normalize to positive offsets
        min_r = min(r for r, c in rotated_cells)
        min_c = min(c for r, c in rotated_cells)
        normalized = tuple(sorted((r - min_r, c - min_c) for r, c in rotated_cells))
        return ItemShape(cells=normalized, rigid=self.rigid)

    def all_orientations(self) -> List["ItemShape"]:
        """Return all unique orientations (rotations) of this shape."""
        if not self.rigid:
            return [self]  # non-rigid items don't rotate, they reshape
        seen: Set[Tuple[Tuple[int, int], ...]] = set()
        result = []
        for deg in (0, 90, 180, 270):
            rotated = self.rotated(deg)
            if rotated.cells not in seen:
                seen.add(rotated.cells)
                result.append(rotated)
        return result

    def bounding_box(self) -> Tuple[int, int]:
        """Return (rows, cols) bounding box."""
        if not self.cells:
            return (0, 0)
        max_r = max(r for r, c in self.cells) + 1
        max_c = max(c for r, c in self.cells) + 1
        return (max_r, max_c)

    def to_dict(self) -> Dict:
        return {"cells": [list(c) for c in self.cells], "rigid": self.rigid}

    @classmethod
    def from_dict(cls, data: Dict) -> "ItemShape":
        cells = tuple(tuple(c) for c in data.get("cells", [(0, 0)]))
        return cls(cells=cells, rigid=data.get("rigid", True))


# Common predefined shapes
SHAPES: Dict[str, ItemShape] = {
    # 1-cell items
    "tiny": ItemShape(cells=((0, 0),), rigid=True),            # potion, gem, coin, key
    # 2-cell items
    "small_h": ItemShape(cells=((0, 0), (0, 1)), rigid=True),  # dagger, scroll
    "small_v": ItemShape(cells=((0, 0), (1, 0)), rigid=True),  # wand
    # 3-cell items
    "medium_h": ItemShape(cells=((0, 0), (0, 1), (0, 2)), rigid=True),  # short sword
    "medium_flex": ItemShape(cells=((0, 0), (0, 1), (0, 2)), rigid=False),  # rope, scroll
    # 4-cell items
    "long": ItemShape(cells=((0, 0), (0, 1), (0, 2), (0, 3)), rigid=True),  # longsword, staff
    "square_2x2": ItemShape(cells=((0, 0), (0, 1), (1, 0), (1, 1)), rigid=True),  # shield, helmet
    "t_shape": ItemShape(cells=((0, 0), (0, 1), (0, 2), (1, 1)), rigid=True),  # crossbow
    # 6-cell items
    "large": ItemShape(cells=((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)), rigid=True),  # plate armor, chest
}

# Map item types to default shapes
ITEM_TYPE_SHAPES: Dict[str, str] = {
    "weapon_sword": "medium_h",
    "weapon_dagger": "small_h",
    "weapon_staff": "long",
    "weapon_bow": "long",
    "armor_light": "square_2x2",
    "armor_medium": "square_2x2",
    "armor_heavy": "large",
    "shield": "square_2x2",
    "helmet": "small_h",
    "boots": "small_h",
    "gloves": "tiny",
    "ring": "tiny",
    "amulet": "tiny",
    "potion": "tiny",
    "consumable": "tiny",
    "tool": "small_h",
    "scroll": "medium_flex",
    "rope": "medium_flex",
    "gem": "tiny",
    "currency": "tiny",
    "container": "square_2x2",
    "default": "tiny",
}


def get_item_shape(item_data: Dict) -> ItemShape:
    """Determine the grid shape for an item based on its data."""
    # Explicit shape in item data
    if "item_shape" in item_data:
        return ItemShape.from_dict(item_data["item_shape"])
    # Named shape reference
    shape_name = item_data.get("shape_name")
    if shape_name and shape_name in SHAPES:
        return SHAPES[shape_name]
    # Infer from item type
    item_type = item_data.get("type", "default")
    armor_type = item_data.get("armor_type", "")
    if item_type == "weapon":
        dmg = item_data.get("damage", 0) or 0
        if dmg <= 4:
            return SHAPES["small_h"]  # dagger
        elif dmg <= 7:
            return SHAPES["medium_h"]  # sword
        else:
            return SHAPES["long"]  # greatsword
    if item_type == "armor":
        if armor_type == "heavy" or (item_data.get("ac_bonus", 0) or 0) >= 5:
            return SHAPES["large"]
        return SHAPES["square_2x2"]
    type_key = f"{item_type}_{armor_type}" if armor_type else item_type
    shape_name = ITEM_TYPE_SHAPES.get(type_key, ITEM_TYPE_SHAPES.get(item_type, "tiny"))
    return SHAPES.get(shape_name, SHAPES["tiny"])


# ---------------------------------------------------------------------------
# Item Stack
# ---------------------------------------------------------------------------

@dataclass
class ItemStack:
    """One item (or stack of identical items) placed in a container."""
    item_id: str
    quantity: int
    item_data: Dict[str, Any]
    instance_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    shape: ItemShape = field(default_factory=lambda: SHAPES["tiny"])
    orientation: int = 0  # 0/90/180/270
    contained_matter: Optional[Dict] = None  # for liquid/gas containers: {"item_id": "water", "amount_ml": 500}

    @property
    def name(self) -> str:
        return self.item_data.get("name", self.item_id)

    @property
    def weight(self) -> float:
        """Total weight of this stack (item weight * quantity)."""
        per_unit = float(self.item_data.get("weight", 0.5))
        return per_unit * self.quantity

    @property
    def matter_state(self) -> MatterState:
        return get_matter_state(self.item_data)

    @property
    def stackable(self) -> bool:
        """Items with slots (equipment) or unique properties don't stack."""
        if self.item_data.get("slot"):
            return False
        if self.item_data.get("uses") is not None:
            return False
        return self.item_data.get("stackable", True)

    @property
    def max_stack(self) -> int:
        return self.item_data.get("max_stack", 20 if self.stackable else 1)

    def active_shape(self) -> ItemShape:
        """Return shape in current orientation."""
        if self.shape.rigid:
            return self.shape.rotated(self.orientation)
        return self.shape

    def to_dict(self) -> Dict:
        d = {
            "item_id": self.item_id,
            "quantity": self.quantity,
            "item_data": self.item_data,
            "instance_id": self.instance_id,
            "shape": self.shape.to_dict(),
            "orientation": self.orientation,
        }
        if self.contained_matter:
            d["contained_matter"] = self.contained_matter
        return d

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
        """Convert a legacy flat inventory dict to ItemStack."""
        item_data = dict(item)
        item_id = item_data.pop("id", item_data.get("item_id", "unknown"))
        qty = item_data.pop("qty", 1)
        inst_id = item_data.pop("instance_id", None) or item_data.pop("ground_instance_id", None) or str(uuid.uuid4())[:8]
        shape = get_item_shape(item_data)
        return cls(
            item_id=item_id,
            quantity=qty,
            item_data={**item_data, "id": item_id},
            instance_id=inst_id,
            shape=shape,
        )

    def to_legacy_dict(self) -> Dict:
        """Convert back to flat inventory dict for backward compatibility."""
        d = dict(self.item_data)
        d["id"] = self.item_id
        d["qty"] = self.quantity
        d["instance_id"] = self.instance_id
        if self.contained_matter:
            d["contained_matter"] = self.contained_matter
        return d


# ---------------------------------------------------------------------------
# Container (grid-based)
# ---------------------------------------------------------------------------

@dataclass
class Container:
    """A grid-based container (backpack, belt, pocket, etc.)."""
    container_id: str
    rows: int
    cols: int
    max_weight: float = 999.0
    accepted_states: List[MatterState] = field(default_factory=lambda: [MatterState.SOLID])
    sealed: bool = False
    liquid_capacity_ml: int = 0
    current_liquid: Optional[Dict] = None  # {"item_id": "water", "amount_ml": 300}

    # Grid: each cell holds an instance_id or None
    grid: List[List[Optional[str]]] = field(default=None)
    placed_items: Dict[str, ItemStack] = field(default_factory=dict)

    def __post_init__(self):
        if self.grid is None:
            self.grid = [[None] * self.cols for _ in range(self.rows)]

    # -- Query --
    def total_weight(self) -> float:
        return sum(s.weight for s in self.placed_items.values())

    def remaining_weight(self) -> float:
        return max(0.0, self.max_weight - self.total_weight())

    def slot_count(self) -> int:
        return self.rows * self.cols

    def used_slots(self) -> int:
        count = 0
        for row in self.grid:
            for cell in row:
                if cell is not None:
                    count += 1
        return count

    def free_slots(self) -> int:
        return self.slot_count() - self.used_slots()

    def all_items(self) -> List[ItemStack]:
        return list(self.placed_items.values())

    def find_item(self, query: str) -> Optional[ItemStack]:
        query_lower = query.lower()
        for stack in self.placed_items.values():
            if query_lower == stack.item_id.lower() or query_lower == stack.instance_id.lower():
                return stack
            if query_lower in stack.name.lower():
                return stack
        return None

    # -- Placement --
    def can_place(self, item: ItemStack, row: int, col: int, shape: Optional[ItemShape] = None) -> bool:
        """Check if item shape fits at (row, col) without overlap."""
        active = shape or item.active_shape()
        if item.weight + self.total_weight() > self.max_weight:
            return False
        # Matter state check
        if item.matter_state not in self.accepted_states:
            return False
        for dr, dc in active.cells:
            r, c = row + dr, col + dc
            if r < 0 or r >= self.rows or c < 0 or c >= self.cols:
                return False
            if self.grid[r][c] is not None:
                return False
        return True

    def place_item(self, item: ItemStack, row: int, col: int, shape: Optional[ItemShape] = None) -> bool:
        """Place item at position. Returns True if successful."""
        if not self.can_place(item, row, col, shape):
            return False
        active = shape or item.active_shape()
        for dr, dc in active.cells:
            self.grid[row + dr][col + dc] = item.instance_id
        self.placed_items[item.instance_id] = item
        return True

    def remove_item(self, instance_id: str) -> Optional[ItemStack]:
        """Remove item by instance_id. Returns the removed ItemStack."""
        stack = self.placed_items.pop(instance_id, None)
        if stack is None:
            return None
        # Clear grid cells
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == instance_id:
                    self.grid[r][c] = None
        return stack

    def auto_fit(self, item: ItemStack) -> Optional[Tuple[int, int, ItemShape]]:
        """Find the first position where item fits, trying all orientations.
        Returns (row, col, shape) or None.
        """
        shapes_to_try = item.shape.all_orientations() if item.shape.rigid else [item.shape]
        for shape in shapes_to_try:
            for r in range(self.rows):
                for c in range(self.cols):
                    if self.can_place(item, r, c, shape):
                        return (r, c, shape)
        return None

    # -- Serialization --
    def to_dict(self) -> Dict:
        return {
            "container_id": self.container_id,
            "rows": self.rows,
            "cols": self.cols,
            "max_weight": self.max_weight,
            "accepted_states": [s.value for s in self.accepted_states],
            "sealed": self.sealed,
            "liquid_capacity_ml": self.liquid_capacity_ml,
            "current_liquid": self.current_liquid,
            "grid": [list(row) for row in self.grid],
            "placed_items": {k: v.to_dict() for k, v in self.placed_items.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Container":
        c = cls(
            container_id=data["container_id"],
            rows=data["rows"],
            cols=data["cols"],
            max_weight=data.get("max_weight", 999.0),
            accepted_states=[MatterState(s) for s in data.get("accepted_states", ["solid"])],
            sealed=data.get("sealed", False),
            liquid_capacity_ml=data.get("liquid_capacity_ml", 0),
            current_liquid=data.get("current_liquid"),
        )
        c.grid = [list(row) for row in data.get("grid", c.grid)]
        for k, v in data.get("placed_items", {}).items():
            c.placed_items[k] = ItemStack.from_dict(v)
        return c


# ---------------------------------------------------------------------------
# Stash Tier
# ---------------------------------------------------------------------------

class StashTier(int, Enum):
    SIMPLE = 1       # pocket, belt pouch — 50% flat discovery
    ADVANCED = 2     # sock, boot lining — contested skill check
    MAGICAL = 3      # bag of holding — detect magic only


# ---------------------------------------------------------------------------
# Physical Inventory
# ---------------------------------------------------------------------------

DEFAULT_EQUIPMENT_SLOTS = {
    "weapon": None, "armor": None, "shield": None, "helmet": None,
    "boots": None, "gloves": None, "ring": None, "amulet": None,
    "backpack": None, "belt": None, "cloak": None, "quiver": None,
}


@dataclass
class PhysicalInventory:
    """Complete physical inventory for any entity (player, NPC, merchant)."""
    equipment: Dict[str, Optional[ItemStack]] = field(
        default_factory=lambda: {k: None for k in DEFAULT_EQUIPMENT_SLOTS}
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
            self.backpack = Container(
                container_id="backpack", rows=6, cols=4,
                max_weight=30.0, accepted_states=[MatterState.SOLID],
            )
        if self.belt is None:
            self.belt = Container(
                container_id="belt", rows=1, cols=4,
                max_weight=5.0, accepted_states=[MatterState.SOLID],
            )
        if not self.pockets:
            self.pockets = [
                Container(container_id="pocket_left", rows=1, cols=2, max_weight=1.0, accepted_states=[MatterState.SOLID]),
                Container(container_id="pocket_right", rows=1, cols=2, max_weight=1.0, accepted_states=[MatterState.SOLID]),
            ]
        if not self.hidden_stashes:
            self.hidden_stashes = {
                "sock_left": Container(container_id="sock_left", rows=1, cols=1, max_weight=0.5, accepted_states=[MatterState.SOLID]),
                "sock_right": Container(container_id="sock_right", rows=1, cols=1, max_weight=0.5, accepted_states=[MatterState.SOLID]),
                "boot_lining": Container(container_id="boot_lining", rows=1, cols=1, max_weight=0.3, accepted_states=[MatterState.SOLID]),
            }
            self._stash_tiers = {
                "sock_left": StashTier.ADVANCED,
                "sock_right": StashTier.ADVANCED,
                "boot_lining": StashTier.ADVANCED,
            }

    # -- Weight --
    def total_carried_weight(self) -> float:
        total = 0.0
        if self.backpack:
            total += self.backpack.total_weight()
        if self.belt:
            total += self.belt.total_weight()
        for pocket in self.pockets:
            total += pocket.total_weight()
        for stash in self.hidden_stashes.values():
            total += stash.total_weight()
        if self.held_left:
            total += self.held_left.weight
        if self.held_right:
            total += self.held_right.weight
        for eq in self.equipment.values():
            if eq:
                total += eq.weight
        return total

    def max_carry_weight(self, strength_modifier: int = 0) -> float:
        return 10.0 + (strength_modifier * 5.0)

    def is_overencumbered(self, strength_modifier: int = 0) -> bool:
        return self.total_carried_weight() > self.max_carry_weight(strength_modifier)

    def encumbrance_ratio(self, strength_modifier: int = 0) -> float:
        max_w = self.max_carry_weight(strength_modifier)
        if max_w <= 0:
            return 999.0
        return self.total_carried_weight() / max_w

    def encumbrance_ap_penalty(self, strength_modifier: int = 0) -> int:
        ratio = self.encumbrance_ratio(strength_modifier)
        if ratio <= 0.75:
            return 0
        elif ratio <= 1.0:
            return 1
        elif ratio <= 1.25:
            return 2
        return 999  # cannot move

    # -- Add/Remove --
    def all_containers(self) -> List[Container]:
        """Return all containers in priority order for auto-placement."""
        result = []
        if self.belt:
            result.append(self.belt)
        for pocket in self.pockets:
            result.append(pocket)
        if self.backpack:
            result.append(self.backpack)
        return result

    def add_item_auto(self, item: ItemStack) -> Tuple[bool, str]:
        """Auto-place item in the best-fit container. Returns (success, message)."""
        # Try stacking first
        for container in self.all_containers():
            if item.stackable:
                for existing in container.placed_items.values():
                    if existing.item_id == item.item_id and existing.quantity < existing.max_stack:
                        space = existing.max_stack - existing.quantity
                        added = min(space, item.quantity)
                        existing.quantity += added
                        item.quantity -= added
                        if item.quantity <= 0:
                            return True, f"Added {item.name} to stack."

        # Try auto-fit in each container
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
        """Find and remove item from any container."""
        for container in self.all_containers():
            stack = container.find_item(query)
            if stack:
                if stack.quantity <= quantity:
                    return container.remove_item(stack.instance_id)
                else:
                    stack.quantity -= quantity
                    removed = ItemStack(
                        item_id=stack.item_id,
                        quantity=quantity,
                        item_data=copy.deepcopy(stack.item_data),
                        instance_id=str(uuid.uuid4())[:8],
                        shape=stack.shape,
                    )
                    return removed
        # Also check hidden stashes
        for stash in self.hidden_stashes.values():
            stack = stash.find_item(query)
            if stack:
                if stack.quantity <= quantity:
                    return stash.remove_item(stack.instance_id)
                else:
                    stack.quantity -= quantity
                    return ItemStack(
                        item_id=stack.item_id, quantity=quantity,
                        item_data=copy.deepcopy(stack.item_data),
                        instance_id=str(uuid.uuid4())[:8], shape=stack.shape,
                    )
        return None

    def find_item(self, query: str) -> Optional[ItemStack]:
        """Find item across all containers without removing it."""
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
        """Return all items across all containers (not equipment)."""
        items = []
        for container in self.all_containers():
            items.extend(container.all_items())
        return items

    def all_items_flat(self) -> List[Dict]:
        """Return all items as legacy flat dicts for backward compatibility."""
        return [s.to_legacy_dict() for s in self.all_items()]

    # -- Stash operations --
    def stash_in(self, location: str, item: ItemStack) -> Tuple[bool, str]:
        """Hide an item in a stash location."""
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

    # -- Liquid operations --
    def fill_liquid_container(self, container_query: str, liquid_id: str, amount_ml: int) -> Tuple[bool, str]:
        """Fill a liquid container (waterskin, bottle) with liquid."""
        for container in self.all_containers():
            stack = container.find_item(container_query)
            if stack and stack.item_data.get("container_type", {}).get("liquid_capacity_ml"):
                cap = stack.item_data["container_type"]["liquid_capacity_ml"]
                current = (stack.contained_matter or {}).get("amount_ml", 0)
                space = cap - current
                filled = min(space, amount_ml)
                if filled <= 0:
                    return False, f"The {stack.name} is already full."
                stack.contained_matter = {"item_id": liquid_id, "amount_ml": current + filled}
                return True, f"You fill the {stack.name} with {filled}ml of {liquid_id}."
        return False, "You don't have a container for liquids."

    # -- Serialization --
    def to_dict(self) -> Dict:
        return {
            "equipment": {k: v.to_dict() if v else None for k, v in self.equipment.items()},
            "backpack": self.backpack.to_dict() if self.backpack else None,
            "belt": self.belt.to_dict() if self.belt else None,
            "pockets": [p.to_dict() for p in self.pockets],
            "held_left": self.held_left.to_dict() if self.held_left else None,
            "held_right": self.held_right.to_dict() if self.held_right else None,
            "hidden_stashes": {k: v.to_dict() for k, v in self.hidden_stashes.items()},
            "stash_tiers": {k: v.value for k, v in self._stash_tiers.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PhysicalInventory":
        inv = cls.__new__(cls)
        inv.equipment = {}
        for k, v in data.get("equipment", {}).items():
            inv.equipment[k] = ItemStack.from_dict(v) if v else None
        # Fill missing slots
        for k in DEFAULT_EQUIPMENT_SLOTS:
            if k not in inv.equipment:
                inv.equipment[k] = None
        inv.backpack = Container.from_dict(data["backpack"]) if data.get("backpack") else None
        inv.belt = Container.from_dict(data["belt"]) if data.get("belt") else None
        inv.pockets = [Container.from_dict(p) for p in data.get("pockets", [])]
        inv.held_left = ItemStack.from_dict(data["held_left"]) if data.get("held_left") else None
        inv.held_right = ItemStack.from_dict(data["held_right"]) if data.get("held_right") else None
        inv.hidden_stashes = {k: Container.from_dict(v) for k, v in data.get("hidden_stashes", {}).items()}
        inv._stash_tiers = {k: StashTier(v) for k, v in data.get("stash_tiers", {}).items()}
        # Ensure defaults exist
        if inv.backpack is None:
            inv.backpack = Container(container_id="backpack", rows=6, cols=4, max_weight=30.0, accepted_states=[MatterState.SOLID])
        if inv.belt is None:
            inv.belt = Container(container_id="belt", rows=1, cols=4, max_weight=5.0, accepted_states=[MatterState.SOLID])
        if not inv.pockets:
            inv.pockets = [
                Container(container_id="pocket_left", rows=1, cols=2, max_weight=1.0, accepted_states=[MatterState.SOLID]),
                Container(container_id="pocket_right", rows=1, cols=2, max_weight=1.0, accepted_states=[MatterState.SOLID]),
            ]
        if not inv.hidden_stashes:
            inv.hidden_stashes = {
                "sock_left": Container(container_id="sock_left", rows=1, cols=1, max_weight=0.5, accepted_states=[MatterState.SOLID]),
                "sock_right": Container(container_id="sock_right", rows=1, cols=1, max_weight=0.5, accepted_states=[MatterState.SOLID]),
                "boot_lining": Container(container_id="boot_lining", rows=1, cols=1, max_weight=0.3, accepted_states=[MatterState.SOLID]),
            }
            inv._stash_tiers = {"sock_left": StashTier.ADVANCED, "sock_right": StashTier.ADVANCED, "boot_lining": StashTier.ADVANCED}
        return inv

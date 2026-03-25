"""Tests for Physical Inventory System — RE4 grid, shapes, containers, matter state."""
import pytest
from engine.world.inventory import (
    ItemShape, ItemStack, Container, PhysicalInventory,
    SHAPES, get_item_shape, StashTier,
)
from engine.world.matter_state import MatterState, validate_storage, get_matter_state


# ---------------------------------------------------------------------------
# ItemShape
# ---------------------------------------------------------------------------

class TestItemShape:
    def test_tiny_is_1x1(self):
        s = SHAPES["tiny"]
        assert s.cell_count == 1
        assert s.bounding_box() == (1, 1)

    def test_long_is_1x4(self):
        s = SHAPES["long"]
        assert s.cell_count == 4
        assert s.bounding_box() == (1, 4)

    def test_square_is_2x2(self):
        s = SHAPES["square_2x2"]
        assert s.cell_count == 4
        assert s.bounding_box() == (2, 2)

    def test_rotation_90(self):
        s = SHAPES["long"]  # horizontal 1x4
        rotated = s.rotated(90)
        assert rotated.bounding_box() == (4, 1)  # now vertical
        assert rotated.cell_count == 4

    def test_rotation_180(self):
        s = SHAPES["long"]
        r180 = s.rotated(180)
        assert r180.bounding_box() == (1, 4)  # same as original for symmetric

    def test_all_orientations_symmetric(self):
        s = SHAPES["square_2x2"]
        orientations = s.all_orientations()
        assert len(orientations) == 1  # square is same in all rotations

    def test_all_orientations_long(self):
        s = SHAPES["long"]
        orientations = s.all_orientations()
        assert len(orientations) == 2  # horizontal and vertical

    def test_non_rigid_no_rotation(self):
        s = SHAPES["medium_flex"]
        assert not s.rigid
        orientations = s.all_orientations()
        assert len(orientations) == 1  # non-rigid items don't rotate

    def test_to_dict_roundtrip(self):
        s = SHAPES["t_shape"]
        d = s.to_dict()
        restored = ItemShape.from_dict(d)
        assert restored.cells == s.cells
        assert restored.rigid == s.rigid


# ---------------------------------------------------------------------------
# ItemStack
# ---------------------------------------------------------------------------

class TestItemStack:
    def test_basic_creation(self):
        stack = ItemStack(item_id="bread", quantity=3, item_data={"name": "Bread", "weight": 0.5})
        assert stack.name == "Bread"
        assert stack.weight == 1.5  # 0.5 * 3
        assert stack.stackable

    def test_equipment_not_stackable(self):
        stack = ItemStack(item_id="sword", quantity=1, item_data={"name": "Sword", "slot": "weapon"})
        assert not stack.stackable
        assert stack.max_stack == 1

    def test_matter_state_default_solid(self):
        stack = ItemStack(item_id="rock", quantity=1, item_data={"name": "Rock"})
        assert stack.matter_state == MatterState.SOLID

    def test_matter_state_liquid(self):
        stack = ItemStack(item_id="water", quantity=1, item_data={"name": "Water", "matter_state": "liquid"})
        assert stack.matter_state == MatterState.LIQUID

    def test_to_dict_roundtrip(self):
        stack = ItemStack(item_id="gem", quantity=5, item_data={"name": "Ruby", "weight": 0.1}, shape=SHAPES["tiny"])
        d = stack.to_dict()
        restored = ItemStack.from_dict(d)
        assert restored.item_id == "gem"
        assert restored.quantity == 5
        assert restored.shape.cell_count == 1

    def test_from_legacy_dict(self):
        legacy = {"id": "bread", "name": "Bread", "qty": 3, "type": "consumable", "heal": 3, "weight": 0.5}
        stack = ItemStack.from_legacy_dict(legacy)
        assert stack.item_id == "bread"
        assert stack.quantity == 3
        assert stack.shape == SHAPES["tiny"]

    def test_from_legacy_dict_preserves_contained_matter(self):
        legacy = {
            "id": "waterskin",
            "name": "Waterskin",
            "qty": 1,
            "type": "tool",
            "container_type": {"liquid_capacity_ml": 500},
            "contained_matter": {"item_id": "water", "amount_ml": 300},
        }
        stack = ItemStack.from_legacy_dict(legacy)
        assert stack.contained_matter == {"item_id": "water", "amount_ml": 300}

    def test_to_legacy_dict(self):
        stack = ItemStack(item_id="bread", quantity=3, item_data={"name": "Bread", "type": "consumable", "id": "bread"})
        d = stack.to_legacy_dict()
        assert d["id"] == "bread"
        assert d["qty"] == 3
        assert d["name"] == "Bread"

    def test_contained_matter(self):
        stack = ItemStack(
            item_id="waterskin", quantity=1,
            item_data={"name": "Waterskin", "container_type": {"liquid_capacity_ml": 500}},
            contained_matter={"item_id": "water", "amount_ml": 300},
        )
        assert stack.contained_matter["amount_ml"] == 300


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------

class TestContainer:
    def _make_container(self, rows=4, cols=4, max_weight=30.0):
        return Container(container_id="test", rows=rows, cols=cols, max_weight=max_weight)

    def _make_item(self, item_id="gem", shape_name="tiny", weight=0.1):
        shape = SHAPES[shape_name]
        return ItemStack(item_id=item_id, quantity=1, item_data={"name": item_id, "weight": weight}, shape=shape)

    def test_empty_container(self):
        c = self._make_container()
        assert c.total_weight() == 0.0
        assert c.free_slots() == 16
        assert c.used_slots() == 0

    def test_place_tiny_item(self):
        c = self._make_container()
        item = self._make_item()
        assert c.can_place(item, 0, 0)
        assert c.place_item(item, 0, 0)
        assert c.used_slots() == 1
        assert c.grid[0][0] == item.instance_id

    def test_place_long_item(self):
        c = self._make_container()
        item = self._make_item("sword", "long", 2.0)
        assert c.place_item(item, 0, 0)
        assert c.used_slots() == 4
        assert c.grid[0][0] == item.instance_id
        assert c.grid[0][3] == item.instance_id

    def test_overlap_rejected(self):
        c = self._make_container()
        item1 = self._make_item("gem1")
        item2 = self._make_item("gem2")
        c.place_item(item1, 0, 0)
        assert not c.can_place(item2, 0, 0)  # occupied

    def test_out_of_bounds_rejected(self):
        c = self._make_container(rows=2, cols=2)
        item = self._make_item("sword", "long")  # 1x4, won't fit in 2x2
        assert not c.can_place(item, 0, 0)

    def test_weight_limit(self):
        c = self._make_container(max_weight=1.0)
        heavy = self._make_item("anvil", weight=2.0)
        assert not c.can_place(heavy, 0, 0)

    def test_remove_item(self):
        c = self._make_container()
        item = self._make_item()
        c.place_item(item, 0, 0)
        removed = c.remove_item(item.instance_id)
        assert removed is not None
        assert removed.item_id == "gem"
        assert c.used_slots() == 0
        assert c.grid[0][0] is None

    def test_auto_fit(self):
        c = self._make_container()
        item = self._make_item("sword", "long")
        fit = c.auto_fit(item)
        assert fit is not None
        row, col, shape = fit
        assert c.place_item(item, row, col, shape)

    def test_auto_fit_tries_rotations(self):
        c = self._make_container(rows=4, cols=1)  # tall narrow container
        item = self._make_item("sword", "long")  # horizontal 1x4
        # Won't fit horizontally but should fit rotated (4x1)
        fit = c.auto_fit(item)
        assert fit is not None

    def test_find_item_by_name(self):
        c = self._make_container()
        item = self._make_item("healing_potion")
        item.item_data["name"] = "Healing Potion"
        c.place_item(item, 0, 0)
        found = c.find_item("healing")
        assert found is not None
        assert found.item_id == "healing_potion"

    def test_matter_state_rejection(self):
        c = self._make_container()  # default accepts SOLID only
        liquid = ItemStack(item_id="water", quantity=1, item_data={"name": "Water", "matter_state": "liquid", "weight": 1.0})
        assert not c.can_place(liquid, 0, 0)

    def test_to_dict_roundtrip(self):
        c = self._make_container()
        item = self._make_item()
        c.place_item(item, 1, 2)
        d = c.to_dict()
        restored = Container.from_dict(d)
        assert restored.rows == 4
        assert restored.cols == 4
        assert len(restored.placed_items) == 1
        assert restored.grid[1][2] is not None

    def test_2x2_item_placement(self):
        c = self._make_container()
        shield = self._make_item("shield", "square_2x2", 3.0)
        assert c.place_item(shield, 0, 0)
        assert c.grid[0][0] == shield.instance_id
        assert c.grid[0][1] == shield.instance_id
        assert c.grid[1][0] == shield.instance_id
        assert c.grid[1][1] == shield.instance_id
        assert c.used_slots() == 4

    def test_large_item_placement(self):
        c = self._make_container(rows=6, cols=4)
        armor = self._make_item("plate", "large", 8.0)
        assert c.place_item(armor, 0, 0)
        assert c.used_slots() == 6


# ---------------------------------------------------------------------------
# PhysicalInventory
# ---------------------------------------------------------------------------

class TestPhysicalInventory:
    def test_default_containers(self):
        inv = PhysicalInventory()
        assert inv.backpack is not None
        assert inv.backpack.rows == 6
        assert inv.backpack.cols == 4
        assert inv.belt is not None
        assert len(inv.pockets) == 2
        assert len(inv.hidden_stashes) == 3

    def test_add_item_auto_to_belt_first(self):
        inv = PhysicalInventory()
        potion = ItemStack(item_id="potion", quantity=1, item_data={"name": "Potion", "weight": 0.3}, shape=SHAPES["tiny"])
        success, msg = inv.add_item_auto(potion)
        assert success
        assert "belt" in msg  # tiny items go to belt first

    def test_add_item_auto_overflow_to_backpack(self):
        inv = PhysicalInventory()
        # Fill belt (1x4 = 4 slots)
        for i in range(4):
            item = ItemStack(item_id=f"item_{i}", quantity=1, item_data={"name": f"Item {i}", "weight": 0.5}, shape=SHAPES["tiny"])
            inv.add_item_auto(item)
        # Next item should go to pockets or backpack
        extra = ItemStack(item_id="extra", quantity=1, item_data={"name": "Extra", "weight": 0.3}, shape=SHAPES["tiny"])
        success, msg = inv.add_item_auto(extra)
        assert success

    def test_add_large_item_to_backpack(self):
        inv = PhysicalInventory()
        # 2x3 item won't fit in belt (1x4) — must go to backpack
        armor = ItemStack(item_id="plate", quantity=1, item_data={"name": "Plate Armor", "weight": 8.0}, shape=SHAPES["large"])
        success, msg = inv.add_item_auto(armor)
        assert success
        assert "backpack" in msg

    def test_stacking(self):
        inv = PhysicalInventory()
        bread1 = ItemStack(item_id="bread", quantity=2, item_data={"name": "Bread", "weight": 0.3}, shape=SHAPES["tiny"])
        bread2 = ItemStack(item_id="bread", quantity=3, item_data={"name": "Bread", "weight": 0.3}, shape=SHAPES["tiny"])
        inv.add_item_auto(bread1)
        inv.add_item_auto(bread2)
        # Should stack into one entry
        all_bread = [s for s in inv.all_items() if s.item_id == "bread"]
        total_qty = sum(s.quantity for s in all_bread)
        assert total_qty == 5

    def test_stacking_does_not_merge_different_metadata(self):
        inv = PhysicalInventory()
        fine_bread = ItemStack(
            item_id="bread",
            quantity=1,
            item_data={"name": "Bread", "weight": 0.3, "quality": "fine"},
            shape=SHAPES["tiny"],
        )
        spoiled_bread = ItemStack(
            item_id="bread",
            quantity=1,
            item_data={"name": "Bread", "weight": 0.3, "quality": "spoiled"},
            shape=SHAPES["tiny"],
        )
        inv.add_item_auto(fine_bread)
        inv.add_item_auto(spoiled_bread)

        bread_stacks = [stack for stack in inv.all_items() if stack.item_id == "bread"]
        assert len(bread_stacks) == 2
        assert sorted(stack.item_data.get("quality") for stack in bread_stacks) == ["fine", "spoiled"]

    def test_stacking_respects_container_weight_limit(self):
        inv = PhysicalInventory()
        first = ItemStack(item_id="ore", quantity=9, item_data={"name": "Ore", "weight": 0.5}, shape=SHAPES["tiny"])
        second = ItemStack(item_id="ore", quantity=8, item_data={"name": "Ore", "weight": 0.5}, shape=SHAPES["tiny"])

        inv.add_item_auto(first)
        inv.add_item_auto(second)

        assert inv.belt.total_weight() <= inv.belt.max_weight
        assert sum(stack.quantity for stack in inv.all_items() if stack.item_id == "ore") == 17

    def test_remove_item(self):
        inv = PhysicalInventory()
        gem = ItemStack(item_id="ruby", quantity=3, item_data={"name": "Ruby", "weight": 0.1}, shape=SHAPES["tiny"])
        inv.add_item_auto(gem)
        removed = inv.remove_item("ruby", 2)
        assert removed is not None
        assert removed.quantity == 2
        remaining = inv.find_item("ruby")
        assert remaining.quantity == 1

    def test_remove_all(self):
        inv = PhysicalInventory()
        gem = ItemStack(item_id="ruby", quantity=1, item_data={"name": "Ruby", "weight": 0.1}, shape=SHAPES["tiny"])
        inv.add_item_auto(gem)
        removed = inv.remove_item("ruby")
        assert removed is not None
        assert inv.find_item("ruby") is None

    def test_weight_tracking(self):
        inv = PhysicalInventory()
        sword = ItemStack(item_id="sword", quantity=1, item_data={"name": "Sword", "weight": 3.0, "slot": "weapon"}, shape=SHAPES["medium_h"])
        inv.add_item_auto(sword)
        assert inv.total_carried_weight() == 3.0

    def test_encumbrance_penalty(self):
        inv = PhysicalInventory()
        # strength_modifier=0 → max_carry=10kg
        assert inv.encumbrance_ap_penalty(0) == 0  # empty
        # Add 8kg → 80% → penalty 1
        heavy = ItemStack(item_id="anvil", quantity=1, item_data={"name": "Anvil", "weight": 8.0}, shape=SHAPES["tiny"])
        inv.add_item_auto(heavy)
        assert inv.encumbrance_ap_penalty(0) == 1  # 80%

    def test_stash_item(self):
        inv = PhysicalInventory()
        coin = ItemStack(item_id="gold", quantity=2, item_data={"name": "Gold Coin", "weight": 0.05}, shape=SHAPES["tiny"])
        success, msg = inv.stash_in("sock_left", coin)
        assert success
        assert "sock" in msg
        # Verify it's in the stash
        stash = inv.hidden_stashes["sock_left"]
        assert len(stash.placed_items) == 1

    def test_stash_tier(self):
        inv = PhysicalInventory()
        assert inv.get_stash_tier("sock_left") == StashTier.ADVANCED
        assert inv.get_stash_tier("nonexistent") == StashTier.SIMPLE

    def test_all_items_flat(self):
        inv = PhysicalInventory()
        bread = ItemStack(item_id="bread", quantity=3, item_data={"name": "Bread", "type": "consumable", "id": "bread", "weight": 0.3}, shape=SHAPES["tiny"])
        inv.add_item_auto(bread)
        flat = inv.all_items_flat()
        assert len(flat) >= 1
        assert flat[0]["id"] == "bread"
        assert flat[0]["qty"] == 3

    def test_fill_liquid_container(self):
        inv = PhysicalInventory()
        waterskin = ItemStack(
            item_id="waterskin", quantity=1,
            item_data={"name": "Waterskin", "weight": 0.5, "container_type": {"liquid_capacity_ml": 500}},
            shape=SHAPES["small_h"],
        )
        inv.add_item_auto(waterskin)
        success, msg = inv.fill_liquid_container("waterskin", "water", 300)
        assert success
        assert "300ml" in msg
        # Check the contained matter
        found = inv.find_item("waterskin")
        assert found.contained_matter["amount_ml"] == 300

    def test_to_dict_roundtrip(self):
        inv = PhysicalInventory()
        bread = ItemStack(item_id="bread", quantity=2, item_data={"name": "Bread", "weight": 0.3, "id": "bread"}, shape=SHAPES["tiny"])
        inv.add_item_auto(bread)
        coin = ItemStack(item_id="gold", quantity=5, item_data={"name": "Gold", "weight": 0.05, "id": "gold"}, shape=SHAPES["tiny"])
        inv.stash_in("sock_left", coin)

        d = inv.to_dict()
        restored = PhysicalInventory.from_dict(d)
        assert len(restored.all_items()) == 1  # bread in containers
        stash = restored.hidden_stashes["sock_left"]
        assert len(stash.placed_items) == 1


# ---------------------------------------------------------------------------
# Matter State Validation
# ---------------------------------------------------------------------------

class TestMatterState:
    def test_solid_in_backpack(self):
        ok, msg = validate_storage("backpack", MatterState.SOLID)
        assert ok

    def test_liquid_rejected_from_backpack(self):
        ok, msg = validate_storage("backpack", MatterState.LIQUID)
        assert not ok
        assert "container" in msg.lower()

    def test_liquid_in_waterskin(self):
        ok, msg = validate_storage("waterskin", MatterState.LIQUID)
        assert ok

    def test_gas_needs_sealed(self):
        ok, msg = validate_storage("glass_bottle", MatterState.GAS)
        assert not ok
        assert "sealed" in msg.lower()

    def test_gas_in_iron_barrel(self):
        ok, msg = validate_storage("iron_barrel", MatterState.GAS)
        assert ok

    def test_ethereal_only_magical(self):
        ok, msg = validate_storage("backpack", MatterState.ETHEREAL)
        assert not ok
        assert "magical" in msg.lower()

    def test_ethereal_in_bag_of_holding(self):
        ok, msg = validate_storage("bag_of_holding", MatterState.ETHEREAL)
        assert ok

    def test_get_matter_state_default(self):
        assert get_matter_state({}) == MatterState.SOLID

    def test_get_matter_state_explicit(self):
        assert get_matter_state({"matter_state": "liquid"}) == MatterState.LIQUID
        assert get_matter_state({"matter_state": "gas"}) == MatterState.GAS


# ---------------------------------------------------------------------------
# Item Shape Inference
# ---------------------------------------------------------------------------

class TestGetItemShape:
    def test_weapon_small(self):
        shape = get_item_shape({"type": "weapon", "damage": 3})
        assert shape.cell_count == 2  # dagger = small_h

    def test_weapon_medium(self):
        shape = get_item_shape({"type": "weapon", "damage": 6})
        assert shape.cell_count == 3  # sword = medium_h

    def test_weapon_large(self):
        shape = get_item_shape({"type": "weapon", "damage": 10})
        assert shape.cell_count == 4  # greatsword = long

    def test_armor_heavy(self):
        shape = get_item_shape({"type": "armor", "ac_bonus": 6})
        assert shape.cell_count == 6  # plate = large

    def test_consumable_tiny(self):
        shape = get_item_shape({"type": "consumable"})
        assert shape.cell_count == 1

    def test_explicit_shape(self):
        shape = get_item_shape({"item_shape": {"cells": [[0, 0], [0, 1], [1, 0]], "rigid": False}})
        assert shape.cell_count == 3
        assert not shape.rigid

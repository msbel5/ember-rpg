"""
Tests for the Action Point system.
Covers: class AP, spending, refreshing, terrain costs, armor penalties, edge cases.
"""

import pytest

from engine.world.action_points import (
    ACTION_COSTS,
    ARMOR_WEIGHT_PENALTY,
    CLASS_AP,
    ActionPointTracker,
)


# ── CLASS_AP ─────────────────────────────────────────────────────────

class TestClassAP:
    def test_warrior_has_4(self):
        assert CLASS_AP["warrior"] == 4

    def test_rogue_has_6(self):
        assert CLASS_AP["rogue"] == 6

    def test_mage_has_3(self):
        assert CLASS_AP["mage"] == 3

    def test_priest_has_4(self):
        assert CLASS_AP["priest"] == 4


# ── ACTION_COSTS ─────────────────────────────────────────────────────

class TestActionCosts:
    def test_move_flat_costs_1(self):
        assert ACTION_COSTS["move_flat"] == 1

    def test_move_rough_costs_2(self):
        assert ACTION_COSTS["move_rough"] == 2

    def test_attack_melee_costs_2(self):
        assert ACTION_COSTS["attack_melee"] == 2

    def test_attack_ranged_costs_3(self):
        assert ACTION_COSTS["attack_ranged"] == 3

    def test_rest_costs_0(self):
        assert ACTION_COSTS["rest"] == 0

    def test_craft_simple_costs_5(self):
        assert ACTION_COSTS["craft_simple"] == 5

    def test_craft_complex_costs_15(self):
        assert ACTION_COSTS["craft_complex"] == 15


# ── ActionPointTracker basics ────────────────────────────────────────

class TestTrackerBasics:
    def test_starts_at_max(self):
        t = ActionPointTracker(max_ap=4)
        assert t.current_ap == 4

    def test_spend_deducts(self):
        t = ActionPointTracker(max_ap=6)
        assert t.spend(2) is True
        assert t.current_ap == 4

    def test_spend_returns_false_when_insufficient(self):
        t = ActionPointTracker(max_ap=3)
        assert t.spend(4) is False
        assert t.current_ap == 3  # unchanged

    def test_spend_exact_amount(self):
        t = ActionPointTracker(max_ap=4)
        assert t.spend(4) is True
        assert t.current_ap == 0

    def test_spend_zero_ap(self):
        t = ActionPointTracker(max_ap=4)
        assert t.spend(0) is True
        assert t.current_ap == 4

    def test_spend_negative_raises(self):
        t = ActionPointTracker(max_ap=4)
        with pytest.raises(ValueError):
            t.spend(-1)

    def test_refresh_restores_to_max(self):
        t = ActionPointTracker(max_ap=6)
        t.spend(4)
        assert t.current_ap == 2
        t.refresh()
        assert t.current_ap == 6

    def test_can_afford_true(self):
        t = ActionPointTracker(max_ap=4)
        assert t.can_afford(3) is True

    def test_can_afford_false(self):
        t = ActionPointTracker(max_ap=4)
        t.spend(3)
        assert t.can_afford(2) is False

    def test_cannot_act_when_exhausted(self):
        t = ActionPointTracker(max_ap=3)
        t.spend(3)
        assert t.can_afford(1) is False
        assert t.spend(1) is False


# ── Movement with armor penalty ──────────────────────────────────────

class TestArmorPenalty:
    def test_no_armor_no_penalty(self):
        t = ActionPointTracker(max_ap=4, armor_type="none")
        assert t.movement_cost(1) == 1

    def test_leather_no_penalty(self):
        t = ActionPointTracker(max_ap=4, armor_type="leather")
        assert t.movement_cost(1) == 1

    def test_chain_mail_plus_one(self):
        t = ActionPointTracker(max_ap=4, armor_type="chain_mail")
        assert t.movement_cost(1) == 2  # 1 base + 1 penalty

    def test_plate_armor_plus_two(self):
        t = ActionPointTracker(max_ap=4, armor_type="plate_armor")
        assert t.movement_cost(1) == 3  # 1 base + 2 penalty

    def test_rough_terrain_with_plate(self):
        t = ActionPointTracker(max_ap=6, armor_type="plate_armor")
        assert t.movement_cost(2) == 4  # 2 base + 2 penalty

    def test_spend_movement_with_penalty(self):
        t = ActionPointTracker(max_ap=4, armor_type="chain_mail")
        assert t.spend_movement(1) is True  # costs 2
        assert t.current_ap == 2

    def test_cant_move_with_heavy_armor_low_ap(self):
        t = ActionPointTracker(max_ap=4, armor_type="plate_armor")
        t.spend(2)
        # 2 AP left, movement cost = 1 + 2 = 3
        assert t.can_move(1) is False

    def test_set_armor_changes_penalty(self):
        t = ActionPointTracker(max_ap=6, armor_type="none")
        assert t.movement_cost(1) == 1
        t.set_armor("plate_armor")
        assert t.movement_cost(1) == 3

    def test_warrior_in_plate_can_only_move_once_on_flat(self):
        """Warrior has 4 AP, plate costs 3 per flat tile => 1 move then stuck."""
        t = ActionPointTracker(max_ap=4, armor_type="plate_armor")
        assert t.spend_movement(1) is True  # costs 3, left 1
        assert t.spend_movement(1) is False  # costs 3, only 1 left

    def test_rogue_in_leather_moves_six_flat_tiles(self):
        """Rogue has 6 AP, leather has 0 penalty => 6 moves on flat."""
        t = ActionPointTracker(max_ap=6, armor_type="leather")
        for _ in range(6):
            assert t.spend_movement(1) is True
        assert t.current_ap == 0
        assert t.spend_movement(1) is False

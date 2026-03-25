"""Tests for engine.world.body_parts — AC-14..AC-17."""

import pytest
from engine.world.body_parts import (
    ARMOR_COVERAGE,
    HIT_LOCATIONS,
    BodyPartTracker,
    calculate_armor_reduction,
    roll_hit_location,
)


class TestHitLocations:
    def test_all_d20_values_mapped(self):
        for i in range(1, 21):
            assert i in HIT_LOCATIONS

    def test_head_on_1(self):
        assert roll_hit_location(1) == "head"

    def test_neck_on_2(self):
        assert roll_hit_location(2) == "neck"

    def test_torso_range(self):
        for v in (6, 7, 8, 9):
            assert roll_hit_location(v) == "torso"

    def test_right_leg_on_20(self):
        assert roll_hit_location(20) == "right_leg"

    def test_random_roll_returns_valid_part(self):
        valid = {"head", "neck", "chest", "torso",
                 "left_arm", "right_arm", "left_leg", "right_leg"}
        for _ in range(50):
            assert roll_hit_location() in valid

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            roll_hit_location(0)
        with pytest.raises(ValueError):
            roll_hit_location(21)


class TestBodyPartTracker:
    def test_initial_hp(self):
        t = BodyPartTracker()
        assert t.current_hp["head"] == 8
        assert t.current_hp["torso"] == 12

    def test_apply_damage(self):
        t = BodyPartTracker()
        info = t.apply_damage("head", 5)
        assert info["hp_before"] == 8
        assert info["hp_after"] == 3
        assert info["damage_dealt"] == 5

    def test_damage_cannot_go_below_zero(self):
        t = BodyPartTracker()
        t.apply_damage("head", 100)
        assert t.current_hp["head"] == 0

    def test_injury_effects_wounded(self):
        t = BodyPartTracker()
        t.apply_damage("torso", 7)  # 12→5, 5/12 ≈ 0.42 → wounded
        effects = t.get_injury_effects()
        assert "torso" in effects
        assert effects["torso"] == "wounded"

    def test_injury_effects_crippled(self):
        t = BodyPartTracker()
        t.apply_damage("left_arm", 8)  # 10→2, 2/10=0.2 → crippled
        assert t.get_injury_effects()["left_arm"] == "crippled"

    def test_injury_effects_destroyed(self):
        t = BodyPartTracker()
        t.apply_damage("right_leg", 10)
        assert t.get_injury_effects()["right_leg"] == "destroyed"

    def test_heal(self):
        t = BodyPartTracker()
        t.apply_damage("chest", 10)
        t.heal("chest", 5)
        assert t.current_hp["chest"] == 9

    def test_heal_capped_at_max(self):
        t = BodyPartTracker()
        t.apply_damage("chest", 2)
        t.heal("chest", 100)
        assert t.current_hp["chest"] == t.max_hp["chest"]

    def test_is_alive_true(self):
        t = BodyPartTracker()
        assert t.is_alive()

    def test_is_alive_false_head_destroyed(self):
        t = BodyPartTracker()
        t.apply_damage("head", 100)
        assert not t.is_alive()

    def test_unknown_part_raises(self):
        t = BodyPartTracker()
        with pytest.raises(ValueError):
            t.apply_damage("tail", 5)


class TestArmorCoverage:
    def test_helmet_covers_head_and_neck(self):
        piece = ARMOR_COVERAGE["helmet"]
        assert "head" in piece.covers
        assert "neck" in piece.covers

    def test_chainmail_covers_torso_and_chest(self):
        piece = ARMOR_COVERAGE["chainmail"]
        assert "torso" in piece.covers
        assert "chest" in piece.covers

    def test_calculate_armor_single(self):
        red = calculate_armor_reduction("head", ["helmet"])
        assert red == 3

    def test_calculate_armor_stacking(self):
        # helmet(head,neck)=3 + leather_cap(head)=1 → 4 for head
        red = calculate_armor_reduction("head", ["helmet", "leather_cap"])
        assert red == 4

    def test_calculate_armor_no_coverage(self):
        red = calculate_armor_reduction("right_arm", ["helmet", "greaves"])
        assert red == 0

    def test_unknown_armor_ignored(self):
        red = calculate_armor_reduction("head", ["helmet", "nonexistent_item"])
        assert red == 3

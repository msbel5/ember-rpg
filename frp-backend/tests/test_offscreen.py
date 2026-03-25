"""Tests for engine.world.offscreen — AC-34..AC-36."""

import pytest
from engine.world.offscreen import catch_up_location, coarse_tick


class TestCoarseTick:
    def test_stock_decreases_over_time(self):
        stock = {"iron_bar": 100, "bread": 50}
        result = coarse_tick(stock, 10)
        assert stock["iron_bar"] < 100
        assert stock["bread"] < 50

    def test_one_hour_two_percent_loss(self):
        stock = {"iron_bar": 100}
        coarse_tick(stock, 1)
        assert stock["iron_bar"] == 98  # 100 * 0.98 = 98

    def test_multiple_hours_compound(self):
        stock = {"iron_bar": 100}
        coarse_tick(stock, 5)
        # 100 * 0.98^5 ≈ 90.39, int → 90
        assert stock["iron_bar"] == 90

    def test_needs_field_decays_faster(self):
        stock = {"needs": 100.0}
        coarse_tick(stock, 1, needs_decay_rate=0.5)
        assert stock["needs"] == 50.0

    def test_needs_decays_to_near_zero(self):
        stock = {"needs": 100.0}
        coarse_tick(stock, 10, needs_decay_rate=0.5)
        assert stock["needs"] < 1.0

    def test_zero_hours_no_change(self):
        stock = {"iron_bar": 100}
        coarse_tick(stock, 0)
        assert stock["iron_bar"] == 100

    def test_negative_hours_treated_as_zero(self):
        stock = {"iron_bar": 100}
        coarse_tick(stock, -5)
        assert stock["iron_bar"] == 100

    def test_returns_hours_simulated(self):
        stock = {"bread": 10}
        result = coarse_tick(stock, 3)
        assert result["hours_simulated"] == 3

    def test_custom_consumption_rate(self):
        stock = {"iron_bar": 100}
        coarse_tick(stock, 1, consumption_rate=0.10)
        assert stock["iron_bar"] == 90  # 100 * 0.9


class TestCatchUpLocation:
    def test_caps_at_72(self):
        stock = {"iron_bar": 1000}
        result = catch_up_location(stock, 200, cap=72)
        assert result["capped"] is True
        assert result["hours_simulated"] == 72

    def test_no_cap_needed(self):
        stock = {"iron_bar": 1000}
        result = catch_up_location(stock, 10, cap=72)
        assert result["capped"] is False
        assert result["hours_simulated"] == 10

    def test_stock_actually_decays(self):
        stock = {"bread": 100}
        catch_up_location(stock, 48)
        assert stock["bread"] < 100

    def test_custom_cap(self):
        stock = {"gold": 500}
        result = catch_up_location(stock, 100, cap=24)
        assert result["hours_simulated"] == 24
        assert result["capped"] is True

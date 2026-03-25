"""Tests for engine.world.economy — AC-23..AC-25."""

import pytest
from engine.world.economy import RECIPES, LocationStock, Recipe


class TestRecipes:
    def test_at_least_eight_recipes(self):
        assert len(RECIPES) >= 8

    def test_all_recipes_have_inputs(self):
        for key, r in RECIPES.items():
            assert len(r.inputs) > 0, f"{key} has no inputs"

    def test_recipe_output_qty_positive(self):
        for key, r in RECIPES.items():
            assert r.output_qty >= 1, f"{key} output_qty"

    def test_iron_bar_recipe(self):
        r = RECIPES["iron_bar"]
        assert r.inputs == {"iron_ore": 2, "coal": 1}
        assert r.output == "iron_bar"

    def test_healing_potion_needs_alchemy(self):
        r = RECIPES["healing_potion"]
        assert r.skill_required == "alchemy"


class TestLocationStock:
    def test_initial_stock_from_baseline(self):
        ls = LocationStock("town", baseline={"iron_bar": 50, "bread": 30})
        assert ls.get_stock("iron_bar") == 50

    def test_add_and_remove_stock(self):
        ls = LocationStock("town")
        ls.add_stock("ale", 20)
        assert ls.get_stock("ale") == 20
        removed = ls.remove_stock("ale", 8)
        assert removed == 8
        assert ls.get_stock("ale") == 12

    def test_remove_more_than_available(self):
        ls = LocationStock("town")
        ls.add_stock("bread", 5)
        removed = ls.remove_stock("bread", 100)
        assert removed == 5
        assert ls.get_stock("bread") == 0

    def test_produce_success(self):
        ls = LocationStock("smithy", baseline={
            "iron_ore": 10, "coal": 5,
        })
        ok = ls.produce("iron_bar")
        assert ok is True
        assert ls.get_stock("iron_ore") == 8
        assert ls.get_stock("coal") == 4
        assert ls.get_stock("iron_bar") == 1

    def test_produce_insufficient_inputs(self):
        ls = LocationStock("smithy", baseline={"iron_ore": 1, "coal": 0})
        ok = ls.produce("iron_bar")
        assert ok is False

    def test_produce_unknown_recipe_raises(self):
        ls = LocationStock("smithy")
        with pytest.raises(KeyError):
            ls.produce("unobtainium_bar")


class TestPricing:
    def test_normal_stock_modifier_is_one(self):
        ls = LocationStock("town", baseline={"iron_bar": 50})
        assert ls.get_price_modifier("iron_bar") == 1.0

    def test_scarcity_doubles_price(self):
        ls = LocationStock("town", baseline={"iron_bar": 100})
        ls.stock["iron_bar"] = 15  # 15 % of 100 → < 20 %
        assert ls.get_price_modifier("iron_bar") == 2.0

    def test_oversupply_reduces_price(self):
        ls = LocationStock("town", baseline={"iron_bar": 100})
        ls.stock["iron_bar"] = 200  # 200 % → > 150 %
        assert ls.get_price_modifier("iron_bar") == 0.7

    def test_zero_stock_max_price(self):
        ls = LocationStock("town", baseline={"bread": 50})
        ls.stock["bread"] = 0
        assert ls.get_price_modifier("bread") == 3.0

    def test_no_baseline_returns_one(self):
        ls = LocationStock("town")
        assert ls.get_price_modifier("mystery_item") == 1.0

    def test_effective_price_uses_recipe_base(self):
        ls = LocationStock("town", baseline={"iron_bar": 100})
        price = ls.get_effective_price("iron_bar")
        assert price == RECIPES["iron_bar"].base_price * 1.0

"""Tests for engine.world.crafting — Sprint 4 (FR-19..FR-24).

30+ tests covering all quality tiers, ingredient logic, workstation
requirements, skill checks, material quality stacking, all 5 disciplines,
and edge cases.
"""

import pytest

from engine.world.crafting import (
    ALL_RECIPES,
    DISCIPLINE_MAP,
    QUALITY_MODIFIERS,
    CraftingRecipe,
    CraftingSystem,
    CraftResult,
    Ingredient,
    Product,
    QualityTier,
    determine_quality,
    recipes_by_discipline,
)


# ── Quality tier determination ──────────────────────────────────────────

class TestDetermineQuality:
    """PRD 6.3 quality thresholds."""

    def test_ruined_fail_by_5(self):
        assert determine_quality(5, 10) == QualityTier.RUINED

    def test_ruined_fail_by_more(self):
        assert determine_quality(1, 15) == QualityTier.RUINED

    def test_shoddy_fail_by_4(self):
        assert determine_quality(6, 10) == QualityTier.SHODDY

    def test_shoddy_fail_by_1(self):
        assert determine_quality(9, 10) == QualityTier.SHODDY

    def test_normal_exact_meet(self):
        assert determine_quality(10, 10) == QualityTier.NORMAL

    def test_normal_beat_by_2(self):
        assert determine_quality(12, 10) == QualityTier.NORMAL

    def test_fine_beat_by_3(self):
        assert determine_quality(13, 10) == QualityTier.FINE

    def test_fine_beat_by_5(self):
        assert determine_quality(15, 10) == QualityTier.FINE

    def test_superior_beat_by_6(self):
        assert determine_quality(16, 10) == QualityTier.SUPERIOR

    def test_superior_beat_by_9(self):
        assert determine_quality(19, 10) == QualityTier.SUPERIOR

    def test_masterwork_beat_by_10(self):
        assert determine_quality(20, 10) == QualityTier.MASTERWORK

    def test_masterwork_beat_by_15(self):
        assert determine_quality(25, 10) == QualityTier.MASTERWORK


class TestQualityModifiers:
    def test_all_tiers_present(self):
        for tier in QualityTier:
            assert tier in QUALITY_MODIFIERS

    def test_ruined_zero_value(self):
        assert QUALITY_MODIFIERS[QualityTier.RUINED]["value_mult"] == 0.0

    def test_masterwork_best_stats(self):
        mw = QUALITY_MODIFIERS[QualityTier.MASTERWORK]
        assert mw["damage_mod"] == 3
        assert mw["armor_mod"] == 3
        assert mw["value_mult"] == 3.0

    def test_normal_no_modifier(self):
        n = QUALITY_MODIFIERS[QualityTier.NORMAL]
        assert n["damage_mod"] == 0
        assert n["armor_mod"] == 0
        assert n["value_mult"] == 1.0


# ── Recipe registry ─────────────────────────────────────────────────────

class TestRecipeRegistry:
    def test_at_least_40_recipes(self):
        assert len(ALL_RECIPES) >= 40

    def test_all_recipes_have_ingredients(self):
        for rid, r in ALL_RECIPES.items():
            assert len(r.ingredients) > 0, f"{rid} has no ingredients"

    def test_all_recipes_have_products(self):
        for rid, r in ALL_RECIPES.items():
            assert len(r.products) > 0, f"{rid} has no products"

    def test_all_recipes_positive_ap(self):
        for rid, r in ALL_RECIPES.items():
            assert r.ap_cost > 0, f"{rid} ap_cost must be positive"

    def test_all_recipes_positive_dc(self):
        for rid, r in ALL_RECIPES.items():
            assert r.skill_dc > 0, f"{rid} skill_dc must be positive"

    def test_discipline_map_complete(self):
        for rid in ALL_RECIPES:
            assert rid in DISCIPLINE_MAP

    def test_five_disciplines_exist(self):
        disciplines = set(DISCIPLINE_MAP.values())
        expected = {"smithing", "alchemy", "cooking", "carpentry", "leatherworking"}
        assert expected == disciplines


# ── Per-discipline recipe tests ─────────────────────────────────────────

class TestSmithingRecipes:
    def test_iron_bar_recipe(self):
        r = ALL_RECIPES["iron_bar"]
        assert r.workstation == "forge"
        assert r.skill == "smithing"
        assert r.skill_dc == 10

    def test_steel_sword_high_dc(self):
        r = ALL_RECIPES["steel_sword"]
        assert r.skill_dc == 16
        assert r.ap_cost == 15

    def test_plate_armor_is_hardest(self):
        r = ALL_RECIPES["plate_armor"]
        assert r.skill_dc >= 18

    def test_smithing_has_14_recipes(self):
        smithing = recipes_by_discipline("smithing")
        assert len(smithing) == 14


class TestAlchemyRecipes:
    def test_healing_potion(self):
        r = ALL_RECIPES["healing_potion"]
        assert r.workstation == "alchemy_bench"
        assert r.skill == "alchemy"
        ing_ids = [i.item_id for i in r.ingredients]
        assert "herb_heal" in ing_ids
        assert "glass_vial" in ing_ids

    def test_invisibility_potion_hardest(self):
        r = ALL_RECIPES["invisibility_potion"]
        assert r.skill_dc == 20

    def test_alchemy_has_10_recipes(self):
        alchemy = recipes_by_discipline("alchemy")
        assert len(alchemy) == 10


class TestCookingRecipes:
    def test_bread_easy(self):
        r = ALL_RECIPES["bread"]
        assert r.skill_dc == 8
        assert r.ap_cost == 3

    def test_stew_produces_two(self):
        r = ALL_RECIPES["stew"]
        assert r.products[0].quantity == 2

    def test_cooking_has_10_recipes(self):
        cooking = recipes_by_discipline("cooking")
        assert len(cooking) == 10


class TestCarpentryRecipes:
    def test_bow_recipe(self):
        r = ALL_RECIPES["bow"]
        assert r.workstation == "workbench"
        assert r.skill == "carpentry"

    def test_arrows_produce_five(self):
        r = ALL_RECIPES["arrows"]
        assert r.products[0].quantity == 5

    def test_carpentry_has_12_recipes(self):
        carpentry = recipes_by_discipline("carpentry")
        assert len(carpentry) == 12


class TestLeatherworkingRecipes:
    def test_leather_from_hide(self):
        r = ALL_RECIPES["leather"]
        ing_ids = [i.item_id for i in r.ingredients]
        assert "hide" in ing_ids
        assert "tanning_agent" in ing_ids

    def test_leather_armor_needs_sinew(self):
        r = ALL_RECIPES["leather_armor"]
        ing_ids = [i.item_id for i in r.ingredients]
        assert "sinew" in ing_ids

    def test_leatherworking_has_9_recipes(self):
        lw = recipes_by_discipline("leatherworking")
        assert len(lw) == 9


# ── CraftingSystem logic ────────────────────────────────────────────────

class TestCheckIngredients:
    def test_sufficient_ingredients(self):
        cs = CraftingSystem()
        recipe = ALL_RECIPES["iron_bar"]
        inv = {"iron_ore": 5, "coal": 3}
        assert cs.check_ingredients(recipe, inv) is True

    def test_missing_ingredient(self):
        cs = CraftingSystem()
        recipe = ALL_RECIPES["iron_bar"]
        inv = {"iron_ore": 1, "coal": 3}  # need 2 iron_ore
        assert cs.check_ingredients(recipe, inv) is False

    def test_zero_stock(self):
        cs = CraftingSystem()
        recipe = ALL_RECIPES["iron_bar"]
        inv = {}
        assert cs.check_ingredients(recipe, inv) is False


class TestConsumeIngredients:
    def test_consumes_correct_amounts(self):
        cs = CraftingSystem()
        recipe = ALL_RECIPES["iron_bar"]
        inv = {"iron_ore": 5, "coal": 3}
        cs.consume_ingredients(recipe, inv)
        assert inv["iron_ore"] == 3
        assert inv["coal"] == 2

    def test_raises_on_insufficient(self):
        cs = CraftingSystem()
        recipe = ALL_RECIPES["iron_bar"]
        inv = {"iron_ore": 1, "coal": 0}
        with pytest.raises(ValueError):
            cs.consume_ingredients(recipe, inv)


class TestAttemptCraft:
    def setup_method(self):
        self.cs = CraftingSystem()

    def _inv_for(self, recipe_id: str, multiplier: int = 1) -> dict:
        """Build an inventory that exactly satisfies a recipe *multiplier* times."""
        recipe = ALL_RECIPES[recipe_id]
        inv: dict = {}
        for ing in recipe.ingredients:
            inv[ing.item_id] = ing.quantity * multiplier
        return inv

    # --- success path ---
    def test_normal_quality_craft(self):
        recipe = ALL_RECIPES["bread"]
        inv = self._inv_for("bread")
        result = self.cs.attempt_craft(roll=8, recipe=recipe, inventory=inv)
        assert result.success is True
        assert result.quality == QualityTier.NORMAL
        assert ("bread", 2) in result.products
        assert inv.get("bread", 0) == 2

    def test_fine_quality_craft(self):
        recipe = ALL_RECIPES["iron_sword"]
        inv = self._inv_for("iron_sword")
        result = self.cs.attempt_craft(roll=15, recipe=recipe, inventory=inv)
        assert result.success is True
        assert result.quality == QualityTier.FINE

    def test_masterwork_craft(self):
        recipe = ALL_RECIPES["steel_sword"]
        inv = self._inv_for("steel_sword")
        result = self.cs.attempt_craft(roll=26, recipe=recipe, inventory=inv)
        assert result.success is True
        assert result.quality == QualityTier.MASTERWORK
        assert result.xp_gained == ALL_RECIPES["steel_sword"].xp_reward * 2

    # --- failure path ---
    def test_ruined_craft_consumes_ingredients(self):
        recipe = ALL_RECIPES["iron_sword"]
        inv = self._inv_for("iron_sword")
        result = self.cs.attempt_craft(roll=2, recipe=recipe, inventory=inv)
        assert result.success is False
        assert result.quality == QualityTier.RUINED
        # ingredients consumed
        assert inv.get("iron_bar", 0) == 0

    def test_ruined_gives_failure_product(self):
        recipe = ALL_RECIPES["iron_sword"]
        inv = self._inv_for("iron_sword")
        result = self.cs.attempt_craft(roll=2, recipe=recipe, inventory=inv)
        assert ("ruined_blade", 1) in result.products
        assert inv.get("ruined_blade", 0) == 1

    def test_shoddy_still_succeeds(self):
        recipe = ALL_RECIPES["bread"]
        inv = self._inv_for("bread")
        result = self.cs.attempt_craft(roll=7, recipe=recipe, inventory=inv)
        assert result.success is True
        assert result.quality == QualityTier.SHODDY
        assert ("bread", 2) in result.products

    # --- pre-flight failures ---
    def test_missing_workstation(self):
        recipe = ALL_RECIPES["iron_bar"]
        inv = self._inv_for("iron_bar")
        result = self.cs.attempt_craft(
            roll=15, recipe=recipe, inventory=inv, workstation_ok=False
        )
        assert result.success is False
        assert "forge" in result.narrative
        # ingredients NOT consumed
        assert inv["iron_ore"] == 2

    def test_missing_ingredients_no_consumption(self):
        recipe = ALL_RECIPES["plate_armor"]
        inv = {"steel_bar": 1}  # need 4
        result = self.cs.attempt_craft(roll=20, recipe=recipe, inventory=inv)
        assert result.success is False
        assert inv["steel_bar"] == 1  # untouched

    # --- xp scaling ---
    def test_xp_bonus_for_superior(self):
        recipe = ALL_RECIPES["healing_potion"]
        inv = self._inv_for("healing_potion")
        result = self.cs.attempt_craft(roll=20, recipe=recipe, inventory=inv)
        assert result.quality == QualityTier.SUPERIOR
        assert result.xp_gained == int(recipe.xp_reward * 1.5)

    def test_ruined_partial_xp(self):
        recipe = ALL_RECIPES["iron_bar"]
        inv = self._inv_for("iron_bar")
        result = self.cs.attempt_craft(roll=1, recipe=recipe, inventory=inv)
        assert result.xp_gained == recipe.xp_reward // 4


# ── Material quality stacking ───────────────────────────────────────────

class TestMaterialQualityStacking:
    """Quality modifiers should stack with material multipliers."""

    def test_steel_sword_fine_damage_boost(self):
        """A Fine steel sword gets +1 damage on top of steel's 1.3x base."""
        from engine.world.materials import MATERIALS
        steel = MATERIALS["steel"]
        quality_mod = QUALITY_MODIFIERS[QualityTier.FINE]
        base_damage = 8  # hypothetical base sword damage
        effective = round(base_damage * steel.damage_mult + quality_mod["damage_mod"], 2)
        # 8 * 1.3 + 1 = 11.4
        assert effective == 11.4

    def test_iron_masterwork_value(self):
        from engine.world.materials import MATERIALS
        iron = MATERIALS["iron"]
        mw = QUALITY_MODIFIERS[QualityTier.MASTERWORK]
        base_value = 35.0
        effective = round(base_value * iron.value_mult * mw["value_mult"], 2)
        assert effective == 105.0  # 35 * 1.0 * 3.0

    def test_shoddy_reduces_armor(self):
        from engine.world.materials import MATERIALS
        iron = MATERIALS["iron"]
        shoddy = QUALITY_MODIFIERS[QualityTier.SHODDY]
        base_armor = 5
        effective = round(base_armor * iron.armor_mult + shoddy["armor_mod"], 2)
        assert effective == 3.0  # 5 * 1.0 - 2


# ── Workstation detection ───────────────────────────────────────────────

class TestFindNearbyWorkstation:
    def test_any_workstation_always_ok(self):
        result = CraftingSystem.find_nearby_workstation(None, (0, 0), "any")
        assert result is True

    def test_finds_matching_workstation(self):
        class FakeEntity:
            def __init__(self, name, etype):
                self.name = name
                self.entity_type = etype

        class FakeSpatial:
            def in_radius(self, x, y, r):
                return [FakeEntity("Town Forge", "FURNITURE")]

        result = CraftingSystem.find_nearby_workstation(
            FakeSpatial(), (5, 5), "forge"
        )
        assert result is not None
        assert result.name == "Town Forge"

    def test_no_matching_workstation(self):
        class FakeSpatial:
            def in_radius(self, x, y, r):
                return []

        result = CraftingSystem.find_nearby_workstation(
            FakeSpatial(), (0, 0), "forge"
        )
        assert result is None


# ── Edge cases ──────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_recipe_with_no_failure_result(self):
        """Recipes where failure_result is None should produce nothing on ruin."""
        cs = CraftingSystem()
        recipe = ALL_RECIPES["iron_nails"]
        inv = {"iron_bar": 1}
        result = cs.attempt_craft(roll=1, recipe=recipe, inventory=inv)
        assert result.success is False
        assert result.products == []

    def test_crafting_twice_needs_double_ingredients(self):
        cs = CraftingSystem()
        recipe = ALL_RECIPES["bread"]
        inv = {"flour": 4, "water": 2}
        r1 = cs.attempt_craft(roll=10, recipe=recipe, inventory=inv)
        assert r1.success is True
        r2 = cs.attempt_craft(roll=10, recipe=recipe, inventory=inv)
        assert r2.success is True
        # Third attempt should fail
        r3 = cs.attempt_craft(roll=10, recipe=recipe, inventory=inv)
        assert r3.success is False

    def test_narrative_contains_recipe_name(self):
        cs = CraftingSystem()
        recipe = ALL_RECIPES["healing_potion"]
        inv = {"herb_heal": 1, "water": 1, "glass_vial": 1}
        result = cs.attempt_craft(roll=12, recipe=recipe, inventory=inv)
        assert "Healing Potion" in result.narrative

    def test_dataclass_frozen_recipe(self):
        r = ALL_RECIPES["bread"]
        with pytest.raises(AttributeError):
            r.name = "Burnt Bread"  # type: ignore[misc]

    def test_ingredient_dataclass_frozen(self):
        ing = Ingredient(item_id="test", quantity=1)
        with pytest.raises(AttributeError):
            ing.quantity = 5  # type: ignore[misc]

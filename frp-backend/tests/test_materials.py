"""Tests for engine.world.materials — AC-11..AC-13."""

import pytest
from engine.world.materials import (
    MATERIALS,
    MaterialProperties,
    apply_material,
    get_item_display_name,
)


class TestMaterialsDict:
    def test_has_all_ten_materials(self):
        expected = {"iron", "steel", "bronze", "wood", "leather",
                    "mithril", "silver", "gold", "bone", "obsidian"}
        assert set(MATERIALS.keys()) == expected

    def test_material_is_frozen_dataclass(self):
        mat = MATERIALS["iron"]
        assert isinstance(mat, MaterialProperties)
        with pytest.raises(AttributeError):
            mat.density = 999

    def test_iron_is_baseline(self):
        iron = MATERIALS["iron"]
        assert iron.density == 1.0
        assert iron.damage_mult == 1.0
        assert iron.armor_mult == 1.0
        assert iron.value_mult == 1.0

    def test_mithril_is_light_and_strong(self):
        m = MATERIALS["mithril"]
        assert m.density < MATERIALS["iron"].density
        assert m.damage_mult > MATERIALS["iron"].damage_mult
        assert m.armor_mult > MATERIALS["iron"].armor_mult

    def test_gold_is_heavy_and_weak(self):
        g = MATERIALS["gold"]
        assert g.density > 2.0
        assert g.damage_mult < 1.0

    def test_all_materials_have_positive_values(self):
        for name, mat in MATERIALS.items():
            assert mat.density > 0, f"{name} density"
            assert mat.hardness > 0, f"{name} hardness"
            assert mat.value_mult > 0, f"{name} value_mult"
            assert mat.damage_mult > 0, f"{name} damage_mult"
            assert mat.armor_mult > 0, f"{name} armor_mult"


class TestApplyMaterial:
    def test_iron_no_change(self):
        result = apply_material(10, 5, 100, 8, "iron")
        assert result["damage"] == 10.0
        assert result["weight"] == 5.0
        assert result["value"] == 100.0
        assert result["armor"] == 8.0
        assert result["material"] == "iron"

    def test_steel_increases_damage(self):
        result = apply_material(10, 5, 100, 8, "steel")
        assert result["damage"] > 10.0
        assert result["armor"] > 8.0

    def test_wood_reduces_weight(self):
        result = apply_material(10, 5, 100, 8, "wood")
        assert result["weight"] < 5.0

    def test_unknown_material_raises(self):
        with pytest.raises(KeyError):
            apply_material(10, 5, 100, 8, "adamantium")

    def test_case_insensitive(self):
        result = apply_material(10, 5, 100, 8, "Steel")
        assert result["material"] == "steel"

    def test_values_are_rounded(self):
        result = apply_material(7, 3, 55, 4, "obsidian")
        for key in ("damage", "weight", "value", "armor"):
            # Should have at most 2 decimal places.
            assert result[key] == round(result[key], 2)


class TestDisplayName:
    def test_basic(self):
        assert get_item_display_name("longsword", "steel") == "Steel Longsword"

    def test_multi_word_item(self):
        assert get_item_display_name("war hammer", "iron") == "Iron War Hammer"

    def test_lowercase_material(self):
        assert get_item_display_name("dagger", "mithril") == "Mithril Dagger"

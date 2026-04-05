"""Class data normalization and progression coverage tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

ALL_CLASS_IDS = {"warrior", "rogue", "mage", "priest", "ranger", "paladin", "bard", "druid", "monk", "warlock", "sorcerer"}
VALID_STATS = {"MIG", "AGI", "END", "MND", "INS", "PRE"}
ABILITY_REQUIRED_KEYS = {"name", "description", "passive", "required_level", "class_name", "cost"}


@pytest.fixture(scope="module")
def classes():
    return json.loads((DATA_DIR / "classes.json").read_text(encoding="utf-8"))["classes"]


@pytest.fixture(scope="module")
def progression():
    return json.loads((DATA_DIR / "progression.json").read_text(encoding="utf-8"))["progression"]


# ── Class ID normalization ───────────────────────────────────────────

class TestClassIdNormalization:
    def test_all_class_ids_are_lowercase(self, classes):
        for class_id in classes:
            assert class_id == class_id.lower(), (
                f"Class ID {class_id!r} is not lowercase"
            )

    def test_all_expected_class_ids_present(self, classes):
        missing = ALL_CLASS_IDS - set(classes.keys())
        assert not missing, f"Missing class IDs: {sorted(missing)}"

    def test_class_names_are_title_case(self, classes):
        for class_id, data in classes.items():
            name = data.get("name", "")
            assert name and name[0].isupper(), (
                f"Class {class_id} name {name!r} should be title case"
            )

    def test_class_ids_match_count(self, classes):
        assert len(classes) == 11, f"Expected 11 classes, got {len(classes)}"


# ── Progression table coverage ───────────────────────────────────────

class TestProgressionTableCoverage:
    def test_hp_per_level_covers_all_classes(self, progression):
        hp = progression["hp_per_level"]
        missing = ALL_CLASS_IDS - set(hp.keys())
        assert not missing, f"hp_per_level missing: {sorted(missing)}"

    def test_sp_per_level_covers_all_classes(self, progression):
        sp = progression["sp_per_level"]
        missing = ALL_CLASS_IDS - set(sp.keys())
        assert not missing, f"sp_per_level missing: {sorted(missing)}"

    def test_stat_bonus_covers_all_classes(self, progression):
        bonuses = progression["stat_bonus_by_class"]
        missing = ALL_CLASS_IDS - set(bonuses.keys())
        assert not missing, f"stat_bonus_by_class missing: {sorted(missing)}"

    def test_stat_bonuses_are_valid_stats(self, progression):
        for cls, stat in progression["stat_bonus_by_class"].items():
            if cls == "null":
                continue
            assert stat in VALID_STATS, (
                f"stat_bonus_by_class[{cls}] = {stat!r} is not a valid stat"
            )

    def test_hp_values_are_positive(self, progression):
        for cls, hp in progression["hp_per_level"].items():
            assert isinstance(hp, int) and hp > 0, (
                f"hp_per_level[{cls}] = {hp} is not a positive integer"
            )

    def test_sp_values_are_non_negative(self, progression):
        for cls, sp in progression["sp_per_level"].items():
            assert isinstance(sp, int) and sp >= 0, (
                f"sp_per_level[{cls}] = {sp} is not a non-negative integer"
            )

    def test_locked_hp_values(self, progression):
        hp = progression["hp_per_level"]
        assert hp["ranger"] == 8
        assert hp["paladin"] == 10
        assert hp["bard"] == 8

    def test_locked_sp_values(self, progression):
        sp = progression["sp_per_level"]
        assert sp["ranger"] == 0
        assert sp["paladin"] == 2
        assert sp["bard"] == 3

    def test_locked_stat_bonuses(self, progression):
        bonuses = progression["stat_bonus_by_class"]
        assert bonuses["ranger"] == "AGI"
        assert bonuses["paladin"] == "PRE"
        assert bonuses["bard"] == "PRE"


# ── Class abilities coverage ─────────────────────────────────────────

class TestClassAbilitiesCoverage:
    def test_class_abilities_cover_all_classes(self, progression):
        abilities = progression["class_abilities"]
        missing = ALL_CLASS_IDS - set(abilities.keys())
        assert not missing, f"class_abilities missing: {sorted(missing)}"

    def test_each_class_has_at_least_5_abilities(self, progression):
        for cls, ab_list in progression["class_abilities"].items():
            assert len(ab_list) >= 5, (
                f"class_abilities[{cls}] has {len(ab_list)} abilities, expected at least 5"
            )

    def test_abilities_have_required_schema(self, progression):
        for cls, ab_list in progression["class_abilities"].items():
            for i, ab in enumerate(ab_list):
                missing = ABILITY_REQUIRED_KEYS - set(ab.keys())
                assert not missing, (
                    f"class_abilities[{cls}][{i}] missing fields: {sorted(missing)}"
                )

    def test_ability_class_names_are_lowercase(self, progression):
        for cls, ab_list in progression["class_abilities"].items():
            for ab in ab_list:
                assert ab["class_name"] == ab["class_name"].lower(), (
                    f"Ability {ab['name']!r} has non-lowercase class_name {ab['class_name']!r}"
                )

    def test_ability_class_names_match_parent_key(self, progression):
        for cls, ab_list in progression["class_abilities"].items():
            for ab in ab_list:
                assert ab["class_name"] == cls, (
                    f"Ability {ab['name']!r} class_name={ab['class_name']!r} "
                    f"does not match parent key {cls!r}"
                )

    def test_abilities_have_ascending_levels(self, progression):
        for cls, ab_list in progression["class_abilities"].items():
            levels = [ab["required_level"] for ab in ab_list]
            assert levels == sorted(levels), (
                f"class_abilities[{cls}] levels are not ascending: {levels}"
            )

    def test_ability_levels_cover_1_through_5_at_minimum(self, progression):
        for cls, ab_list in progression["class_abilities"].items():
            levels = {ab["required_level"] for ab in ab_list}
            assert {1, 2, 3, 4, 5} <= levels, (
                f"class_abilities[{cls}] does not cover levels 1-5: {sorted(levels)}"
            )

    def test_ability_costs_are_non_negative(self, progression):
        for cls, ab_list in progression["class_abilities"].items():
            for ab in ab_list:
                assert isinstance(ab["cost"], int) and ab["cost"] >= 0, (
                    f"Ability {ab['name']!r} has invalid cost {ab['cost']}"
                )

    def test_passive_is_boolean(self, progression):
        for cls, ab_list in progression["class_abilities"].items():
            for ab in ab_list:
                assert isinstance(ab["passive"], bool), (
                    f"Ability {ab['name']!r} passive is not boolean: {ab['passive']!r}"
                )

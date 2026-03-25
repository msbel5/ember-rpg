"""
Tests for the skill check system.
Covers: d20 rolls, modifiers, DC descriptions, criticals, contested checks, edge cases.
"""

import random

import pytest

from engine.world.skill_checks import (
    ABILITIES,
    SkillCheckResult,
    ability_modifier,
    contested_check,
    get_dc_description,
    roll_check,
)


# ── ability_modifier ─────────────────────────────────────────────────

class TestAbilityModifier:
    def test_score_10_gives_zero(self):
        assert ability_modifier(10) == 0

    def test_score_11_gives_zero(self):
        assert ability_modifier(11) == 0

    def test_score_12_gives_plus_one(self):
        assert ability_modifier(12) == 1

    def test_score_14_gives_plus_two(self):
        assert ability_modifier(14) == 2

    def test_score_20_gives_plus_five(self):
        assert ability_modifier(20) == 5

    def test_score_8_gives_minus_one(self):
        assert ability_modifier(8) == -1

    def test_score_1_gives_minus_four(self):
        # (1-10)//2 = -9//2 = -5  (Python floor division)
        assert ability_modifier(1) == -5

    def test_score_30_gives_plus_ten(self):
        assert ability_modifier(30) == 10

    def test_score_0_gives_minus_five(self):
        assert ability_modifier(0) == -5


# ── get_dc_description ───────────────────────────────────────────────

class TestDCDescription:
    def test_trivial(self):
        assert get_dc_description(3) == "trivial"
        assert get_dc_description(5) == "trivial"

    def test_easy(self):
        assert get_dc_description(6) == "easy"
        assert get_dc_description(8) == "easy"

    def test_medium(self):
        assert get_dc_description(10) == "medium"
        assert get_dc_description(12) == "medium"

    def test_hard(self):
        assert get_dc_description(14) == "hard"
        assert get_dc_description(15) == "hard"

    def test_very_hard(self):
        assert get_dc_description(18) == "very hard"
        assert get_dc_description(20) == "very hard"

    def test_nearly_impossible(self):
        assert get_dc_description(25) == "nearly impossible"
        assert get_dc_description(30) == "nearly impossible"


# ── ABILITIES dict ───────────────────────────────────────────────────

class TestAbilities:
    def test_all_six_present(self):
        assert set(ABILITIES.keys()) == {"MIG", "AGI", "END", "MND", "INS", "PRE"}

    def test_descriptions_are_strings(self):
        for desc in ABILITIES.values():
            assert isinstance(desc, str) and len(desc) > 5


# ── roll_check ───────────────────────────────────────────────────────

class TestRollCheck:
    def test_deterministic_with_seeded_rng(self):
        rng = random.Random(42)
        result = roll_check(14, 12, _rng=rng)
        assert isinstance(result, SkillCheckResult)
        assert 1 <= result.roll <= 20
        assert result.modifier == ability_modifier(14)
        assert result.total == result.roll + result.modifier

    def test_success_when_total_meets_dc(self):
        """Force a roll of 10 with score 14 (mod +2) vs DC 12 => total 12, success."""
        rng = _rigged_rng(10)
        result = roll_check(14, 12, _rng=rng)
        assert result.total == 12
        assert result.success is True
        assert result.margin == 0

    def test_failure_when_total_below_dc(self):
        rng = _rigged_rng(5)
        result = roll_check(10, 15, _rng=rng)
        assert result.total == 5  # roll 5 + mod 0
        assert result.success is False
        assert result.margin == -10

    def test_natural_20_always_succeeds(self):
        rng = _rigged_rng(20)
        result = roll_check(1, 30, _rng=rng)  # mod -5, total 15 < DC 30
        assert result.critical == "success"
        assert result.success is True

    def test_natural_1_always_fails(self):
        rng = _rigged_rng(1)
        result = roll_check(30, 1, _rng=rng)  # mod +10, total 11 > DC 1
        assert result.critical == "failure"
        assert result.success is False

    def test_no_critical_on_normal_roll(self):
        rng = _rigged_rng(10)
        result = roll_check(10, 10, _rng=rng)
        assert result.critical is None

    def test_margin_positive_on_success(self):
        rng = _rigged_rng(18)
        result = roll_check(16, 10, _rng=rng)  # total = 18+3 = 21, margin = 11
        assert result.margin == 11
        assert result.success is True

    def test_margin_negative_on_failure(self):
        rng = _rigged_rng(3)
        result = roll_check(8, 15, _rng=rng)  # total = 3+(-1) = 2, margin = -13
        assert result.margin == -13
        assert result.success is False

    def test_very_high_score(self):
        rng = _rigged_rng(10)
        result = roll_check(30, 20, _rng=rng)  # mod +10, total 20
        assert result.success is True

    def test_very_low_score(self):
        rng = _rigged_rng(10)
        result = roll_check(1, 5, _rng=rng)  # mod -5, total 5
        assert result.success is True

    def test_result_is_frozen(self):
        rng = _rigged_rng(10)
        result = roll_check(10, 10, _rng=rng)
        with pytest.raises(AttributeError):
            result.roll = 5  # type: ignore[misc]


# ── contested_check ──────────────────────────────────────────────────

class TestContestedCheck:
    def test_higher_total_wins(self):
        rng = _rigged_rng(15, 5)
        ra, rb, winner = contested_check(14, 14, _rng=rng)
        assert winner == "a"
        assert ra.success is True
        assert rb.success is False

    def test_tie_when_equal(self):
        rng = _rigged_rng(10, 10)
        ra, rb, winner = contested_check(14, 14, _rng=rng)
        assert winner == "tie"
        assert ra.success is False  # neither wins on tie
        assert rb.success is False

    def test_b_wins_when_higher(self):
        rng = _rigged_rng(3, 18)
        ra, rb, winner = contested_check(10, 10, _rng=rng)
        assert winner == "b"

    def test_margin_reflects_difference(self):
        rng = _rigged_rng(15, 10)
        ra, rb, _ = contested_check(12, 12, _rng=rng)
        # Both have mod +1, so totals are 16 and 11
        assert ra.margin == 5
        assert rb.margin == -5

    def test_different_scores(self):
        rng = _rigged_rng(10, 10)
        ra, rb, winner = contested_check(16, 10, _rng=rng)
        # A: 10+3=13, B: 10+0=10
        assert winner == "a"

    def test_critical_tracked_in_contest(self):
        rng = _rigged_rng(20, 1)
        ra, rb, _ = contested_check(10, 10, _rng=rng)
        assert ra.critical == "success"
        assert rb.critical == "failure"


# ── Helpers ──────────────────────────────────────────────────────────

def _rigged_rng(*values: int) -> random.Random:
    """Return a Random whose randint always returns from a sequence of fixed values."""
    rng = random.Random()
    call_iter = iter(values)

    def _fixed_randint(a: int, b: int) -> int:
        return next(call_iter)

    rng.randint = _fixed_randint  # type: ignore[assignment]
    return rng

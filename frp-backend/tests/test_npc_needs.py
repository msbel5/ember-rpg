"""Tests for NPCNeeds (FR-05..FR-09, AC-05..AC-07)."""
import pytest

from engine.world.npc_needs import NPCNeeds, DECAY_RATES


class TestNPCNeedsDecay:
    """AC-05: needs decay at correct rates."""

    def test_default_values(self):
        needs = NPCNeeds()
        assert needs.safety == 80.0
        assert needs.sustenance == 80.0

    def test_tick_1_hour_decay(self):
        needs = NPCNeeds(safety=80, commerce=80, social=80, sustenance=80, duty=80)
        needs.tick(hours=1)
        assert needs.sustenance == 78.0  # -2/hr
        assert needs.social == 79.0      # -1/hr
        assert needs.safety == 79.5      # -0.5/hr
        assert needs.duty == 79.0        # -1/hr
        assert needs.commerce == 79.5    # -0.5/hr

    def test_tick_8_hour_decay(self):
        needs = NPCNeeds(sustenance=80)
        needs.tick(hours=8)
        assert needs.sustenance == 64.0  # 80 - 2*8

    def test_decay_floors_at_zero(self):
        needs = NPCNeeds(sustenance=3)
        needs.tick(hours=5)  # would be 3 - 10 = -7
        assert needs.sustenance == 0.0

    def test_decay_rates_match_spec(self):
        assert DECAY_RATES["sustenance"] == 2.0
        assert DECAY_RATES["social"] == 1.0
        assert DECAY_RATES["safety"] == 0.5
        assert DECAY_RATES["duty"] == 1.0
        assert DECAY_RATES["commerce"] == 0.5


class TestNPCNeedsSatisfy:
    """AC-06: satisfy clamps to [0, 100]."""

    def test_satisfy_increases(self):
        needs = NPCNeeds(sustenance=30)
        needs.satisfy("sustenance", 40)
        assert needs.sustenance == 70.0

    def test_satisfy_clamp_upper(self):
        needs = NPCNeeds(sustenance=90)
        needs.satisfy("sustenance", 50)
        assert needs.sustenance == 100.0

    def test_satisfy_unknown_need_raises(self):
        needs = NPCNeeds()
        with pytest.raises(ValueError, match="Unknown need"):
            needs.satisfy("happiness", 10)


class TestNPCNeedsEmotionalState:
    """AC-07: emotional state thresholds."""

    def test_content_all_above_60(self):
        needs = NPCNeeds(safety=70, commerce=70, social=70, sustenance=70, duty=70)
        assert needs.emotional_state() == "content"

    def test_uneasy_default(self):
        needs = NPCNeeds(safety=50, commerce=50, social=50, sustenance=50, duty=50)
        assert needs.emotional_state() == "uneasy"

    def test_distressed_any_below_20(self):
        needs = NPCNeeds(safety=70, commerce=70, social=15, sustenance=70, duty=70)
        assert needs.emotional_state() == "distressed"

    def test_desperate_any_below_10(self):
        needs = NPCNeeds(safety=70, commerce=70, social=70, sustenance=5, duty=70)
        assert needs.emotional_state() == "desperate"

    def test_terrified_safety_below_10(self):
        needs = NPCNeeds(safety=5)
        assert needs.emotional_state() == "terrified"

    def test_terrified_takes_priority_over_desperate(self):
        """safety<10 should be terrified even if other needs also < 10."""
        needs = NPCNeeds(safety=5, sustenance=5)
        assert needs.emotional_state() == "terrified"


class TestBehaviorModifiers:

    def test_default_modifiers(self):
        needs = NPCNeeds()  # all at 80
        mods = needs.behavior_modifiers()
        assert mods["will_talk"] is True
        assert mods["will_trade"] is True
        assert mods["price_mult"] == pytest.approx(1.1, abs=0.01)

    def test_low_safety_blocks_talk_and_trade(self):
        needs = NPCNeeds(safety=10)
        mods = needs.behavior_modifiers()
        assert mods["will_talk"] is False
        assert mods["will_trade"] is False

    def test_low_duty_high_bribe(self):
        needs = NPCNeeds(duty=0)
        mods = needs.behavior_modifiers()
        assert mods["bribe_susceptibility"] == 1.0

    def test_high_duty_low_bribe(self):
        needs = NPCNeeds(duty=100)
        mods = needs.behavior_modifiers()
        assert mods["bribe_susceptibility"] == 0.0


class TestSerialization:

    def test_round_trip(self):
        original = NPCNeeds(safety=42, commerce=13, social=99, sustenance=0, duty=55)
        restored = NPCNeeds.from_dict(original.to_dict())
        assert restored.safety == original.safety
        assert restored.commerce == original.commerce
        assert restored.social == original.social
        assert restored.sustenance == original.sustenance
        assert restored.duty == original.duty

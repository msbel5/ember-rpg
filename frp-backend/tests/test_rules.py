"""
Ember RPG - Core Engine
Rules system tests (dice rolling)
"""
import pytest
from engine.core.rules import roll_dice


class TestDiceRolling:
    """Test dice rolling mechanics."""
    
    @pytest.mark.parametrize("dice_str,min_val,max_val", [
        ("1d6", 1, 6),
        ("2d10", 2, 20),
        ("1d6+2", 3, 8),
        ("3d6+5", 8, 23),
        ("1d20-1", 0, 19),
        ("1d20", 1, 20),
        ("4d6", 4, 24),
        ("1d10+10", 11, 20),
    ])
    def test_dice_ranges(self, dice_str, min_val, max_val):
        """Test dice rolls stay within expected ranges."""
        for _ in range(100):  # Test multiple times
            result = roll_dice(dice_str)
            assert min_val <= result <= max_val, \
                f"{dice_str} rolled {result}, expected {min_val}-{max_val}"
    
    def test_consistent_results(self):
        """Test that same notation produces consistent range."""
        results = [roll_dice("1d6") for _ in range(100)]
        assert all(1 <= r <= 6 for r in results)
        assert min(results) == 1  # Should hit min at least once
        assert max(results) == 6  # Should hit max at least once
    
    def test_modifier_addition(self):
        """Test positive modifiers increase result."""
        # Roll 1d6+10 should always be 11-16
        for _ in range(50):
            result = roll_dice("1d6+10")
            assert 11 <= result <= 16
    
    def test_modifier_subtraction(self):
        """Test negative modifiers decrease result."""
        # Roll 1d20-5 should be -4 to 15
        for _ in range(50):
            result = roll_dice("1d20-5")
            assert -4 <= result <= 15
    
    def test_multiple_dice(self):
        """Test rolling multiple dice sums correctly."""
        # 3d6 should be 3-18
        results = [roll_dice("3d6") for _ in range(100)]
        assert all(3 <= r <= 18 for r in results)
    
    def test_invalid_notation(self):
        """Test that invalid dice strings raise errors."""
        with pytest.raises(ValueError, match="Invalid dice notation"):
            roll_dice("invalid")
        
        with pytest.raises(ValueError, match="Invalid dice notation"):
            roll_dice("d6")  # Missing num_dice
        
        with pytest.raises(ValueError, match="Invalid dice notation"):
            roll_dice("2d")  # Missing die_size
        
        with pytest.raises(ValueError, match="Invalid dice notation"):
            roll_dice("abc")
    
    def test_edge_cases(self):
        """Test edge cases."""
        # 1d2 (coin flip)
        results = [roll_dice("1d2") for _ in range(50)]
        assert all(r in [1, 2] for r in results)
        
        # Large dice
        result = roll_dice("1d100")
        assert 1 <= result <= 100
        
        # Many dice
        result = roll_dice("10d6")
        assert 10 <= result <= 60

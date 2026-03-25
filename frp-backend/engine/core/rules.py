"""
Ember RPG - Core Engine
Dice rolling and rule mechanics
"""
import re
import random


def roll_dice(dice_str: str) -> int:
    """
    Roll dice from string notation.
    
    Supports:
    - Simple: "1d6" → roll 1d6
    - Multiple: "2d10" → roll 2d10, sum
    - Modifier: "1d6+2" → roll 1d6, add 2
    - Complex: "3d6+5" → roll 3d6, add 5
    - Negative: "1d20-1" → roll 1d20, subtract 1
    
    Args:
        dice_str: Dice notation (e.g., "1d6", "2d10+3", "1d20-1")
    
    Returns:
        Total roll result
    
    Raises:
        ValueError: If dice string is malformed
    
    Examples:
        >>> roll_dice("1d6")  # Returns 1-6
        >>> roll_dice("2d10+3")  # Returns 5-23
        >>> roll_dice("3d6")  # Returns 3-18
    """
    # Parse dice string: NdX+M or NdX-M or NdX
    match = re.match(r'(\d+)d(\d+)(([+\-])(\d+))?', dice_str.strip())
    if not match:
        raise ValueError(f"Invalid dice notation: {dice_str}")
    
    num_dice = int(match.group(1))
    die_size = int(match.group(2))
    modifier = 0
    
    if match.group(3):  # Has modifier
        sign = match.group(4)
        mod_value = int(match.group(5))
        modifier = mod_value if sign == '+' else -mod_value
    
    # Validate
    if num_dice < 1:
        raise ValueError(f"Number of dice must be ≥ 1: {dice_str}")
    if die_size < 2:
        raise ValueError(f"Die size must be ≥ 2: {dice_str}")
    
    # Roll dice
    total = sum(random.randint(1, die_size) for _ in range(num_dice))
    return total + modifier

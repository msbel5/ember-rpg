"""
Ember RPG - Core Engine
Leveling & Progression System
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from engine.data_loader import (
    get_class_abilities,
    get_hp_per_level,
    get_sp_per_level,
    get_stat_bonus_by_class,
    get_xp_thresholds,
)

if TYPE_CHECKING:
    from engine.core.character import Character


@dataclass
class ClassAbility:
    """
    A class ability unlocked at a specific level.
    
    Attributes:
        name: Ability name
        description: Flavor + mechanical description
        passive: True if always active, False if activated
        required_level: Level at which this is unlocked
        class_name: Which class grants this ability
        cost: AP cost if active (0 = free / passive)
    """
    name: str
    description: str
    passive: bool
    required_level: int
    class_name: str
    cost: int = 0


@dataclass
class LevelUpResult:
    """
    Result returned when a character levels up.
    
    Attributes:
        old_level: Level before gaining XP
        new_level: Level after gaining XP
        new_abilities: Abilities unlocked at new level(s)
        stat_bonus: Stat name that received +1 (None if odd level)
        hp_increase: HP added to max_hp
        sp_increase: Spell points added to max_spell_points
    """
    old_level: int
    new_level: int
    new_abilities: List[ClassAbility]
    stat_bonus: Optional[str]
    hp_increase: int
    sp_increase: int


XP_THRESHOLDS = get_xp_thresholds()
HP_PER_LEVEL = get_hp_per_level()
SP_PER_LEVEL = get_sp_per_level()

CLASS_ABILITIES: Dict[str, List[ClassAbility]] = {
    class_name: [ClassAbility(**ability) for ability in abilities]
    for class_name, abilities in get_class_abilities().items()
}

# Default stat to increase on even levels (per dominant class)
STAT_BONUS_BY_CLASS = get_stat_bonus_by_class()
STAT_BONUS_BY_CLASS.setdefault("None", "MIG")


class ProgressionSystem:
    """
    Manages XP, leveling, and class ability progression.
    
    Usage:
        ps = ProgressionSystem()
        result = ps.add_xp(character, 300)
        if result:
            print(f"Leveled up to {result.new_level}!")
    """

    def get_level_for_xp(self, xp: int) -> int:
        """
        Convert total XP to character level.
        
        Args:
            xp: Total experience points
        
        Returns:
            Character level (1-20)
        """
        level = 1
        for i, threshold in enumerate(XP_THRESHOLDS):
            if xp >= threshold:
                level = i + 1
            else:
                break
        return min(level, 20)

    def add_xp(self, character: 'Character', amount: int) -> Optional[LevelUpResult]:
        """
        Add XP to a character and trigger level-ups if applicable.
        
        Args:
            character: Character receiving XP
            amount: XP amount to add
        
        Returns:
            LevelUpResult if character leveled up, None otherwise
        """
        old_level = character.level
        character.xp += amount
        new_level = self.get_level_for_xp(character.xp)
        new_level = min(new_level, 20)

        if new_level <= old_level:
            return None

        # Determine stat bonus (even levels only)
        stat_bonus = None
        if new_level % 2 == 0:
            dominant = character.dominant_class
            stat_bonus = STAT_BONUS_BY_CLASS.get(dominant, "MIG")
            if stat_bonus in character.stats:
                character.stats[stat_bonus] += 1

        # HP increase
        dominant = character.dominant_class
        hp_die = HP_PER_LEVEL.get(dominant, 8) if dominant else 8
        levels_gained = new_level - old_level
        hp_increase = (hp_die // 2 + 1) * levels_gained  # Fixed avg for determinism
        character.max_hp += hp_increase
        character.hp = character.max_hp  # Full heal on level-up

        # Spell points increase
        sp_per = SP_PER_LEVEL.get(dominant, 0) if dominant else 0
        sp_increase = sp_per * levels_gained
        if sp_increase > 0:
            character.max_spell_points += sp_increase
            character.spell_points = character.max_spell_points

        # Unlock new abilities
        new_abilities = []
        if dominant:
            for lvl in range(old_level + 1, new_level + 1):
                abilities_at_level = self.get_abilities(dominant, lvl)
                # Only new abilities (exactly at this level)
                for ability in abilities_at_level:
                    if ability.required_level == lvl:
                        new_abilities.append(ability)

        # Update character level
        character.level = new_level

        return LevelUpResult(
            old_level=old_level,
            new_level=new_level,
            new_abilities=new_abilities,
            stat_bonus=stat_bonus,
            hp_increase=hp_increase,
            sp_increase=sp_increase,
        )

    def get_abilities(self, class_name: str, level: int) -> List[ClassAbility]:
        """
        Get all abilities unlocked for a class up to a given level.
        
        Args:
            class_name: Class name (warrior, rogue, mage, priest)
            level: Character level (abilities up to and including this level)
        
        Returns:
            List of ClassAbility objects unlocked at <= level
        """
        if level <= 0:
            return []

        class_lower = class_name.lower()
        abilities = CLASS_ABILITIES.get(class_lower, [])
        return [a for a in abilities if a.required_level <= level]

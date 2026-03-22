"""
Ember RPG - Core Engine
Leveling & Progression System
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

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


# XP thresholds to reach each level
XP_THRESHOLDS = [
    0,       # L1
    300,     # L2
    900,     # L3
    2700,    # L4
    6500,    # L5
    14000,   # L6
    23000,   # L7
    34000,   # L8
    48000,   # L9
    64000,   # L10
    85000,   # L11
    100000,  # L12
    120000,  # L13
    140000,  # L14
    165000,  # L15
    195000,  # L16
    225000,  # L17
    265000,  # L18
    305000,  # L19
    355000,  # L20
]

# HP gained per level-up per class (d-value)
HP_PER_LEVEL = {
    "warrior": 10,
    "rogue": 8,
    "priest": 8,
    "mage": 6,
}

# Spell points gained per level-up for casters
SP_PER_LEVEL = {
    "mage": 4,
    "priest": 3,
    "warrior": 0,
    "rogue": 0,
}

# Class abilities: class_name -> list of ClassAbility
CLASS_ABILITIES: Dict[str, List[ClassAbility]] = {
    "warrior": [
        ClassAbility(
            name="Combat Stance",
            description="+2 to MIG skill checks in combat. Passive combat training.",
            passive=True,
            required_level=1,
            class_name="warrior",
            cost=0,
        ),
        ClassAbility(
            name="Second Wind",
            description="Once per rest, regain 1d10 + level HP as a bonus action.",
            passive=False,
            required_level=2,
            class_name="warrior",
            cost=1,
        ),
        ClassAbility(
            name="Extra Attack",
            description="Make one additional attack per turn for 1 AP (instead of 2).",
            passive=True,
            required_level=3,
            class_name="warrior",
            cost=0,
        ),
        ClassAbility(
            name="Battle Hardened",
            description="Years of combat have toughened your hide. Gain +2 AC permanently.",
            passive=True,
            required_level=4,
            class_name="warrior",
            cost=0,
        ),
        ClassAbility(
            name="Mighty Blow",
            description="Once per turn, make a strike that deals double damage on hit.",
            passive=False,
            required_level=5,
            class_name="warrior",
            cost=1,
        ),
    ],
    "rogue": [
        ClassAbility(
            name="Sneak Attack",
            description="Deal +1d6 bonus damage when attacking with advantage.",
            passive=True,
            required_level=1,
            class_name="rogue",
            cost=0,
        ),
        ClassAbility(
            name="Nimble Escape",
            description="Disengage or hide as a free action once per turn.",
            passive=False,
            required_level=2,
            class_name="rogue",
            cost=0,
        ),
        ClassAbility(
            name="Cunning Action",
            description="Dash, Disengage, or Hide costs only 1 AP instead of 2.",
            passive=True,
            required_level=3,
            class_name="rogue",
            cost=0,
        ),
        ClassAbility(
            name="Uncanny Dodge",
            description="When an attacker you can see hits you, halve the damage once per round.",
            passive=False,
            required_level=4,
            class_name="rogue",
            cost=0,
        ),
        ClassAbility(
            name="Evasion",
            description="When you succeed on a DEX saving throw, you take 0 damage.",
            passive=True,
            required_level=5,
            class_name="rogue",
            cost=0,
        ),
    ],
    "mage": [
        ClassAbility(
            name="Arcane Recovery",
            description="Once per rest, recover level/2 spell points.",
            passive=False,
            required_level=1,
            class_name="mage",
            cost=0,
        ),
        ClassAbility(
            name="Spellcraft",
            description="Your mastery of spell theory increases your spell save DC by 1.",
            passive=True,
            required_level=2,
            class_name="mage",
            cost=0,
        ),
        ClassAbility(
            name="Expanded Spells",
            description="You learn 2 additional spells of your choice.",
            passive=True,
            required_level=3,
            class_name="mage",
            cost=0,
        ),
        ClassAbility(
            name="Metamagic: Quicken",
            description="Spend 2 spell points to cast a spell as a bonus action (1 AP instead of 2).",
            passive=False,
            required_level=4,
            class_name="mage",
            cost=2,
        ),
        ClassAbility(
            name="Potent Cantrip",
            description="Your cantrips deal bonus damage equal to your MND modifier.",
            passive=True,
            required_level=5,
            class_name="mage",
            cost=0,
        ),
    ],
    "priest": [
        ClassAbility(
            name="Divine Favor",
            description="Once per rest, add +1d4 to all rolls for 1 minute.",
            passive=False,
            required_level=1,
            class_name="priest",
            cost=1,
        ),
        ClassAbility(
            name="Healing Touch",
            description="Cure Wounds and similar spells heal additional HP equal to your level.",
            passive=True,
            required_level=2,
            class_name="priest",
            cost=0,
        ),
        ClassAbility(
            name="Channel Divinity",
            description="Once per rest, turn undead or restore 2d6 HP to allies in 30ft.",
            passive=False,
            required_level=3,
            class_name="priest",
            cost=2,
        ),
        ClassAbility(
            name="Sacred Flame",
            description="Your fire damage ignores resistance. Sacred attacks bypass normal defenses.",
            passive=True,
            required_level=4,
            class_name="priest",
            cost=0,
        ),
        ClassAbility(
            name="Greater Heal",
            description="Channel 4 spell points to restore 4d8+5 HP to one target.",
            passive=False,
            required_level=5,
            class_name="priest",
            cost=4,
        ),
    ],
}

# Default stat to increase on even levels (per dominant class)
STAT_BONUS_BY_CLASS = {
    "warrior": "MIG",
    "rogue": "AGI",
    "mage": "MND",
    "priest": "INS",
    None: "MIG",  # No class default
}


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

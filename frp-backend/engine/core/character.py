"""
Ember RPG - Core Engine
Universal Character class for PC, NPC, and monsters
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class ProficiencyLevel(Enum):
    """Skill proficiency tiers."""
    UNTRAINED = 0
    TRAINED = 2
    EXPERT = 4
    MASTER = 6


@dataclass
class Character:
    """
    Universal character representation for all entities.
    
    Attributes:
        name: Character name
        race: Race/species (default "Human")
        classes: Dictionary of class_name -> level (supports multiclass)
        stats: Six core stats (MIG, AGI, END, MND, INS, PRE), range 3-20
        hp: Current hit points
        max_hp: Maximum hit points
        ac: Armor class (defense)
        initiative_bonus: Bonus to initiative rolls
        spell_points: Current spell points
        max_spell_points: Maximum spell points
        skills: Dictionary of skill_name -> proficiency bonus
        gold: Gold pieces
        inventory: List of item IDs
        equipment: Dictionary of slot -> item_id
        conditions: List of active conditions (poisoned, stunned, etc.)
        xp: Current experience points
        level: Character level (1-20)
    """
    
    # Identity
    name: str
    race: str = "Human"
    classes: Dict[str, int] = field(default_factory=dict)
    
    # Core Stats (3-20 range, default 10)
    stats: Dict[str, int] = field(default_factory=lambda: {
        'MIG': 10, 'AGI': 10, 'END': 10,
        'MND': 10, 'INS': 10, 'PRE': 10
    })
    
    # Combat
    hp: int = 10
    max_hp: int = 10
    ac: int = 10
    initiative_bonus: int = 0
    
    # Resources
    spell_points: int = 0
    max_spell_points: int = 0
    
    # Progression
    xp: int = 0
    level: int = 1
    
    # Skills (skill_name -> proficiency level: 0/2/4/6)
    skills: Dict[str, int] = field(default_factory=dict)
    
    # Inventory
    gold: int = 0
    inventory: List[str] = field(default_factory=list)
    equipment: Dict[str, str] = field(default_factory=dict)
    
    # State
    conditions: List[str] = field(default_factory=list)
    
    # --- Skill -> Stat Mapping ---
    SKILL_STATS = {
        'athletics': 'MIG',
        'stealth': 'AGI',
        'survival': 'INS',
        'melee': 'MIG',
        'ranged': 'AGI',
        'defense': 'END',
        'arcana': 'MND',
        'lore': 'MND',
        'perception': 'INS',
        'persuasion': 'PRE',
        'deception': 'PRE',
        'intimidation': 'PRE'
    }
    
    # --- Derived Properties ---
    
    @property
    def total_level(self) -> int:
        """
        Calculate total level across all classes.
        
        Returns:
            Sum of all class levels, or 0 if no classes
        """
        return sum(self.classes.values()) if self.classes else 0
    
    @property
    def dominant_class(self) -> Optional[str]:
        """
        Get the class with the highest level.
        
        Returns:
            Class name with highest level, or None if no classes
            (if tie, returns first by insertion order)
        """
        if not self.classes:
            return None
        return max(self.classes.items(), key=lambda x: x[1])[0]
    
    # --- Methods ---
    
    def stat_modifier(self, stat: str) -> int:
        """
        Calculate the modifier for a given stat.
        
        Formula: (stat_value - 10) // 2
        
        Args:
            stat: Stat name (MIG, AGI, END, MND, INS, PRE)
        
        Returns:
            Modifier value (e.g., 16 -> +3, 8 -> -1)
        
        Raises:
            ValueError: If stat name is invalid
        """
        if stat not in self.stats:
            raise ValueError(f"Unknown stat: {stat}")
        return (self.stats[stat] - 10) // 2
    
    def skill_bonus(self, skill: str) -> int:
        """
        Calculate total bonus for a skill check.
        
        Formula: governing_stat_modifier + proficiency_bonus
        
        Args:
            skill: Skill name (lowercase, e.g., 'stealth', 'arcana')
        
        Returns:
            Total skill bonus
        
        Raises:
            ValueError: If skill name is invalid
        """
        skill_lower = skill.lower()
        if skill_lower not in self.SKILL_STATS:
            raise ValueError(f"Unknown skill: {skill}")
        
        governing_stat = self.SKILL_STATS[skill_lower]
        stat_mod = self.stat_modifier(governing_stat)
        proficiency = self.skills.get(skill_lower, 0)
        
        return stat_mod + proficiency
    
    def add_class(self, class_name: str, levels: int = 1):
        """
        Add or increase levels in a class.
        
        Args:
            class_name: Name of the class (e.g., 'Warrior', 'Mage')
            levels: Number of levels to add (default 1)
        """
        if class_name in self.classes:
            self.classes[class_name] += levels
        else:
            self.classes[class_name] = levels
    
    def equip_item(self, slot: str, item_id: str):
        """
        Equip an item to an equipment slot.
        
        Args:
            slot: Equipment slot (weapon, offhand, armor, accessory)
            item_id: Item identifier to equip
        
        Raises:
            ValueError: If slot name is invalid
        """
        valid_slots = ['weapon', 'offhand', 'armor', 'accessory']
        if slot not in valid_slots:
            raise ValueError(f"Invalid slot: {slot}. Valid slots: {valid_slots}")
        self.equipment[slot] = item_id
    
    def unequip_item(self, slot: str) -> Optional[str]:
        """
        Remove an item from an equipment slot.
        
        Args:
            slot: Equipment slot to clear
        
        Returns:
            Item ID that was removed, or None if slot was empty
        """
        return self.equipment.pop(slot, None)
    
    def to_dict(self) -> dict:
        """
        Serialize character to a dictionary.
        
        Returns:
            Dictionary containing all character data
        """
        return {
            'name': self.name,
            'race': self.race,
            'classes': self.classes,
            'stats': self.stats,
            'hp': self.hp,
            'max_hp': self.max_hp,
            'ac': self.ac,
            'initiative_bonus': self.initiative_bonus,
            'spell_points': self.spell_points,
            'max_spell_points': self.max_spell_points,
            'xp': self.xp,
            'level': self.level,
            'skills': self.skills,
            'gold': self.gold,
            'inventory': self.inventory,
            'equipment': self.equipment,
            'conditions': self.conditions
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Character':
        """
        Deserialize character from a dictionary.
        
        Args:
            data: Dictionary containing character data
        
        Returns:
            Character instance
        """
        return cls(**data)
    
    def __repr__(self) -> str:
        """String representation of character."""
        class_str = ", ".join(f"{c} {lvl}" for c, lvl in self.classes.items()) if self.classes else "Level 0"
        return f"<Character {self.name} ({self.race}) - {class_str} - HP {self.hp}/{self.max_hp}>"

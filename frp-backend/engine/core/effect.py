"""
Ember RPG - Core Engine
Effect system for items and spells
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.core.character import Character


class Effect(ABC):
    """Base class for all effects (item, spell, ability)."""
    
    @abstractmethod
    def apply(self, target: 'Character') -> str:
        """
        Apply effect to target character.
        
        Args:
            target: Character to apply effect to
        
        Returns:
            Log message describing what happened
        """
        pass
    
    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize effect to dictionary."""
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Effect':
        """
        Deserialize effect from dictionary.
        
        Args:
            data: Dictionary containing effect data (must have 'type' key)
        
        Returns:
            Effect instance of appropriate type
        
        Raises:
            ValueError: If effect type is unknown
        """
        effect_type = data.get('type')
        if not effect_type:
            raise ValueError("Effect data missing 'type' field")
        
        # Remove 'type' from data before passing to constructor
        effect_data = {k: v for k, v in data.items() if k != 'type'}
        
        if effect_type == 'heal':
            return HealEffect(**effect_data)
        elif effect_type == 'damage':
            return DamageEffect(**effect_data)
        elif effect_type == 'buff':
            return BuffEffect(**effect_data)
        else:
            raise ValueError(f"Unknown effect type: {effect_type}")


@dataclass
class HealEffect(Effect):
    """Restore HP to target."""
    
    amount: str  # Dice notation (e.g., "2d6+2")
    
    def apply(self, target: 'Character') -> str:
        from engine.core.rules import roll_dice
        
        roll = roll_dice(self.amount)
        old_hp = target.hp
        target.hp = min(target.hp + roll, target.max_hp)
        healed = target.hp - old_hp
        
        return f"{target.name} heals {healed} HP (rolled {roll})"
    
    def to_dict(self) -> dict:
        return {'type': 'heal', 'amount': self.amount}


@dataclass
class DamageEffect(Effect):
    """Deal damage to target."""
    
    amount: str  # Dice notation
    damage_type: str  # fire, cold, necrotic, etc.
    
    def apply(self, target: 'Character') -> str:
        from engine.core.rules import roll_dice
        
        roll = roll_dice(self.amount)
        # TODO: Apply resistances/immunities (Module 3)
        target.hp -= roll
        
        return f"{target.name} takes {roll} {self.damage_type} damage"
    
    def to_dict(self) -> dict:
        return {
            'type': 'damage',
            'amount': self.amount,
            'damage_type': self.damage_type
        }


@dataclass
class BuffEffect(Effect):
    """Temporarily increase a stat."""
    
    stat: str  # MIG, AGI, END, etc.
    bonus: int  # +2, +4, etc.
    duration: int  # turns/hours (context-dependent)
    
    def apply(self, target: 'Character') -> str:
        # Temporary stat buff
        # TODO: Proper condition tracking with expiry (Module 3)
        # For now, just apply directly
        if self.stat not in target.stats:
            raise ValueError(f"Invalid stat: {self.stat}")
        
        target.stats[self.stat] += self.bonus
        return f"{target.name} gains +{self.bonus} {self.stat} for {self.duration} turns"
    
    def to_dict(self) -> dict:
        return {
            'type': 'buff',
            'stat': self.stat,
            'bonus': self.bonus,
            'duration': self.duration
        }

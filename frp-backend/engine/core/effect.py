"""
Ember RPG - Core Engine
Effect system for items and spells
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

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
            return BuffEffect.from_dict_data(effect_data)
        elif effect_type == 'status':
            return StatusEffect(**effect_data)
        elif effect_type == 'utility':
            return UtilityEffect(**effect_data)
        elif effect_type == 'summon':
            return SummonEffect(**effect_data)
        else:
            raise ValueError(f"Unknown effect type: {effect_type}")


@dataclass
class HealEffect(Effect):
    """Restore HP to target."""
    
    amount: str  # Dice notation (e.g., "2d6+2")
    
    def __init__(self, amount: str, **kwargs):
        self.amount = amount
        # Accept extra fields (e.g. targets) without crashing
        self._extra = kwargs

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
    
    def __init__(self, amount: str, damage_type: str, **kwargs):
        self.amount = amount
        self.damage_type = damage_type
        self._extra = kwargs

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
    bonus: Any  # +2, +4, etc. (may be int or str for dice notation)
    duration: int  # turns/hours (context-dependent)

    def __init__(self, stat: str, duration: int, bonus: Any = None,
                 amount: Any = None, value: Any = None, **kwargs):
        self.stat = stat
        self.duration = duration
        # Accept bonus, amount, or value as aliases
        resolved = bonus if bonus is not None else (amount if amount is not None else value)
        if resolved is None:
            raise ValueError("BuffEffect requires one of: bonus, amount, value")
        self.bonus = resolved
        self._extra = kwargs

    @classmethod
    def from_dict_data(cls, data: dict) -> 'BuffEffect':
        """Create BuffEffect from raw dict data (without 'type' key)."""
        return cls(**data)

    def apply(self, target: 'Character') -> str:
        # Temporary stat buff
        # TODO: Proper condition tracking with expiry (Module 3)
        # For now, just apply directly
        if self.stat not in target.stats:
            raise ValueError(f"Invalid stat: {self.stat}")
        
        bonus_val = self.bonus if isinstance(self.bonus, (int, float)) else 0
        target.stats[self.stat] += bonus_val
        return f"{target.name} gains +{self.bonus} {self.stat} for {self.duration} turns"
    
    def to_dict(self) -> dict:
        return {
            'type': 'buff',
            'stat': self.stat,
            'bonus': self.bonus,
            'duration': self.duration
        }


class StatusEffect(Effect):
    """Apply a status condition to a target."""

    def __init__(self, status: str, duration: int = 0, **kwargs):
        self.status = status
        self.duration = duration
        self._extra = kwargs

    def apply(self, target: 'Character') -> str:
        # TODO: Proper condition tracking (Module 3)
        return f"{target.name} is affected by {self.status} for {self.duration} turns"

    def to_dict(self) -> dict:
        return {'type': 'status', 'status': self.status, 'duration': self.duration}


class UtilityEffect(Effect):
    """Non-damage utility action (dispel, teleport, detect, etc.)."""

    def __init__(self, action: str, **kwargs):
        self.action = action
        self._extra = kwargs

    def apply(self, target: 'Character') -> str:
        return f"Utility action '{self.action}' applied to {target.name}"

    def to_dict(self) -> dict:
        return {'type': 'utility', 'action': self.action}


class SummonEffect(Effect):
    """Summon a creature or object."""

    def __init__(self, creature: str, **kwargs):
        self.creature = creature
        self._extra = kwargs

    def apply(self, target: 'Character') -> str:
        return f"{target.name} summons a {self.creature}"

    def to_dict(self) -> dict:
        return {'type': 'summon', 'creature': self.creature}


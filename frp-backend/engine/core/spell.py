"""
Ember RPG - Core Engine
Magic system (spells, spell points, casting)
"""
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from enum import Enum
import json

if TYPE_CHECKING:
    from engine.core.character import Character
    from engine.core.effect import Effect


class SpellSchool(Enum):
    """Spell schools for categorization."""
    EVOCATION = "evocation"
    ABJURATION = "abjuration"
    TRANSMUTATION = "transmutation"
    NECROMANCY = "necromancy"
    CONJURATION = "conjuration"
    ILLUSION = "illusion"


class TargetType(Enum):
    """Spell targeting modes."""
    SELF = "self"
    SINGLE = "single"
    AREA = "area"


@dataclass
class Spell:
    """
    Spell definition.
    
    Attributes:
        name: Spell name
        cost: Spell point cost
        range: Range in feet (0 = self, 30 = close, 60+ = far)
        target_type: Who can be targeted
        effects: List of effects to apply
        school: Spell school (flavor)
        description: Flavor text
        level: Spell tier (1-9)
    """
    name: str
    cost: int
    range: int
    target_type: TargetType
    effects: List['Effect'] = field(default_factory=list)
    school: SpellSchool = SpellSchool.EVOCATION
    description: str = ""
    level: int = 1
    
    def can_cast(self, caster: 'Character') -> bool:
        """
        Check if caster has enough spell points.
        
        Args:
            caster: Character attempting to cast
        
        Returns:
            True if caster has enough spell points
        """
        return caster.spell_points >= self.cost
    
    def cast(self, caster: 'Character', target: Optional['Character'] = None) -> dict:
        """
        Cast spell on target.
        
        Args:
            caster: Character casting the spell
            target: Target character (required for single-target spells)
        
        Returns:
            Result dictionary with effects and messages
        
        Raises:
            ValueError: If insufficient spell points or invalid target
        """
        if not self.can_cast(caster):
            raise ValueError(f"Insufficient spell points ({caster.spell_points}/{self.cost})")
        
        if self.target_type == TargetType.SINGLE and target is None:
            raise ValueError("Single-target spell requires a target")
        
        # Deduct spell points
        caster.spell_points -= self.cost
        
        # Determine actual target
        actual_target = target if self.target_type == TargetType.SINGLE else caster
        
        # Apply effects
        messages = []
        for effect in self.effects:
            msg = effect.apply(actual_target)
            messages.append(msg)
        
        return {
            "caster": caster.name,
            "spell": self.name,
            "target": actual_target.name,
            "cost": self.cost,
            "effects": messages
        }
    
    def to_dict(self) -> dict:
        """Serialize spell to dictionary."""
        return {
            "name": self.name,
            "cost": self.cost,
            "range": self.range,
            "target_type": self.target_type.value,
            "effects": [e.to_dict() for e in self.effects],
            "school": self.school.value,
            "description": self.description,
            "level": self.level
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Spell':
        """
        Deserialize spell from dictionary.
        
        Args:
            data: Dictionary containing spell data
        
        Returns:
            Spell instance
        """
        from engine.core.effect import Effect
        
        data = data.copy()  # Don't mutate input
        data['target_type'] = TargetType(data['target_type'])
        data['school'] = SpellSchool(data['school'])
        data['effects'] = [Effect.from_dict(e) for e in data.get('effects', [])]
        
        return cls(**data)


class SpellDatabase:
    """Load and manage spell definitions from JSON."""
    
    def __init__(self, filepath: Optional[str] = None):
        """
        Initialize spell database.
        
        Args:
            filepath: Path to spells JSON file (optional)
        """
        self.spells: List[Spell] = []
        if filepath:
            self.load(filepath)
    
    def load(self, filepath: str):
        """
        Load spells from JSON file.
        
        Args:
            filepath: Path to JSON file
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        for spell_data in data['spells']:
            spell = Spell.from_dict(spell_data)
            self.spells.append(spell)
    
    def add(self, spell: Spell):
        """Add a spell to the database."""
        self.spells.append(spell)
    
    def get(self, name: str) -> Optional[Spell]:
        """
        Get spell by name (case-insensitive).
        
        Args:
            name: Spell name
        
        Returns:
            Spell if found, None otherwise
        """
        for spell in self.spells:
            if spell.name.lower() == name.lower():
                return spell
        return None
    
    def filter(self, 
               school: Optional[SpellSchool] = None,
               max_cost: Optional[int] = None,
               max_level: Optional[int] = None) -> List[Spell]:
        """
        Filter spells by criteria.
        
        Args:
            school: Filter by spell school
            max_cost: Maximum spell point cost
            max_level: Maximum spell level
        
        Returns:
            List of matching spells
        """
        results = self.spells
        
        if school:
            results = [s for s in results if s.school == school]
        if max_cost is not None:
            results = [s for s in results if s.cost <= max_cost]
        if max_level is not None:
            results = [s for s in results if s.level <= max_level]
        
        return results

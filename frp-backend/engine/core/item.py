"""
Ember RPG - Core Engine
Universal Item class for all objects
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from engine.core.character import Character
    from engine.core.effect import Effect


class ItemType(Enum):
    """Item categories."""
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    CONSUMABLE = "consumable"
    QUEST = "quest"
    CURRENCY = "currency"


class Rarity(Enum):
    """
    Item rarity tiers.
    Value tuple: (value_multiplier, color)
    """
    COMMON = (1.0, "white")
    UNCOMMON = (2.0, "green")
    RARE = (5.0, "blue")
    EPIC = (10.0, "purple")
    LEGENDARY = (20.0, "orange")


@dataclass
class Item:
    """
    Universal item representation for all objects.
    
    Attributes:
        name: Item name
        value: Base value in gold pieces
        weight: Weight in pounds
        item_type: Category (weapon, armor, consumable, etc.)
        description: Flavor text
        rarity: Rarity tier (affects value multiplier)
        damage_dice: Weapon damage notation (e.g., "1d10")
        damage_type: Weapon damage type (slashing, fire, etc.)
        armor_bonus: AC bonus granted by armor/shield
        armor_type: Armor category (light, medium, heavy)
        effects: List of effects applied when used
        stackable: Whether item can stack (potions, gold, etc.)
        quantity: Number of items in stack
        can_drop: Whether item can be dropped
        can_sell: Whether item can be sold
    """
    
    # Core properties
    name: str
    value: int  # gold pieces
    weight: float  # pounds
    item_type: ItemType
    description: str = ""
    rarity: Rarity = Rarity.COMMON
    
    # Weapon properties
    damage_dice: Optional[str] = None
    damage_type: Optional[str] = None
    
    # Armor properties
    armor_bonus: int = 0
    armor_type: Optional[str] = None  # light, medium, heavy
    
    # Effects (for consumables, magic items)
    effects: List['Effect'] = field(default_factory=list)
    
    # Stacking
    stackable: bool = False
    quantity: int = 1
    
    # Restrictions
    can_drop: bool = True
    can_sell: bool = True
    
    @property
    def total_value(self) -> int:
        """Calculate total value (value × quantity)."""
        return self.value * self.quantity
    
    @property
    def total_weight(self) -> float:
        """Calculate total weight (weight × quantity)."""
        return self.weight * self.quantity
    
    def apply_effects(self, target: 'Character') -> List[str]:
        """
        Apply all item effects to target character.
        
        Args:
            target: Character to apply effects to
        
        Returns:
            List of log messages describing what happened
        """
        messages = []
        for effect in self.effects:
            msg = effect.apply(target)
            messages.append(msg)
        return messages
    
    def to_dict(self) -> dict:
        """
        Serialize item to dictionary.
        
        Returns:
            Dictionary containing all item data
        """
        return {
            'name': self.name,
            'value': self.value,
            'weight': self.weight,
            'item_type': self.item_type.value,
            'description': self.description,
            'rarity': self.rarity.name,
            'damage_dice': self.damage_dice,
            'damage_type': self.damage_type,
            'armor_bonus': self.armor_bonus,
            'armor_type': self.armor_type,
            'effects': [e.to_dict() for e in self.effects],
            'stackable': self.stackable,
            'quantity': self.quantity,
            'can_drop': self.can_drop,
            'can_sell': self.can_sell
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Item':
        """
        Deserialize item from dictionary.
        
        Args:
            data: Dictionary containing item data
        
        Returns:
            Item instance
        """
        from engine.core.effect import Effect
        
        # Convert enum strings back to enums
        data['item_type'] = ItemType(data['item_type'])
        data['rarity'] = Rarity[data['rarity']]
        
        # Reconstruct effects
        data['effects'] = [Effect.from_dict(e) for e in data.get('effects', [])]
        
        return cls(**data)
    
    def __repr__(self) -> str:
        """String representation of item."""
        qty_str = f" x{self.quantity}" if self.stackable and self.quantity > 1 else ""
        return f"<Item {self.name} ({self.rarity.name}){qty_str} - {self.total_value}gp, {self.total_weight:.1f}lb>"


class ItemDatabase:
    """Load and manage item definitions from JSON."""

    def __init__(self, filepath: Optional[str] = None):
        """
        Initialize item database.

        Args:
            filepath: Path to items JSON file (optional)
        """
        self.items: List[Item] = []
        if filepath:
            self.load(filepath)

    def load(self, filepath: str):
        """
        Load items from JSON file.

        Args:
            filepath: Path to JSON file containing item definitions.
                      Expected structure: {"items": [...]}
        """
        with open(filepath, 'r') as f:
            data = json.load(f)

        for item_data in data['items']:
            item = self._item_from_json(item_data)
            self.items.append(item)

    @staticmethod
    def _item_from_json(data: dict) -> 'Item':
        """Convert a JSON item dict to an Item instance (no Effect objects)."""
        return Item(
            name=data['name'],
            value=data.get('value', 0),
            weight=data.get('weight', 0.0),
            item_type=ItemType(data['type']),
            description=data.get('description', ''),
            rarity=Rarity[data.get('rarity', 'COMMON').upper()],
            damage_dice=data.get('damage_dice'),
            damage_type=data.get('damage_type'),
            armor_bonus=data.get('armor_bonus', 0),
            armor_type=data.get('armor_type'),
            stackable=data.get('stackable', False),
            quantity=data.get('quantity', 1),
            can_drop=data.get('can_drop', True),
            can_sell=data.get('can_sell', True),
        )

    def add(self, item: Item):
        """Add an item to the database."""
        self.items.append(item)

    def get(self, name: str) -> Optional[Item]:
        """
        Get item by name (case-insensitive).

        Args:
            name: Item name

        Returns:
            Item if found, None otherwise
        """
        for item in self.items:
            if item.name.lower() == name.lower():
                return item
        return None

    def filter(self,
               item_type: Optional[ItemType] = None,
               rarity: Optional[Rarity] = None,
               max_value: Optional[int] = None) -> List[Item]:
        """
        Filter items by criteria.

        Args:
            item_type: Filter by item type
            rarity: Filter by rarity
            max_value: Maximum gold value

        Returns:
            List of matching items
        """
        results = self.items

        if item_type:
            results = [i for i in results if i.item_type == item_type]
        if rarity:
            results = [i for i in results if i.rarity == rarity]
        if max_value is not None:
            results = [i for i in results if i.value <= max_value]

        return results

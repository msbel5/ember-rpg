# PRD: Item System (Module 2)
**Project:** Ember RPG  
**Phase:** 2  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-22  
**Status:** Draft

---

## 1. Overview

**Purpose:** Implement the universal `Item` class and `Effect` system that represents all objects (weapons, armor, consumables, quest items, currency) in Ember RPG.

**Scope:**
- Item data structure (name, value, weight, type, effects)
- Item types (weapon, armor, consumable, quest, junk, currency)
- Effect system (heal, damage, buff, debuff)
- Deterministic economy (value/weight/rarity)
- Serialization/deserialization

**Out of Scope (other modules):**
- Combat damage application (Module 3)
- Spell effects (Module 4)
- Loot tables (Phase 3)
- Crafting (Phase 7)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR1: Item Creation**
- Create item with name, value, weight, type
- Default values for optional fields
- Validation: value ≥ 0, weight ≥ 0

**FR2: Item Types**
- Six item types: weapon, armor, shield, consumable, quest, currency
- Type-specific properties:
  - Weapon: damage dice, damage type
  - Armor: armor bonus, armor type (light/medium/heavy)
  - Consumable: effects (applied on use)
  - Quest: cannot be dropped/sold
  - Currency: stackable, 1 value = 1 gold

**FR3: Effect System**
- Base Effect class (abstract)
- Concrete effects:
  - Heal: restore HP (e.g., "2d6+2")
  - Damage: deal damage (e.g., "1d6 fire")
  - Buff: temporary stat increase (e.g., "+2 MIG for 1 hour")
  - Debuff: temporary stat decrease
- Effects can be applied to Character instances

**FR4: Stacking**
- Stackable items (potions, gold, arrows) have quantity
- Non-stackable items (weapons, armor) are unique instances

**FR5: Rarity & Value**
- Rarity tiers: Common, Uncommon, Rare, Epic, Legendary
- Value scaling: base value × rarity multiplier

**FR6: Serialization**
- Export item to JSON (save)
- Import item from JSON (load)
- Validate loaded data

### 2.2 Non-Functional Requirements

**NFR1: Performance**
- Item creation: < 0.1ms
- Effect application: < 1ms

**NFR2: Testability**
- 100% unit test coverage for Item and Effect classes

**NFR3: Extensibility**
- Easy to add new item types
- Easy to add new effect types

---

## 3. Data Model

### 3.1 Item Class

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class ItemType(Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    CONSUMABLE = "consumable"
    QUEST = "quest"
    CURRENCY = "currency"

class Rarity(Enum):
    COMMON = (1.0, "white")
    UNCOMMON = (2.0, "green")
    RARE = (5.0, "blue")
    EPIC = (10.0, "purple")
    LEGENDARY = (20.0, "orange")

@dataclass
class Item:
    # Core properties
    name: str
    value: int  # gold pieces
    weight: float  # pounds
    item_type: ItemType
    description: str = ""
    rarity: Rarity = Rarity.COMMON
    
    # Weapon properties
    damage_dice: Optional[str] = None  # "1d10", "2d6", etc.
    damage_type: Optional[str] = None  # "slashing", "fire", etc.
    
    # Armor properties
    armor_bonus: int = 0
    armor_type: Optional[str] = None  # "light", "medium", "heavy"
    
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
        """Apply all effects to target, return log messages."""
        messages = []
        for effect in self.effects:
            msg = effect.apply(target)
            messages.append(msg)
        return messages
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
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
        """Deserialize from dictionary."""
        # Convert enum strings back to enums
        data['item_type'] = ItemType(data['item_type'])
        data['rarity'] = Rarity[data['rarity']]
        # Reconstruct effects (requires Effect.from_dict)
        data['effects'] = [Effect.from_dict(e) for e in data.get('effects', [])]
        return cls(**data)
```

### 3.2 Effect System

```python
from abc import ABC, abstractmethod

class Effect(ABC):
    """Base class for all item effects."""
    
    @abstractmethod
    def apply(self, target: 'Character') -> str:
        """Apply effect to target, return log message."""
        pass
    
    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Effect':
        """Deserialize from dictionary."""
        effect_type = data['type']
        if effect_type == 'heal':
            return HealEffect(**{k: v for k, v in data.items() if k != 'type'})
        elif effect_type == 'damage':
            return DamageEffect(**{k: v for k, v in data.items() if k != 'type'})
        elif effect_type == 'buff':
            return BuffEffect(**{k: v for k, v in data.items() if k != 'type'})
        else:
            raise ValueError(f"Unknown effect type: {effect_type}")

@dataclass
class HealEffect(Effect):
    amount: str  # "2d6+2"
    
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
    amount: str  # "1d6"
    damage_type: str  # "fire", "necrotic", etc.
    
    def apply(self, target: 'Character') -> str:
        from engine.core.rules import roll_dice
        roll = roll_dice(self.amount)
        # TODO: Apply resistances/immunities (Module 3)
        target.hp -= roll
        return f"{target.name} takes {roll} {self.damage_type} damage"
    
    def to_dict(self) -> dict:
        return {'type': 'damage', 'amount': self.amount, 'damage_type': self.damage_type}

@dataclass
class BuffEffect(Effect):
    stat: str  # "MIG", "AGI", etc.
    bonus: int  # +2, +4, etc.
    duration: int  # turns/hours (context-dependent)
    
    def apply(self, target: 'Character') -> str:
        # Temporary stat buff (real implementation needs condition tracking)
        # For now, just apply directly
        target.stats[self.stat] += self.bonus
        return f"{target.name} gains +{self.bonus} {self.stat} for {self.duration} turns"
    
    def to_dict(self) -> dict:
        return {
            'type': 'buff',
            'stat': self.stat,
            'bonus': self.bonus,
            'duration': self.duration
        }
```

### 3.3 Rules Module (Dice Rolling)

```python
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
    
    Args:
        dice_str: Dice notation (e.g., "1d6", "2d10+3")
    
    Returns:
        Total roll result
    
    Raises:
        ValueError: If dice string is malformed
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
    
    # Roll dice
    total = sum(random.randint(1, die_size) for _ in range(num_dice))
    return total + modifier
```

---

## 4. Acceptance Criteria

### AC1: Item Creation
- [ ] Can create weapon with damage dice
- [ ] Can create armor with AC bonus
- [ ] Can create consumable with effects
- [ ] Default values applied correctly

### AC2: Item Properties
- [ ] Weapon has damage_dice and damage_type
- [ ] Armor has armor_bonus and armor_type
- [ ] Consumable has effects list
- [ ] Quest item has can_drop=False, can_sell=False

### AC3: Stacking
- [ ] Stackable items track quantity
- [ ] total_value = value × quantity
- [ ] total_weight = weight × quantity
- [ ] Non-stackable items have quantity=1

### AC4: Effect Application
- [ ] HealEffect restores HP (capped at max_hp)
- [ ] DamageEffect reduces HP
- [ ] BuffEffect increases stat temporarily
- [ ] apply_effects returns log messages

### AC5: Dice Rolling
- [ ] roll_dice("1d6") returns 1-6
- [ ] roll_dice("2d10") returns 2-20
- [ ] roll_dice("1d6+2") returns 3-8
- [ ] roll_dice("3d6+5") returns 8-23
- [ ] Raises error for invalid notation

### AC6: Serialization
- [ ] to_dict exports complete item data
- [ ] from_dict reconstructs identical item
- [ ] Effects serialize/deserialize correctly

---

## 5. Test Cases

### TC1: Weapon Creation
```python
def test_weapon_creation():
    longsword = Item(
        name="Longsword",
        value=15,
        weight=3.0,
        item_type=ItemType.WEAPON,
        damage_dice="1d10",
        damage_type="slashing"
    )
    assert longsword.name == "Longsword"
    assert longsword.damage_dice == "1d10"
    assert longsword.damage_type == "slashing"
    assert longsword.total_value == 15
    assert longsword.total_weight == 3.0
```

### TC2: Armor Creation
```python
def test_armor_creation():
    plate_armor = Item(
        name="Plate Armor",
        value=1500,
        weight=45.0,
        item_type=ItemType.ARMOR,
        armor_bonus=6,
        armor_type="heavy",
        rarity=Rarity.UNCOMMON
    )
    assert plate_armor.armor_bonus == 6
    assert plate_armor.armor_type == "heavy"
    assert plate_armor.rarity == Rarity.UNCOMMON
```

### TC3: Consumable with Effects
```python
def test_consumable_with_heal_effect():
    potion = Item(
        name="Potion of Healing",
        value=50,
        weight=0.5,
        item_type=ItemType.CONSUMABLE,
        effects=[HealEffect(amount="2d6+2")],
        stackable=True
    )
    assert len(potion.effects) == 1
    assert isinstance(potion.effects[0], HealEffect)
    assert potion.stackable is True
```

### TC4: Stacking
```python
def test_stackable_items():
    gold = Item(
        name="Gold Coins",
        value=1,
        weight=0.02,
        item_type=ItemType.CURRENCY,
        stackable=True,
        quantity=100
    )
    assert gold.quantity == 100
    assert gold.total_value == 100
    assert gold.total_weight == 2.0  # 0.02 × 100
```

### TC5: Effect Application (Heal)
```python
def test_heal_effect_application():
    char = Character(name="Test", hp=50, max_hp=100)
    potion = Item(
        name="Potion",
        value=50,
        weight=0.5,
        item_type=ItemType.CONSUMABLE,
        effects=[HealEffect(amount="2d6+2")]
    )
    
    messages = potion.apply_effects(char)
    
    assert char.hp > 50  # HP increased
    assert char.hp <= 100  # Capped at max_hp
    assert len(messages) == 1
    assert "heals" in messages[0]
```

### TC6: Dice Rolling
```python
@pytest.mark.parametrize("dice_str,min_val,max_val", [
    ("1d6", 1, 6),
    ("2d10", 2, 20),
    ("1d6+2", 3, 8),
    ("3d6+5", 8, 23),
    ("1d20-1", 0, 19),
])
def test_dice_rolling(dice_str, min_val, max_val):
    for _ in range(100):  # Test multiple times
        result = roll_dice(dice_str)
        assert min_val <= result <= max_val

def test_invalid_dice_notation():
    with pytest.raises(ValueError):
        roll_dice("invalid")
    with pytest.raises(ValueError):
        roll_dice("d6")  # Missing num_dice
```

### TC7: Quest Items
```python
def test_quest_item_restrictions():
    ancient_key = Item(
        name="Ancient Key",
        value=0,
        weight=0.1,
        item_type=ItemType.QUEST,
        can_drop=False,
        can_sell=False
    )
    assert ancient_key.can_drop is False
    assert ancient_key.can_sell is False
```

### TC8: Serialization
```python
def test_item_serialization():
    original = Item(
        name="Flaming Sword",
        value=500,
        weight=3.0,
        item_type=ItemType.WEAPON,
        damage_dice="1d10",
        damage_type="slashing",
        rarity=Rarity.RARE,
        effects=[DamageEffect(amount="1d6", damage_type="fire")],
        description="A sword wreathed in flames"
    )
    
    # Serialize
    data = original.to_dict()
    
    # Deserialize
    restored = Item.from_dict(data)
    
    # Verify
    assert restored.name == original.name
    assert restored.value == original.value
    assert restored.damage_dice == original.damage_dice
    assert len(restored.effects) == 1
    assert isinstance(restored.effects[0], DamageEffect)
```

---

## 6. Implementation Plan

1. **Create rules module:**
   - `engine/core/rules.py` with `roll_dice()`
   - Test dice rolling first (TC6)

2. **Create effect system:**
   - `engine/core/effect.py` with base Effect class
   - Implement HealEffect, DamageEffect, BuffEffect
   - Test effect application (TC5)

3. **Create item system:**
   - `engine/core/item.py` with Item class
   - Test weapon, armor, consumable creation (TC1-TC3)
   - Test stacking (TC4)

4. **Test serialization:**
   - Round-trip tests (TC8)

5. **Integration tests:**
   - Character + Item interaction
   - Effect application on Character

---

## 7. Dependencies

**Python Packages:**
- `python >= 3.11`
- `pytest >= 7.0` (already installed)

**Internal:**
- `engine.core.character` (Module 1)

---

## 8. Success Metrics

- [ ] All 8 test cases pass
- [ ] Code coverage ≥ 95%
- [ ] Dice rolling tested with 100+ samples
- [ ] Effect application validated on Character instances

---

**Next Step:** Implement `rules.py` → `effect.py` → `item.py` (TDD)

---

## 9. Public API

```python
class Item:
    def __init__(self, name: str, value: int, weight: float, item_type: ItemType, ...)
    # value >= 0, weight >= 0 assumed; no runtime validation in MVP

    @property
    def total_value(self) -> int:
        """Returns value * quantity."""

    @property
    def total_weight(self) -> float:
        """Returns weight * quantity."""

    def apply_effects(self, target: 'Character') -> List[str]:
        """Calls effect.apply(target) for each effect. Returns list of log messages."""

    def to_dict(self) -> dict:
        """JSON-serializable dict. Effects are serialized via each effect's to_dict()."""

    @classmethod
    def from_dict(cls, data: dict) -> 'Item':
        """Deserializes item + effects. Raises KeyError if required field missing."""

def roll_dice(dice_str: str) -> int:
    """Parses NdX[+/-M] notation and returns integer result.
    Raises: ValueError if dice_str is malformed."""
```

---

## 10. Acceptance Criteria (Standard Format)

AC-01 [FR1]: Given `Item(name="Longsword", value=15, weight=3.0, item_type=ItemType.WEAPON, damage_dice="1d10", damage_type="slashing")`, when created, then `damage_dice == "1d10"` and `total_value == 15`.

AC-02 [FR2]: Given an item with `item_type=ItemType.QUEST, can_drop=False, can_sell=False`, when inspected, then both flags are False and the item has no armor_bonus or damage_dice.

AC-03 [FR3]: Given a `HealEffect(amount="2d6+2")` applied to a Character with `hp=50, max_hp=100`, when `apply()` is called, then HP increases by the roll result (capped at 100).

AC-04 [FR4]: Given `Item(stackable=True, quantity=100, value=1, weight=0.02)`, when `total_value` and `total_weight` are accessed, then they return 100 and 2.0 respectively.

AC-05 [FR5]: Given `roll_dice("1d6")` called 50 times, when results are checked, then all results are between 1 and 6 inclusive. Given `roll_dice("1d6+2")`, then all results are between 3 and 8.

AC-06 [FR6]: Given a Flaming Sword item with a DamageEffect, when `to_dict()` is called and `from_dict()` is called on the result, then the restored item has identical name, damage_dice, and a DamageEffect with the same amount.

---

## 11. Performance Requirements

- Item creation: < 0.1ms
- Effect application (single effect): < 1ms
- Dice roll (`roll_dice`): < 0.1ms per call
- Serialization round-trip: < 1ms

---

## 12. Error Handling

| Condition | Method | Behavior |
|---|---|---|
| Malformed dice string `"d6"` | `roll_dice()` | Raises `ValueError("Invalid dice notation: d6")` |
| Unknown effect type in dict | `Effect.from_dict()` | Raises `ValueError("Unknown effect type: <type>")` |
| Missing required field in dict | `Item.from_dict()` | Raises `KeyError` |
| Heal effect overshooting max_hp | `HealEffect.apply()` | HP clamped to `max_hp` (no over-healing) |
| Negative value/weight | Constructor | No validation in MVP; callers responsible |

---

## 13. Integration Points

- **Character System (Module 1):** `apply_effects(target: Character)` mutates `character.hp`, `character.stats`
- **Combat Engine (Module 3):** `Item.damage_dice` and `Item.damage_type` consumed by `CombatManager.attack()`
- **Magic System (Module 4):** Shares `Effect` base class (spells and items both use HealEffect, DamageEffect, BuffEffect)
- **Progression System (Module 5):** Items may grant XP on use (future extension)

---

## 14. Test Coverage Target

- **Target:** ≥ 95% line coverage
- **Must cover:** all ItemType branches, all Effect subclass `apply()` methods, `roll_dice` with and without modifier, from_dict error path for unknown effect type
- **Statistical:** roll_dice tested over 100+ samples to verify distribution bounds

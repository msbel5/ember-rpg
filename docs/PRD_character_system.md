# PRD: Character System (Module 1)
**Project:** Ember RPG  
**Phase:** 2  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-22  
**Status:** Draft

---

## 1. Overview

**Purpose:** Implement the universal `Character` class that represents all entities (player characters, NPCs, monsters) in Ember RPG.

**Scope:**
- Character data structure (stats, skills, HP, inventory)
- Stat modifier calculation
- Skill bonus calculation
- Proficiency system
- Level calculation (multiclass support)
- Serialization/deserialization (save/load)

**Out of Scope (other modules):**
- Combat actions (Module 3)
- Spell casting (Module 4)
- Leveling logic (Module 5)
- AI behavior (Phase 3)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR1: Character Creation**
- Create character with name, race, initial class, stats
- Default values for optional fields
- Validation: stats 3-20, at least one class

**FR2: Stat System**
- Six stats: MIG, AGI, END, MND, INS, PRE
- Stat modifier: `(stat - 10) // 2`
- Support stat changes (buffs, debuffs, equipment)

**FR3: Skill System**
- 12 skills mapped to governing stats
- Proficiency tiers: Untrained (0), Trained (+2), Expert (+4), Master (+6)
- Skill bonus: `stat_mod + proficiency`

**FR4: Multiclass Support**
- Track multiple classes with levels: `{'Warrior': 5, 'Mage': 3}`
- Total level = sum of all class levels
- Query dominant class (highest level)

**FR5: Health & Resources**
- HP (current/max)
- Spell points (current/max, if caster)
- AC calculation (base 10 + AGI mod + armor + shield)
- Initiative bonus (INS modifier)

**FR6: Inventory & Equipment**
- List of items in inventory
- Equipment slots: weapon, offhand, armor, accessory (4 slots)
- Gold tracking

**FR7: Serialization**
- Export character to JSON (save)
- Import character from JSON (load)
- Validate loaded data

### 2.2 Non-Functional Requirements

**NFR1: Performance**
- Character creation: < 1ms
- Stat modifier calculation: < 0.01ms (trivial math)

**NFR2: Testability**
- 100% unit test coverage
- Property-based testing for stat modifiers

**NFR3: Extensibility**
- Easy to add new stats/skills
- Support future features (conditions, temporary effects)

---

## 3. Data Model

### 3.1 Character Class

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

class ProficiencyLevel(Enum):
    UNTRAINED = 0
    TRAINED = 2
    EXPERT = 4
    MASTER = 6

@dataclass
class Character:
    # Identity
    name: str
    race: str = "Human"
    classes: Dict[str, int] = field(default_factory=dict)  # class_name -> level
    
    # Core Stats (3-20 range)
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
    
    # Skills (skill_name -> proficiency level)
    skills: Dict[str, int] = field(default_factory=dict)
    
    # Inventory
    gold: int = 0
    inventory: List[str] = field(default_factory=list)  # item IDs (simplified for now)
    equipment: Dict[str, str] = field(default_factory=dict)  # slot -> item_id
    
    # State
    conditions: List[str] = field(default_factory=list)  # poisoned, stunned, etc.
    
    # --- Derived Properties ---
    
    @property
    def total_level(self) -> int:
        """Sum of all class levels."""
        return sum(self.classes.values()) if self.classes else 0
    
    @property
    def dominant_class(self) -> Optional[str]:
        """Class with highest level (or first if tie)."""
        if not self.classes:
            return None
        return max(self.classes.items(), key=lambda x: x[1])[0]
    
    # --- Methods ---
    
    def stat_modifier(self, stat: str) -> int:
        """Calculate modifier for a stat."""
        if stat not in self.stats:
            raise ValueError(f"Unknown stat: {stat}")
        return (self.stats[stat] - 10) // 2
    
    def skill_bonus(self, skill: str) -> int:
        """Calculate total bonus for a skill check."""
        # Skill -> governing stat mapping
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
        
        skill_lower = skill.lower()
        if skill_lower not in SKILL_STATS:
            raise ValueError(f"Unknown skill: {skill}")
        
        governing_stat = SKILL_STATS[skill_lower]
        stat_mod = self.stat_modifier(governing_stat)
        proficiency = self.skills.get(skill_lower, 0)
        
        return stat_mod + proficiency
    
    def add_class(self, class_name: str, level: int = 1):
        """Add or increase a class level."""
        if class_name in self.classes:
            self.classes[class_name] += level
        else:
            self.classes[class_name] = level
    
    def equip_item(self, slot: str, item_id: str):
        """Equip an item to a slot."""
        valid_slots = ['weapon', 'offhand', 'armor', 'accessory']
        if slot not in valid_slots:
            raise ValueError(f"Invalid slot: {slot}")
        self.equipment[slot] = item_id
    
    def unequip_item(self, slot: str) -> Optional[str]:
        """Remove item from slot, return item ID."""
        return self.equipment.pop(slot, None)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
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
            'skills': self.skills,
            'gold': self.gold,
            'inventory': self.inventory,
            'equipment': self.equipment,
            'conditions': self.conditions
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Character':
        """Deserialize from dictionary."""
        return cls(**data)
```

---

## 4. Acceptance Criteria

### AC1: Character Creation
- [ ] Can create character with minimal args (name only)
- [ ] Default values applied (race=Human, stats=10, hp=10)
- [ ] Can create with custom stats, classes, skills

### AC2: Stat Modifiers
- [ ] stat_modifier(10) = 0
- [ ] stat_modifier(8) = -1
- [ ] stat_modifier(16) = +3
- [ ] stat_modifier(20) = +5
- [ ] stat_modifier(3) = -4
- [ ] Raises error for invalid stat name

### AC3: Skill Bonuses
- [ ] Untrained skill (prof=0, stat=10): bonus = 0
- [ ] Trained skill (prof=2, stat=14): bonus = 2 + 2 = 4
- [ ] Expert skill (prof=4, stat=18): bonus = 4 + 4 = 8
- [ ] Raises error for invalid skill name

### AC4: Multiclass
- [ ] Single class: total_level = class level
- [ ] Multiclass (Warrior 5, Mage 3): total_level = 8
- [ ] dominant_class returns highest level class
- [ ] add_class increases existing class or adds new

### AC5: Equipment
- [ ] equip_item adds to equipment dict
- [ ] unequip_item removes and returns item ID
- [ ] Raises error for invalid slot

### AC6: Serialization
- [ ] to_dict returns complete character data
- [ ] from_dict reconstructs identical character
- [ ] Round-trip: char == Character.from_dict(char.to_dict())

---

## 5. Test Cases

### TC1: Default Character Creation
```python
def test_default_character():
    char = Character(name="Aldric")
    assert char.name == "Aldric"
    assert char.race == "Human"
    assert char.total_level == 0
    assert char.stats['MIG'] == 10
    assert char.hp == 10
```

### TC2: Custom Character Creation
```python
def test_custom_character():
    char = Character(
        name="Theron",
        race="Elf",
        classes={'Warrior': 5},
        stats={'MIG': 16, 'AGI': 14, 'END': 12, 'MND': 8, 'INS': 10, 'PRE': 13},
        hp=54,
        max_hp=54
    )
    assert char.total_level == 5
    assert char.dominant_class == "Warrior"
    assert char.stat_modifier('MIG') == 3
```

### TC3: Stat Modifiers (Property-Based)
```python
import pytest

@pytest.mark.parametrize("stat,expected", [
    (3, -4), (8, -1), (9, -1), (10, 0), (11, 0),
    (14, 2), (16, 3), (18, 4), (20, 5)
])
def test_stat_modifiers(stat, expected):
    char = Character(name="Test", stats={'MIG': stat})
    assert char.stat_modifier('MIG') == expected
```

### TC4: Skill Bonuses
```python
def test_skill_bonus():
    char = Character(
        name="Rogue",
        stats={'AGI': 16},
        skills={'stealth': 4}  # Expert
    )
    # AGI mod = +3, Expert prof = +4 → total +7
    assert char.skill_bonus('stealth') == 7
```

### TC5: Multiclass
```python
def test_multiclass():
    char = Character(name="Spellblade")
    char.add_class('Warrior', 5)
    char.add_class('Mage', 3)
    
    assert char.total_level == 8
    assert char.dominant_class == 'Warrior'
    assert char.classes == {'Warrior': 5, 'Mage': 3}
    
    char.add_class('Mage', 1)  # Level up Mage
    assert char.classes['Mage'] == 4
```

### TC6: Equipment
```python
def test_equipment():
    char = Character(name="Knight")
    char.equip_item('weapon', 'longsword_001')
    char.equip_item('armor', 'plate_armor_001')
    
    assert char.equipment['weapon'] == 'longsword_001'
    assert char.equipment['armor'] == 'plate_armor_001'
    
    removed = char.unequip_item('weapon')
    assert removed == 'longsword_001'
    assert 'weapon' not in char.equipment
```

### TC7: Serialization
```python
def test_serialization():
    original = Character(
        name="Wizard",
        race="Human",
        classes={'Mage': 10},
        stats={'MIG': 8, 'AGI': 12, 'END': 10, 'MND': 18, 'INS': 14, 'PRE': 13},
        hp=80,
        max_hp=80,
        spell_points=66,
        max_spell_points=66,
        skills={'arcana': 6, 'lore': 4},
        gold=500,
        inventory=['wand_001', 'spellbook_001'],
        equipment={'weapon': 'staff_001', 'accessory': 'ring_001'}
    )
    
    # Serialize
    data = original.to_dict()
    
    # Deserialize
    restored = Character.from_dict(data)
    
    # Verify equality
    assert restored.name == original.name
    assert restored.stats == original.stats
    assert restored.classes == original.classes
    assert restored.equipment == original.equipment
```

### TC8: Invalid Inputs
```python
def test_invalid_stat():
    char = Character(name="Test")
    with pytest.raises(ValueError, match="Unknown stat"):
        char.stat_modifier('INVALID')

def test_invalid_skill():
    char = Character(name="Test")
    with pytest.raises(ValueError, match="Unknown skill"):
        char.skill_bonus('invalid_skill')

def test_invalid_slot():
    char = Character(name="Test")
    with pytest.raises(ValueError, match="Invalid slot"):
        char.equip_item('invalid_slot', 'item')
```

---

## 6. Implementation Plan

1. **Create project structure:**
   ```
   frp-backend/
   ├── engine/
   │   └── core/
   │       ├── __init__.py
   │       └── character.py
   ├── tests/
   │   └── test_character.py
   ├── requirements.txt
   └── pyproject.toml
   ```

2. **Write tests first (TDD):**
   - `test_character.py` with all TC1-TC8
   - Run tests (all fail initially)

3. **Implement Character class:**
   - Basic structure
   - Properties (total_level, dominant_class)
   - Methods (stat_modifier, skill_bonus, etc.)
   - Run tests until all pass

4. **Validation & edge cases:**
   - Add input validation
   - Handle edge cases (empty classes, negative stats)

5. **Documentation:**
   - Docstrings for all methods
   - Type hints verified

---

## 7. Dependencies

**Python Packages:**
- `python >= 3.11`
- `pytest >= 7.0` (testing)
- `pytest-cov` (coverage)

**Internal:**
- None (this is foundation module)

---

## 8. Success Metrics

- [ ] All 8 test cases pass
- [ ] Code coverage ≥ 95%
- [ ] No type errors (mypy clean)
- [ ] Execution time: < 1ms per character creation

---

**Next Step:** Implement `character.py` + `test_character.py` (TDD)

---

## 11. Public API

```python
class Character:
    # Constructor
    def __init__(self, name: str, race: str = "Human", classes: Dict[str, int] = None,
                 stats: Dict[str, int] = None, hp: int = 10, max_hp: int = 10,
                 ac: int = 10, initiative_bonus: int = 0, spell_points: int = 0,
                 max_spell_points: int = 0, skills: Dict[str, int] = None,
                 gold: int = 0, inventory: List[str] = None,
                 equipment: Dict[str, str] = None, conditions: List[str] = None)
    # Raises: nothing (uses defaults for missing fields)

    @property
    def total_level(self) -> int:
        """Sum of all class levels. Returns 0 if no classes."""

    @property
    def dominant_class(self) -> Optional[str]:
        """Class with highest level. Returns None if no classes."""

    def stat_modifier(self, stat: str) -> int:
        """Returns (stat_value - 10) // 2.
        Raises: ValueError if stat not in ('MIG','AGI','END','MND','INS','PRE')."""

    def skill_bonus(self, skill: str) -> int:
        """Returns stat_modifier(governing_stat) + proficiency.
        Raises: ValueError if skill name unknown."""

    def add_class(self, class_name: str, level: int = 1) -> None:
        """Adds or increases class level. level must be >= 1."""

    def equip_item(self, slot: str, item_id: str) -> None:
        """Equips item to slot. Valid slots: weapon, offhand, armor, accessory.
        Raises: ValueError for invalid slot."""

    def unequip_item(self, slot: str) -> Optional[str]:
        """Removes item from slot. Returns item_id or None if slot empty."""

    def to_dict(self) -> dict:
        """Serializes character to JSON-compatible dict."""

    @classmethod
    def from_dict(cls, data: dict) -> 'Character':
        """Deserializes character from dict. Raises: KeyError if required field missing."""
```

---

## 12. Acceptance Criteria (Standard Format)

AC-01 [FR1]: Given `Character(name="Aldric")` is called with only a name, when the object is created, then `race == "Human"`, all stats equal 10, `hp == 10`, and `total_level == 0`.

AC-02 [FR2]: Given a Character with `stats={'MIG': 16}`, when `stat_modifier('MIG')` is called, then the return value is 3. Given `stats={'MIG': 8}`, then the return value is -1.

AC-03 [FR3]: Given a Character with `stats={'AGI': 16}` and `skills={'stealth': 4}`, when `skill_bonus('stealth')` is called, then the result is 7 (AGI mod +3 + Expert +4).

AC-04 [FR4]: Given a Character with classes `{'Warrior': 5, 'Mage': 3}`, when `total_level` is accessed, then it returns 8. When `dominant_class` is accessed, then it returns `"Warrior"`.

AC-05 [FR5]: Given a Character with `hp=0` and `max_hp=20`, when HP is not changed, then `hp` remains 0 (no auto-heal; HP is a plain field with no clamping).

AC-06 [FR6]: Given a Character, when `equip_item('weapon', 'sword_01')` is called, then `equipment['weapon'] == 'sword_01'`. When `unequip_item('weapon')` is called, then the return value is `'sword_01'` and `'weapon'` is no longer in equipment.

AC-07 [FR7]: Given a fully populated Character, when `to_dict()` is called and the result passed to `Character.from_dict()`, then the reconstructed character has identical name, stats, classes, equipment, and skills.

---

## 13. Error Handling

| Condition | Method | Behavior |
|---|---|---|
| Unknown stat name (e.g. `'STR'`) | `stat_modifier()` | Raises `ValueError("Unknown stat: STR")` |
| Unknown skill name | `skill_bonus()` | Raises `ValueError("Unknown skill: <name>")` |
| Invalid equipment slot | `equip_item()` | Raises `ValueError("Invalid slot: <slot>")` |
| Missing required key in dict | `from_dict()` | Raises `KeyError` (dataclass default behavior) |
| `add_class()` with level ≤ 0 | `add_class()` | Should raise `ValueError("level must be >= 1")` |
| Stat value outside 3-20 range | `__init__` | No validation in MVP; consumers responsible for range checks |

---

## 14. Test Coverage Target

- **Target:** ≥ 95% line coverage
- **Must cover:** every branch of `stat_modifier`, `skill_bonus`, `equip_item`, `from_dict`
- **Property-based:** `stat_modifier` tested for all values 3–20 (parametrize)
- **Error paths:** each `ValueError` branch must have at least one test
- **Serialization:** round-trip test with all fields populated

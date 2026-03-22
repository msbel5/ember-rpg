# PRD: Magic System (Module 4)
**Project:** Ember RPG — FRP AI Game  
**Module:** Phase 2, Module 4  
**Author:** Alcyone  
**Date:** 2026-03-22  
**Status:** Draft → Implementation

---

## 1. Overview

**Purpose:** Implement spell system with spell points, spell casting, and spell effects integration.

**Scope:**
- Spell class (name, cost, range, effects)
- Spell casting action (2 AP, spell point cost)
- Spell database (JSON format)
- Spell slots vs spell points (GDD: spell points)
- Spell targeting (self, single, area)
- Spell resistance/saving throws

**Out of Scope (other modules):**
- AI spell selection (Module 6)
- Spell crafting (Phase 7)
- Multi-target spells (Phase 3 with map system)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR1: Spell Definition**
- Spell has: name, cost (spell points), range, target type, effects
- Target types: self, single, area (future)
- Effects reuse existing Effect system (Heal, Damage, Buff)

**FR2: Spell Casting**
- Cast spell costs 2 AP (GDD rule)
- Costs spell points from caster
- Fails if insufficient spell points
- Applies effects to target(s)

**FR3: Spell Point Management**
- Characters have current/max spell points
- Spell points restore on rest (future)
- Classes determine max spell points (Mage high, Warrior low)

**FR4: Spell Database**
- JSON file with spell definitions
- Load spells from file
- Search spells by name, level, school

**FR5: Spell Schools** (flavor)
- Evocation (damage), Abjuration (defense), Transmutation (buffs), Necromancy (debuffs), Conjuration (summons - future)

**FR6: Saving Throws** (future enhancement)
- Target makes stat check to resist
- Partial damage on success

### 2.2 Non-Functional Requirements

**NFR1: Performance**
- Spell casting: < 5ms
- Spell database load: < 100ms

**NFR2: Testability**
- 100% unit test coverage for Spell class

**NFR3: Extensibility**
- Easy to add new spells via JSON

---

## 3. Data Model

### 3.1 Spell Class

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class SpellSchool(Enum):
    """Spell schools for flavor/categorization."""
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
    AREA = "area"  # Future

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
        level: Spell tier (1-9, future for progression)
    """
    name: str
    cost: int  # Spell points
    range: int  # Feet
    target_type: TargetType
    effects: List['Effect'] = field(default_factory=list)
    school: SpellSchool = SpellSchool.EVOCATION
    description: str = ""
    level: int = 1  # Future: spell progression
    
    def can_cast(self, caster: 'Character') -> bool:
        """Check if caster has enough spell points."""
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
        """Deserialize spell from dictionary."""
        from engine.core.effect import Effect
        
        data['target_type'] = TargetType(data['target_type'])
        data['school'] = SpellSchool(data['school'])
        data['effects'] = [Effect.from_dict(e) for e in data.get('effects', [])]
        
        return cls(**data)
```

### 3.2 Spell Database

```python
import json
from typing import List, Optional

class SpellDatabase:
    """Load and manage spell definitions from JSON."""
    
    def __init__(self, filepath: str):
        self.spells: List[Spell] = []
        self.load(filepath)
    
    def load(self, filepath: str):
        """Load spells from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        for spell_data in data['spells']:
            spell = Spell.from_dict(spell_data)
            self.spells.append(spell)
    
    def get(self, name: str) -> Optional[Spell]:
        """Get spell by name."""
        for spell in self.spells:
            if spell.name.lower() == name.lower():
                return spell
        return None
    
    def filter(self, school: Optional[SpellSchool] = None, 
               max_cost: Optional[int] = None,
               max_level: Optional[int] = None) -> List[Spell]:
        """Filter spells by criteria."""
        results = self.spells
        
        if school:
            results = [s for s in results if s.school == school]
        if max_cost:
            results = [s for s in results if s.cost <= max_cost]
        if max_level:
            results = [s for s in results if s.level <= max_level]
        
        return results
```

### 3.3 Combat Integration

```python
# In CombatManager class:

def cast_spell(self, spell: Spell, target_index: Optional[int] = None) -> dict:
    """
    Cast a spell during combat.
    
    Args:
        spell: Spell to cast
        target_index: Index of target combatant (for single-target spells)
    
    Returns:
        Spell casting result
    """
    caster = self.active_combatant
    
    # Check AP
    if caster.ap < 2:
        return {"error": "Insufficient AP (casting costs 2 AP)"}
    
    # Get target
    target = None
    if spell.target_type == TargetType.SINGLE:
        if target_index is None:
            return {"error": "Single-target spell requires target"}
        target = self.combatants[target_index].character
    
    # Cast spell
    try:
        result = spell.cast(caster.character, target)
        caster.ap -= 2  # Deduct AP after successful cast
        self._log_event("spell_cast", result)
        return result
    except ValueError as e:
        return {"error": str(e)}
```

---

## 4. Acceptance Criteria

### AC1: Spell Creation
- [ ] Can create spell with name, cost, range, effects
- [ ] Target type validation (self, single, area)
- [ ] School and level metadata

### AC2: Spell Casting
- [ ] Casting deducts spell points
- [ ] Fails if insufficient spell points
- [ ] Applies effects to correct target
- [ ] Self-target spells don't require target parameter

### AC3: Combat Integration
- [ ] cast_spell action costs 2 AP
- [ ] Spell effects logged to combat log
- [ ] Target validation for single-target spells

### AC4: Spell Database
- [ ] Load spells from JSON
- [ ] Get spell by name
- [ ] Filter by school/cost/level

### AC5: Serialization
- [ ] Spell to_dict/from_dict round-trip
- [ ] Effects serialize correctly

---

## 5. Test Cases

### TC1: Spell Creation
```python
def test_fireball_spell():
    fireball = Spell(
        name="Fireball",
        cost=5,
        range=60,
        target_type=TargetType.SINGLE,
        effects=[DamageEffect(amount="3d6", damage_type="fire")],
        school=SpellSchool.EVOCATION,
        level=3
    )
    assert fireball.name == "Fireball"
    assert fireball.cost == 5
    assert fireball.target_type == TargetType.SINGLE
```

### TC2: Self-Buff Spell
```python
def test_self_buff_spell():
    shield = Spell(
        name="Shield",
        cost=2,
        range=0,
        target_type=TargetType.SELF,
        effects=[BuffEffect(stat="END", bonus=4, duration=10)]
    )
    
    caster = Character(name="Mage", spell_points=10, max_spell_points=10)
    result = shield.cast(caster)
    
    assert caster.spell_points == 8  # Cost 2
    assert caster.stats['END'] == 14  # 10 + 4
```

### TC3: Damage Spell
```python
def test_damage_spell():
    magic_missile = Spell(
        name="Magic Missile",
        cost=3,
        range=120,
        target_type=TargetType.SINGLE,
        effects=[DamageEffect(amount="2d4+2", damage_type="force")]
    )
    
    caster = Character(name="Wizard", spell_points=10, max_spell_points=10)
    target = Character(name="Orc", hp=20, max_hp=20)
    
    result = magic_missile.cast(caster, target)
    
    assert caster.spell_points == 7  # 10 - 3
    assert target.hp < 20  # Damaged
```

### TC4: Insufficient Spell Points
```python
def test_insufficient_spell_points():
    expensive_spell = Spell(
        name="Meteor Swarm",
        cost=20,
        range=240,
        target_type=TargetType.AREA,
        effects=[DamageEffect(amount="10d6", damage_type="fire")]
    )
    
    caster = Character(name="Weak Mage", spell_points=5, max_spell_points=10)
    
    with pytest.raises(ValueError, match="Insufficient spell points"):
        expensive_spell.cast(caster)
```

### TC5: Combat Spell Casting
```python
def test_combat_spell_casting():
    mage = Character(name="Mage", spell_points=10, max_spell_points=10)
    warrior = Character(name="Warrior", hp=50, max_hp=50)
    
    shock = Spell(
        name="Shocking Grasp",
        cost=2,
        range=5,
        target_type=TargetType.SINGLE,
        effects=[DamageEffect(amount="2d8", damage_type="lightning")]
    )
    
    combat = CombatManager([mage, warrior], seed=1)
    combat.start_turn()
    
    # Find warrior index
    warrior_idx = next(i for i, c in enumerate(combat.combatants) if c.name == "Warrior")
    
    result = combat.cast_spell(shock, target_index=warrior_idx)
    
    assert 'effects' in result
    assert combat.active_combatant.ap == 1  # 3 - 2
    assert mage.spell_points == 8  # 10 - 2
```

### TC6: Spell Database
```python
def test_spell_database_load():
    db = SpellDatabase("data/spells.json")
    
    fireball = db.get("Fireball")
    assert fireball is not None
    assert fireball.school == SpellSchool.EVOCATION
    
    evocation_spells = db.filter(school=SpellSchool.EVOCATION)
    assert len(evocation_spells) > 0
```

---

## 6. Sample Spell Database (JSON)

```json
{
  "spells": [
    {
      "name": "Fireball",
      "cost": 5,
      "range": 60,
      "target_type": "single",
      "school": "evocation",
      "level": 3,
      "description": "A bright streak flashes to a point you choose, exploding in a roar of flame.",
      "effects": [
        {"type": "damage", "amount": "3d6", "damage_type": "fire"}
      ]
    },
    {
      "name": "Cure Wounds",
      "cost": 2,
      "range": 5,
      "target_type": "single",
      "school": "abjuration",
      "level": 1,
      "description": "You touch a creature, channeling healing energy.",
      "effects": [
        {"type": "heal", "amount": "2d8+2"}
      ]
    },
    {
      "name": "Shield",
      "cost": 2,
      "range": 0,
      "target_type": "self",
      "school": "abjuration",
      "level": 1,
      "description": "An invisible barrier of magical force protects you.",
      "effects": [
        {"type": "buff", "stat": "END", "bonus": 4, "duration": 10}
      ]
    }
  ]
}
```

---

## 7. Implementation Plan

1. **Create Spell class** (spell.py)
2. **Integrate with combat** (add cast_spell to CombatManager)
3. **Create SpellDatabase** (spell_db.py)
4. **Write sample spells JSON** (data/spells.json)
5. **Write comprehensive tests** (TC1-TC6)

---

## 8. Dependencies

**Internal:**
- `engine.core.character` (Module 1)
- `engine.core.effect` (Module 2)
- `engine.core.combat` (Module 3)

---

## 9. Success Metrics

- [ ] All 6 test cases pass
- [ ] Code coverage ≥ 95%
- [ ] Spell database loads < 100ms
- [ ] 10+ sample spells in JSON

---

**Next Step:** Implement `spell.py` + tests (TDD approach)

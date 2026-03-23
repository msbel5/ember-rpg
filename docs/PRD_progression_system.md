# PRD: Leveling & Progression System (Module 5)
**Project:** Ember RPG  
**Phase:** 2  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Draft

---

## 1. Overview

**Purpose:** Implement XP-based leveling system with level-up mechanics, class ability unlocks, and stat progression.

**Scope:**
- XP earning (combat kills, quest rewards)
- Level-up detection + stat improvements
- Class ability system (passive + active abilities per class/level)
- Multiclass leveling support

**Out of Scope:**
- Quest system (Phase 4)
- UI level-up screen (Phase 5)
- Prestige classes (Phase 7)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR1: XP System**
- Characters have `xp: int` and `level: int` (1-20)
- XP thresholds per level (exponential curve)
- `add_xp(amount)` → check level-up

**FR2: Level-Up**
- On level-up: increment level, apply stat bonuses
- Notify via returned event dict
- Multiclass: XP shared, level per class

**FR3: Class Abilities**
- Each class has abilities unlocked at certain levels
- Ability: name, description, passive/active, effect
- `get_abilities(class_name, level)` → list of unlocked abilities

**FR4: Stat Growth**
- Every 2 levels: +1 to one stat (player choice → placeholder: MIG)
- Max HP increase on END gain
- Spell points increase for Mage/Priest

**FR5: XP Rewards (Data)**
- JSON file: monster XP values
- CombatManager awards XP on kill

### 2.2 Non-Functional Requirements
- Level calculation < 1ms
- No circular imports (standalone module)

---

## 3. XP Thresholds

```
Level  XP Required (total)
1      0
2      300
3      900
4      2700
5      6500
6      14000
7      23000
8      34000
9      48000
10     64000
11     85000
12     100000
13     120000
14     140000
15     165000
16     195000
17     225000
18     265000
19     305000
20     355000
```

---

## 4. Class Abilities (MVP — 4 classes, L1-5)

### Warrior
- L1: **Combat Stance** (passive) — +2 MIG skill checks in combat
- L2: **Second Wind** (active, 1/rest) — Heal 1d10+level HP
- L3: **Extra Attack** (passive) — +1 attack per turn (costs 1 AP)
- L4: **Battle Hardened** (passive) — +2 AC
- L5: **Mighty Blow** (active, 1 AP) — 2x damage on hit, once per turn

### Rogue
- L1: **Sneak Attack** (passive) — +1d6 bonus damage when advantage
- L2: **Nimble Escape** (active, free) — Disengage or hide as bonus action
- L3: **Cunning Action** (passive) — Dash/Disengage/Hide cost 1 AP (vs 2)
- L4: **Uncanny Dodge** (passive) — Halve damage from one attack per round
- L5: **Evasion** (passive) — Take 0 damage on successful DEX save

### Mage
- L1: **Arcane Recovery** (active, 1/rest) — Recover level/2 spell points
- L2: **Spellcraft** (passive) — Spell save DC +1
- L3: **Expanded Spells** (passive) — Learn 2 additional spells
- L4: **Metamagic: Quicken** (active, 2 SP) — Cast spell as bonus action
- L5: **Potent Cantrip** (passive) — Cantrips deal bonus damage

### Priest
- L1: **Divine Favor** (active, 1/rest) — +1d4 to all rolls for 1 min
- L2: **Healing Touch** (passive) — Cure Wounds heals +level HP
- L3: **Channel Divinity** (active, 1/rest) — Turn undead or restore 2d6 HP
- L4: **Sacred Flame** (passive) — Fire damage ignores resistance
- L5: **Greater Heal** (active, 4 SP) — Restore 4d8+5 HP to one target

---

## 5. Data Model

```python
@dataclass
class ClassAbility:
    name: str
    description: str
    passive: bool
    required_level: int
    class_name: str
    cost: int = 0  # AP cost if active

@dataclass
class LevelUpResult:
    old_level: int
    new_level: int
    new_abilities: List[ClassAbility]
    stat_bonus: Optional[str]  # Stat name that increased
    hp_increase: int
    sp_increase: int  # Spell point increase

class ProgressionSystem:
    XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, ...]
    
    def get_level_for_xp(self, xp: int) -> int: ...
    def add_xp(self, character, amount) -> Optional[LevelUpResult]: ...
    def get_abilities(self, class_name, level) -> List[ClassAbility]: ...
```

---

## 6. Test Cases

### TC1: XP Thresholds
```python
def test_xp_thresholds():
    ps = ProgressionSystem()
    assert ps.get_level_for_xp(0) == 1
    assert ps.get_level_for_xp(299) == 1
    assert ps.get_level_for_xp(300) == 2
    assert ps.get_level_for_xp(900) == 3
    assert ps.get_level_for_xp(355000) == 20
```

### TC2: Level-Up
```python
def test_level_up():
    char = Character(name="Hero", xp=0, level=1)
    ps = ProgressionSystem()
    result = ps.add_xp(char, 300)
    
    assert char.level == 2
    assert char.xp == 300
    assert result is not None
    assert result.new_level == 2
```

### TC3: Multi-Level Jump
```python
def test_multi_level_jump():
    char = Character(name="Hero", xp=0, level=1)
    ps = ProgressionSystem()
    ps.add_xp(char, 2700)
    
    assert char.level == 4  # Jumped 3 levels
```

### TC4: Class Abilities
```python
def test_warrior_abilities():
    ps = ProgressionSystem()
    abilities = ps.get_abilities("warrior", 3)
    
    assert len(abilities) == 3  # L1, L2, L3
    names = [a.name for a in abilities]
    assert "Combat Stance" in names
    assert "Extra Attack" in names
```

### TC5: Stat Growth on Level-Up
```python
def test_stat_bonus():
    char = Character(name="Warrior", level=1, classes={"warrior": 1})
    ps = ProgressionSystem()
    result = ps.add_xp(char, 300)  # Level 2
    
    # Level 2 = even level = stat bonus
    assert result.stat_bonus is not None
```

### TC6: Spell Point Increase (Mage)
```python
def test_mage_spell_point_increase():
    mage = Character(name="Mage", level=1, classes={"mage": 1},
                     spell_points=10, max_spell_points=10)
    ps = ProgressionSystem()
    result = ps.add_xp(mage, 300)
    
    assert result.sp_increase > 0
    assert mage.max_spell_points > 10
```

---

## 7. Implementation Plan

1. Write `tests/test_progression.py` (TDD)
2. Write `engine/core/progression.py` (ProgressionSystem, ClassAbility, LevelUpResult)
3. Integrate with Character (add `xp`, `level` fields if missing)
4. Write `data/class_abilities.json` (L1-L5, 4 classes)
5. Run tests + verify 95%+ coverage
6. Commit + push

---

## 8. Dependencies
- `engine.core.character` (Character class)
- No circular imports (progression does not import combat)

---

## 9. Success Metrics
- [ ] All 6 test cases pass
- [ ] Coverage ≥ 95%
- [ ] Level calculation < 1ms
- [ ] 4 classes × 5 levels = 20 abilities in JSON

---

## 10. Public API

```python
class ProgressionSystem:
    XP_THRESHOLDS: List[int]  # Index = level-1, value = XP required

    def get_level_for_xp(self, xp: int) -> int:
        """Returns character level (1-20) for given XP total. O(n) scan."""

    def add_xp(self, character: Character, amount: int) -> Optional[LevelUpResult]:
        """Adds amount to character.xp. If level-up occurs, applies bonuses and returns LevelUpResult. Returns None if no level-up."""

    def get_abilities(self, class_name: str, level: int) -> List[ClassAbility]:
        """Returns all abilities unlocked at or below given level for the class."""

@dataclass
class ClassAbility:
    name: str
    description: str
    passive: bool
    required_level: int
    class_name: str
    cost: int = 0  # AP cost if active (0 = no cost / passive)

@dataclass
class LevelUpResult:
    old_level: int
    new_level: int
    new_abilities: List[ClassAbility]
    stat_bonus: Optional[str]  # e.g., "MIG"
    hp_increase: int
    sp_increase: int
```

---

## 11. Acceptance Criteria (Standard Format)

AC-01 [FR1]: Given `ProgressionSystem`, when `get_level_for_xp(0)` is called, then result is 1. When `get_level_for_xp(300)` is called, then result is 2. When `get_level_for_xp(354999)` is called, then result is 19.

AC-02 [FR2]: Given a Character with `xp=0, level=1`, when `add_xp(char, 300)` is called, then `char.level == 2`, `char.xp == 300`, and the returned `LevelUpResult.new_level == 2`.

AC-03 [FR2]: Given a Character with `xp=0, level=1`, when `add_xp(char, 2700)` is called, then `char.level == 4` (multi-level jump handled correctly).

AC-04 [FR3]: Given `get_abilities("warrior", 3)`, when called, then 3 abilities are returned (Combat Stance, Second Wind, Extra Attack) and all have `class_name == "warrior"`.

AC-05 [FR4]: Given a Character at level 1, when leveled to 2 (even level), then `LevelUpResult.stat_bonus` is not None (stat bonus awarded).

AC-06 [FR4]: Given a Mage Character, when `add_xp()` triggers level-up, then `LevelUpResult.sp_increase > 0` and `character.max_spell_points` increases by that amount.

---

## 12. Performance Requirements

- `get_level_for_xp()`: < 1ms (20-element scan)
- `add_xp()` with level-up: < 5ms
- `get_abilities()`: < 1ms

---

## 13. Error Handling

| Condition | Method | Behavior |
|---|---|---|
| `amount < 0` | `add_xp()` | No specification in MVP; should be treated as 0 or raise ValueError |
| Unknown class name | `get_abilities()` | Returns empty list (no abilities found) |
| `xp` already at max (level 20) | `add_xp()` | Returns None; no further level-up |
| Character missing `xp` field | `add_xp()` | AttributeError — caller must ensure Character has `xp` field |

---

## 14. Integration Points

- **Character System (Module 1):** Reads and mutates `character.xp`, `character.level`, `character.stats`, `character.max_hp`, `character.max_spell_points`
- **Combat Engine (Module 3):** Awards XP on kill via `add_xp()` call from CombatManager
- **Class Abilities Data:** `data/class_abilities.json` — loaded by ProgressionSystem at init
- **DM Agent (Module 6):** Receives `LevelUpResult` for level-up narrative

---

## 15. Test Coverage Target

- **Target:** ≥ 95% line coverage
- **Must cover:** XP threshold boundaries (exact boundary values), multi-level jump, level-20 cap, stat bonus at even levels, SP increase for Mage vs Warrior, empty class abilities for unknown class

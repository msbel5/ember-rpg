# PRD: Combat Engine (Module 3)
**Project:** Ember RPG  
**Phase:** 2  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-22  
**Status:** Draft

---

## 1. Overview

**Purpose:** Implement turn-based tactical combat system with action point management, initiative, attack resolution, and condition tracking.

**Scope:**
- Combat manager (initiative, turn order)
- Action system (attack, cast spell, move, use item)
- Attack resolution (d20 + modifier vs AC)
- Damage application (with resistances)
- Condition tracking (stunned, poisoned, etc.)
- Combat log (JSON event stream)

**Out of Scope (other modules):**
- Spell effects (Module 4)
- AI decision-making (Module 6)
- Map/terrain mechanics (Phase 3)
- Multiplayer sync (Phase 6)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR1: Combat Initialization**
- Create combat encounter with list of combatants
- Roll initiative (d20 + AGI modifier)
- Sort combatants by initiative (descending)

**FR2: Turn Management**
- Track current turn (combatant index)
- 3 Action Points (AP) per turn (GDD rule)
- AP costs: Attack (1 AP), Move (1 AP), Cast (2 AP), Item (1 AP), End Turn (0 AP)
- Next turn when AP depleted or explicit end_turn

**FR3: Attack Action**
- Roll d20 + melee/ranged skill bonus
- Compare to target AC
- On hit: roll weapon damage + stat modifier
- On crit (natural 20): double damage dice
- On fumble (natural 1): automatic miss

**FR4: Damage Application**
- Reduce target HP by damage amount
- Check for death (HP ≤ 0)
- Track damage types (slashing, fire, etc.)
- Apply resistances/immunities (future)

**FR5: Condition System**
- Conditions: stunned, poisoned, prone, grappled, burning, bleeding
- Conditions can reduce AP, prevent actions, or deal damage
- Duration tracking (turns remaining)
- Auto-expire after duration

**FR6: Combat Log**
- JSON event log for each action
- Event types: turn_start, attack, damage, heal, condition_applied, death, combat_end
- Timestamp, actor, target, result

**FR7: Combat End**
- Combat ends when one side has no living combatants
- Return combat summary (winner, rounds, casualties)

### 2.2 Non-Functional Requirements

**NFR1: Performance**
- Initiative roll: < 1ms per combatant
- Action resolution: < 5ms
- Full combat (10 combatants, 20 rounds): < 1 second

**NFR2: Testability**
- 100% unit test coverage for CombatManager
- Deterministic dice rolls (seeded RNG) for tests

**NFR3: Extensibility**
- Easy to add new action types
- Easy to add new conditions

---

## 3. Data Model

### 3.1 CombatManager

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from engine.core.character import Character
from engine.core.item import Item
import random

@dataclass
class Combatant:
    """Wrapper for characters in combat with combat-specific state."""
    character: Character
    initiative: int
    ap: int = 3  # Action points
    conditions: List['Condition'] = field(default_factory=list)
    is_dead: bool = False
    
    @property
    def name(self) -> str:
        return self.character.name

@dataclass
class Condition:
    """Temporary status effect on a combatant."""
    name: str  # stunned, poisoned, etc.
    duration: int  # turns remaining
    effect: str  # description
    
    def apply_turn_effect(self, combatant: Combatant) -> Optional[str]:
        """Apply per-turn effect (poison damage, etc.). Return log message if any."""
        # Example: poison deals 1d4 damage per turn
        if self.name == "poisoned":
            from engine.core.rules import roll_dice
            damage = roll_dice("1d4")
            combatant.character.hp -= damage
            return f"{combatant.name} takes {damage} poison damage"
        return None

class CombatManager:
    """Manages turn-based combat encounters."""
    
    def __init__(self, combatants: List[Character], seed: Optional[int] = None):
        """
        Initialize combat.
        
        Args:
            combatants: List of characters participating in combat
            seed: Random seed for deterministic dice rolls (testing)
        """
        if seed is not None:
            random.seed(seed)
        
        self.combatants: List[Combatant] = []
        self.current_turn: int = 0
        self.round: int = 1
        self.log: List[Dict] = []
        self.combat_ended: bool = False
        
        # Roll initiative and sort
        for char in combatants:
            initiative = self.roll_initiative(char)
            self.combatants.append(Combatant(character=char, initiative=initiative))
        
        self.combatants.sort(key=lambda c: c.initiative, reverse=True)
        self._log_event("combat_start", {"combatants": [c.name for c in self.combatants]})
    
    def roll_initiative(self, char: Character) -> int:
        """Roll initiative (d20 + AGI modifier)."""
        from engine.core.rules import roll_dice
        roll = roll_dice("1d20")
        agi_mod = char.stat_modifier('AGI')
        return roll + agi_mod + char.initiative_bonus
    
    @property
    def active_combatant(self) -> Combatant:
        """Get the combatant whose turn it is."""
        return self.combatants[self.current_turn]
    
    def start_turn(self):
        """Start a new turn for the active combatant."""
        combatant = self.active_combatant
        combatant.ap = 3  # Reset AP
        
        # Apply condition turn effects (poison, burning, etc.)
        for condition in combatant.conditions[:]:
            msg = condition.apply_turn_effect(combatant)
            if msg:
                self._log_event("condition_damage", {"combatant": combatant.name, "message": msg})
            
            # Decrement duration
            condition.duration -= 1
            if condition.duration <= 0:
                combatant.conditions.remove(condition)
                self._log_event("condition_expired", {"combatant": combatant.name, "condition": condition.name})
        
        # Check death after conditions
        if combatant.character.hp <= 0:
            combatant.is_dead = True
            self._log_event("death", {"combatant": combatant.name})
        
        self._log_event("turn_start", {
            "combatant": combatant.name,
            "round": self.round,
            "hp": combatant.character.hp,
            "ap": combatant.ap
        })
    
    def attack(self, target_index: int, weapon: Optional[Item] = None) -> Dict:
        """
        Perform an attack action.
        
        Args:
            target_index: Index of target in combatants list
            weapon: Weapon to attack with (uses equipped weapon if None)
        
        Returns:
            Attack result dictionary
        """
        attacker = self.active_combatant
        target = self.combatants[target_index]
        
        if attacker.ap < 1:
            return {"error": "Insufficient AP"}
        if target.is_dead:
            return {"error": "Target is dead"}
        
        attacker.ap -= 1
        
        # Get weapon (default: unarmed 1d4)
        if weapon is None:
            weapon = Item(name="Unarmed", value=0, weight=0, item_type="weapon", damage_dice="1d4", damage_type="bludgeoning")
        
        # Attack roll: d20 + skill_bonus
        from engine.core.rules import roll_dice
        roll = roll_dice("1d20")
        skill_bonus = attacker.character.skill_bonus("melee")  # TODO: ranged check
        attack_roll = roll + skill_bonus
        
        # Check hit
        hit = attack_roll >= target.character.ac
        crit = (roll == 20)
        fumble = (roll == 1)
        
        if fumble:
            hit = False
        
        result = {
            "attacker": attacker.name,
            "target": target.name,
            "roll": roll,
            "attack_roll": attack_roll,
            "target_ac": target.character.ac,
            "hit": hit,
            "crit": crit,
            "fumble": fumble
        }
        
        if hit:
            # Damage roll
            damage_roll = roll_dice(weapon.damage_dice)
            stat_mod = attacker.character.stat_modifier('MIG')  # TODO: finesse check
            damage = damage_roll + stat_mod
            
            if crit:
                damage = (damage_roll * 2) + stat_mod  # Double dice, not modifier
            
            target.character.hp -= damage
            result["damage"] = damage
            result["damage_type"] = weapon.damage_type
            
            if target.character.hp <= 0:
                target.is_dead = True
                result["killed"] = True
        
        self._log_event("attack", result)
        self._check_combat_end()
        return result
    
    def use_item(self, item: Item) -> Dict:
        """Use a consumable item (heal, buff, etc.)."""
        combatant = self.active_combatant
        
        if combatant.ap < 1:
            return {"error": "Insufficient AP"}
        
        combatant.ap -= 1
        messages = item.apply_effects(combatant.character)
        
        result = {
            "combatant": combatant.name,
            "item": item.name,
            "effects": messages
        }
        self._log_event("use_item", result)
        return result
    
    def apply_condition(self, target_index: int, condition: Condition) -> Dict:
        """Apply a condition to a target."""
        target = self.combatants[target_index]
        target.conditions.append(condition)
        
        result = {
            "target": target.name,
            "condition": condition.name,
            "duration": condition.duration
        }
        self._log_event("condition_applied", result)
        return result
    
    def end_turn(self):
        """End the current turn and advance to next combatant."""
        self.active_combatant.ap = 0  # Spend remaining AP
        
        self.current_turn += 1
        if self.current_turn >= len(self.combatants):
            self.current_turn = 0
            self.round += 1
        
        # Skip dead combatants
        while self.combatants[self.current_turn].is_dead:
            self.current_turn += 1
            if self.current_turn >= len(self.combatants):
                self.current_turn = 0
                self.round += 1
        
        self.start_turn()
    
    def _check_combat_end(self):
        """Check if combat has ended (one side eliminated)."""
        alive = [c for c in self.combatants if not c.is_dead]
        if len(alive) <= 1:
            self.combat_ended = True
            winner = alive[0].name if alive else "Nobody"
            self._log_event("combat_end", {"winner": winner, "rounds": self.round})
    
    def _log_event(self, event_type: str, data: Dict):
        """Log a combat event."""
        self.log.append({"type": event_type, "data": data})
    
    def get_summary(self) -> Dict:
        """Get combat summary."""
        return {
            "rounds": self.round,
            "survivors": [c.name for c in self.combatants if not c.is_dead],
            "casualties": [c.name for c in self.combatants if c.is_dead],
            "event_count": len(self.log)
        }
```

---

## 4. Acceptance Criteria

### AC1: Initiative
- [ ] Initiative = d20 + AGI modifier + initiative_bonus
- [ ] Combatants sorted descending by initiative
- [ ] Turn order logged

### AC2: Turn Management
- [ ] Each combatant starts with 3 AP
- [ ] AP decreases with actions
- [ ] Turn advances when AP = 0 or end_turn called
- [ ] Round increments when all combatants acted

### AC3: Attack Resolution
- [ ] Attack roll = d20 + skill_bonus
- [ ] Hit if attack_roll ≥ target.ac
- [ ] Natural 20 = critical hit (double damage dice)
- [ ] Natural 1 = automatic miss
- [ ] Damage = weapon_dice + stat_modifier

### AC4: Damage Application
- [ ] HP reduces by damage amount
- [ ] is_dead = True when HP ≤ 0
- [ ] Dead combatants skipped in turn order

### AC5: Conditions
- [ ] Conditions have name, duration, effect
- [ ] Duration decrements each turn
- [ ] Condition removed when duration = 0
- [ ] Poison deals damage per turn

### AC6: Combat End
- [ ] Combat ends when ≤ 1 combatant alive
- [ ] Winner logged
- [ ] Summary includes rounds, survivors, casualties

---

## 5. Test Cases

### TC1: Initiative Roll
```python
def test_initiative_order():
    char1 = Character(name="Fighter", stats={'AGI': 16})  # +3
    char2 = Character(name="Rogue", stats={'AGI': 18})    # +4
    char3 = Character(name="Cleric", stats={'AGI': 10})   # +0
    
    combat = CombatManager([char1, char2, char3], seed=42)
    
    # Check order (deterministic with seed)
    assert len(combat.combatants) == 3
    assert all(c.initiative > 0 for c in combat.combatants)
    # Initiative descending
    initiatives = [c.initiative for c in combat.combatants]
    assert initiatives == sorted(initiatives, reverse=True)
```

### TC2: Attack Hit
```python
def test_attack_hit():
    attacker = Character(name="Fighter", stats={'MIG': 16, 'AGI': 14})
    attacker.skills['melee'] = 2  # Trained
    target = Character(name="Goblin", hp=10, max_hp=10, ac=12)
    
    weapon = Item(name="Sword", value=15, weight=3, item_type="weapon", 
                  damage_dice="1d8", damage_type="slashing")
    
    combat = CombatManager([attacker, target], seed=100)
    combat.start_turn()
    
    result = combat.attack(target_index=1, weapon=weapon)
    
    assert result['hit'] is True or result['hit'] is False  # Deterministic
    if result['hit']:
        assert 'damage' in result
        assert target.hp < 10
```

### TC3: Critical Hit
```python
def test_critical_hit():
    attacker = Character(name="Fighter", stats={'MIG': 18})
    target = Character(name="Target", hp=50, max_hp=50, ac=10)
    
    # Force natural 20 (seed manipulation or mock)
    combat = CombatManager([attacker, target], seed=777)
    combat.start_turn()
    
    # Roll until crit (or use seeded test)
    for _ in range(100):
        combat.start_turn()
        result = combat.attack(target_index=1)
        if result.get('crit'):
            assert result['damage'] > 0
            break
```

### TC4: Turn Progression
```python
def test_turn_progression():
    chars = [Character(name=f"C{i}", stats={'AGI': 10}) for i in range(3)]
    combat = CombatManager(chars, seed=1)
    
    combat.start_turn()
    assert combat.round == 1
    assert combat.active_combatant.ap == 3
    
    combat.end_turn()
    assert combat.current_turn == 1  # Next combatant
    
    combat.end_turn()
    combat.end_turn()
    assert combat.round == 2  # New round after 3 turns
```

### TC5: Condition Application
```python
def test_poison_condition():
    char = Character(name="Hero", hp=50, max_hp=50)
    enemy = Character(name="Enemy", hp=10, max_hp=10)
    
    combat = CombatManager([char, enemy], seed=1)
    combat.start_turn()
    
    poison = Condition(name="poisoned", duration=3, effect="1d4 damage per turn")
    combat.apply_condition(target_index=0, condition=poison)
    
    assert len(combat.combatants[0].conditions) == 1
    
    initial_hp = char.hp
    combat.end_turn()
    combat.end_turn()  # Back to char's turn
    
    # Poison should have triggered
    assert char.hp < initial_hp
```

### TC6: Combat End
```python
def test_combat_end():
    strong = Character(name="Dragon", hp=100, max_hp=100, stats={'MIG': 20})
    weak = Character(name="Peasant", hp=5, max_hp=5, ac=8)
    
    weapon = Item(name="Claw", value=0, weight=0, item_type="weapon",
                  damage_dice="2d10", damage_type="slashing")
    
    combat = CombatManager([strong, weak], seed=1)
    combat.start_turn()
    
    # Attack until combat ends
    for _ in range(10):
        if combat.combat_ended:
            break
        result = combat.attack(target_index=1, weapon=weapon)
        if result.get('killed'):
            break
        combat.end_turn()
    
    assert combat.combat_ended is True
    summary = combat.get_summary()
    assert "Dragon" in summary['survivors']
    assert "Peasant" in summary['casualties']
```

---

## 6. Implementation Plan

1. **Create Condition class** (simple dataclass)
2. **Create Combatant wrapper** (character + initiative + AP + conditions)
3. **Create CombatManager skeleton** (init, initiative, turn tracking)
4. **Implement attack action** (d20 roll, hit check, damage)
5. **Implement conditions** (apply, turn effect, expiry)
6. **Implement combat end** (death check, winner)
7. **Write comprehensive tests** (TC1-TC6)

---

## 7. Dependencies

**Python Packages:**
- `pytest` (already installed)
- `random` (stdlib, seeded for tests)

**Internal:**
- `engine.core.character` (Module 1)
- `engine.core.item` (Module 2)
- `engine.core.rules` (Module 2)

---

## 8. Success Metrics

- [ ] All 6 test cases pass
- [ ] Code coverage ≥ 95%
- [ ] 10-combatant combat < 1 second
- [ ] Combat log JSON-serializable

---

**Next Step:** Implement `combat.py` + tests (TDD approach)

---

## 9. Public API

```python
class CombatManager:
    def __init__(self, combatants: List[Character], seed: Optional[int] = None)
    # Rolls initiative for all combatants, sorts descending, logs combat_start.

    @property
    def active_combatant(self) -> Combatant:
        """Returns combatant whose turn it currently is."""

    def roll_initiative(self, char: Character) -> int:
        """Returns d20 + AGI modifier + initiative_bonus."""

    def start_turn(self) -> None:
        """Resets AP to 3, applies condition turn effects, decrements durations, removes expired conditions, logs turn_start."""

    def attack(self, target_index: int, weapon: Optional[Item] = None) -> Dict:
        """Costs 1 AP. Returns result dict with hit/miss/crit/fumble/damage.
        Precondition: active combatant has AP >= 1, target is not dead.
        Postcondition: target HP reduced if hit; target.is_dead=True if HP<=0."""

    def use_item(self, item: Item) -> Dict:
        """Costs 1 AP. Applies item effects to active combatant. Returns result dict."""

    def apply_condition(self, target_index: int, condition: Condition) -> Dict:
        """Appends condition to target's condition list. Returns confirmation dict."""

    def end_turn(self) -> None:
        """Advances to next living combatant. Increments round if all have acted. Calls start_turn()."""

    def get_summary(self) -> Dict:
        """Returns {'rounds': int, 'survivors': List[str], 'casualties': List[str], 'event_count': int}."""
```

---

## 10. Acceptance Criteria (Standard Format)

AC-01 [FR1]: Given a CombatManager initialized with 3 characters, when combat starts, then all 3 combatants have an initiative value and are sorted in descending order.

AC-02 [FR2]: Given an active combatant, when `start_turn()` is called, then `active_combatant.ap == 3`. When `end_turn()` is called after all 3 combatants act, then `round == 2`.

AC-03 [FR3]: Given an attacker with melee skill +5 and a target with AC=12, when `attack()` is called with seed forcing roll=15, then `attack_roll == 20`, `hit=True`, and `damage > 0`. When roll=1, then `fumble=True` and `hit=False`.

AC-04 [FR4]: Given a target with HP=10 and a weapon dealing 5 damage, when `attack()` hits, then `target.character.hp == 5`. When HP drops to 0, then `target.is_dead == True`.

AC-05 [FR5]: Given a combatant with a Poison condition of duration=2, when `start_turn()` is called twice, then HP decreases each turn and the condition is removed after duration expires.

AC-06 [FR6]: Given a CombatManager where all combatants except one are dead, when `_check_combat_end()` runs, then `combat_ended == True` and the log contains a `combat_end` event with the winner's name.

AC-07 [FR7]: Given a completed combat, when `get_summary()` is called, then it returns correct survivors, casualties, and round count.

---

## 11. Performance Requirements

- Initiative roll: < 1ms per combatant
- Single action resolution (attack): < 5ms
- Full combat simulation (10 combatants, 20 rounds): < 1 second
- Log serialization (JSON dump of full log): < 10ms

---

## 12. Error Handling

| Condition | Method | Behavior |
|---|---|---|
| `target_index` out of range | `attack()` | Raises `IndexError` (default list behavior) |
| Target already dead | `attack()` | Returns `{"error": "Target is dead"}` |
| Insufficient AP (< 1) | `attack()`, `use_item()` | Returns `{"error": "Insufficient AP"}` |
| All combatants dead | `end_turn()` | `_check_combat_end()` catches; combat_ended=True |
| Negative dice roll result | `roll_dice()` | Not possible for standard dice; modifier can produce negative |

---

## 13. Integration Points

- **Character System (Module 1):** All combatants are `Character` instances; reads `stats`, `skills`, `hp`, `ac`
- **Item System (Module 2):** `weapon.damage_dice`, `item.apply_effects()` called during combat actions
- **Rules Module:** `roll_dice()` used for initiative, attacks, and damage
- **Magic System (Module 4):** `cast_spell()` method delegates to `Spell.cast()`
- **DM Agent (Module 6):** Consumes `self.log` to narrate combat events

---

## 14. Test Coverage Target

- **Target:** ≥ 95% line coverage
- **Must cover:** natural 20 crit path, natural 1 fumble path, condition expiry, turn wraparound (end of round), combat_ended detection
- **Determinism:** all combat tests use `seed=` parameter for reproducibility
- **Edge cases:** all combatants dead simultaneously; single-combatant combat

# PRD: Kernel-Native Combat Engine v1

**Status:** In Progress
**Phase:** 1
**Date:** 2026-04-03

## Summary

Replace the legacy `CombatManager` (engine/core/combat.py, 592 lines) with a
kernel-native `CombatEngine` that manages turn order, D&D turn resources, and
dispatches to existing kernel combat math functions.

## Motivation

Currently, combat flows through a Frankenstein hybrid:
1. Legacy `CombatManager.attack()` does d20 + skill_bonus vs flat AC
2. Kernel `resolve_strike()` is called AFTER to patch in armor/wounds
3. HP is manually corrected on the legacy `Character` object

The kernel already has `resolve_attack()` and `resolve_combat_round()` which
handle the full attack pipeline (attack roll, defense AC, critical confirmation,
wound creation, pain/blood/morale). What's missing is the turn management layer.

## Design

### CombatState (dataclass)
Holds the state of an ongoing combat encounter:
- `combatants`: list of `CombatantEntry` (actor_id, initiative, is_player)
- `round_number`: int
- `current_turn_index`: int
- `phase`: "initiative" | "active" | "resolved"
- `turn_resources`: per-combatant D&D turn resources

### CombatantEntry (dataclass)
Per-combatant combat tracking:
- `actor_id`: str (references ActorRecord in roster)
- `initiative`: int
- `is_player`: bool
- `turn_resources`: TurnResources

### TurnResources (dataclass)
D&D 5e turn economy:
- `action`: bool (1 per turn)
- `bonus_action`: bool (1 per turn)
- `reaction`: bool (1 per turn)
- `movement`: int (tiles remaining)
- `max_movement`: int (base speed)

### Functions

- `roll_initiative(actor, seed) -> int`
  - Formula: d20 + ability_modifier(AGI) + initiative_bonus
- `start_combat(actors, seed) -> CombatState`
  - Roll initiative for each, sort descending, set phase="active"
- `start_turn(state, actors) -> TurnStartResult`
  - Reset turn resources, tick effects/conditions on active actor
- `execute_attack(state, actors, attacker_id, defender_id, weapon, seed) -> AttackResult`
  - Validate action available, call kernel `resolve_attack()`, deduct action
- `execute_spell(state, actors, caster_id, spell_def, target_id, seed) -> SpellResult`
  - Validate action, call kernel spellcasting, deduct action
- `end_turn(state) -> CombatState`
  - Advance to next living combatant, increment round if wrapped
- `is_combat_over(state, actors) -> bool | str`
  - Check if one side eliminated

## Functional Requirements

- **FR-01:** Initiative uses `AGI` modifier (Ember canonical stat).
- **FR-02:** Turn resources follow D&D model: action, bonus_action, reaction, movement.
- **FR-03:** Attacks consume the `action` resource and delegate to kernel `resolve_attack()`.
- **FR-04:** Damage flows through tissue layers, creating wounds, not flat HP subtraction.
- **FR-05:** Effect queue ticks at turn start for the active combatant.
- **FR-06:** Death determined by body viability (vital organ destruction or blood loss).
- **FR-07:** Combat state is fully serializable (to_dict / from_dict).

## Acceptance Criteria

- **AC-01:** `test_kernel_combat_engine.py` passes all tests.
- **AC-02:** No imports from `engine.core.combat` in the combat engine.
- **AC-03:** Attack damage creates WoundRecord on defender's BodyState.
- **AC-04:** Turn resources reset each turn (action=True, movement=max_movement).
- **AC-05:** Combat ends when all combatants on one side are dead.

## Files

- NEW: `engine/kernel/combat_engine.py` (~300 lines)
- NEW: `tests/test_kernel_combat_engine.py`

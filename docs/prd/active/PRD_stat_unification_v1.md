# PRD: Stat Unification v1

**Status:** In Progress
**Phase:** 0 (Foundation)
**Date:** 2026-04-03

## Summary

Unify the entire codebase on a single canonical stat vocabulary:
**Ember stats only** (`MIG`, `AGI`, `END`, `MND`, `INS`, `PRE`).

Remove all D&D stat name aliases (`STR`, `DEX`, `CON`, `INT`, `WIS`, `CHA`)
and fallback chains from the kernel layer.

## Motivation

The kernel currently contains 10+ files with dual-stat fallback chains like:
```python
actor.stats.get("STR", actor.stats.get("MIG", 10))
```

This creates ambiguity about which stat keys are canonical, makes debugging
harder, and risks silent failures when actors have one naming convention but
the code expects another.

## Stat Mapping (Reference Only)

| Ember (Canonical) | D&D (Removed) | Domain |
|---|---|---|
| MIG | STR | Physical power |
| AGI | DEX | Speed, reflexes |
| END | CON | Stamina, health |
| MND | INT | Intellect, learning |
| INS | WIS | Awareness, intuition |
| PRE | CHA | Force of personality |

## Functional Requirements

- **FR-01:** All kernel modules must reference stats using Ember keys only.
- **FR-02:** No fallback chains to D&D stat keys in any kernel function.
- **FR-03:** `SAVE_STAT_MAP` in `effects.py` must use Ember keys only.
- **FR-04:** `combat_math.py` `attack_stat()` and `defense_dex_stat()` must
  not fall back to `STR` or `DEX`.
- **FR-05:** `_spell_ability_score()` in `spells.py` must use `MND`/`INS`/`PRE`.
- **FR-06:** All existing kernel tests must pass after the change.

## Acceptance Criteria

- **AC-01:** `grep -r "STR\|DEX\|CON\|INT\|WIS\|CHA" engine/kernel/` returns
  zero matches for stat key usage (excluding comments and this mapping doc).
- **AC-02:** `test_stat_canonical.py` passes with all assertions.
- **AC-03:** All existing `test_kernel_*.py` tests pass unchanged or with
  stat key updates only.
- **AC-04:** No behavioral change -- same combat results, same spell checks,
  same dialog scores.

## Files to Change

1. `engine/kernel/effects.py` -- `SAVE_STAT_MAP` fallback tuple cleanup
2. `engine/kernel/combat_math.py` -- `attack_stat()`, `defense_dex_stat()`
3. `engine/kernel/spells.py` -- `learn_spell()`, `resolve_casting_tick()`,
   `_spell_ability_score()`
4. `engine/kernel/area.py` -- `open_door()` STR fallback
5. `engine/kernel/dialog.py` -- `compute_npc_reaction()` CHA fallback
6. `engine/kernel/store.py` -- `_actor_cha()` CHA fallback
7. `engine/kernel/pathfinding_algorithms.py` -- `compute_movement_speed()` DEX
8. `engine/kernel/systems_syndromes.py` -- `apply_syndrome()` CON fallback

## Test Plan

- New test file: `tests/test_stat_canonical.py`
- Run full kernel test suite: `pytest tests/test_kernel_*.py`

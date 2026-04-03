# PRD: Save Schema v4

**Status:** In Progress
**Phase:** 4
**Date:** 2026-04-03

## Summary

Define a kernel-pure save serializer that validates round-trip fidelity
for all kernel state: GameState, WorldState, ActorRecord[], CombatState.
Bump schema version to 4.0.

## Acceptance Criteria

- **AC-01:** Save/load round-trip preserves ActorRecord stats, body, wounds.
- **AC-02:** EffectQueue instances survive round-trip.
- **AC-03:** CombatState (from combat_engine.py) survives round-trip.
- **AC-04:** Schema version is "4.0".
- **AC-05:** v3 saves are rejected with a clear message.

## Files

- MODIFIED: `engine/save/save_models.py` (bump version, add validation)
- NEW: `tests/test_save_schema_v4.py`

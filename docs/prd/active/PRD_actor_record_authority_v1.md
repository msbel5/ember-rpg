# PRD: ActorRecord Authority v1

**Status:** In Progress
**Phase:** 2
**Date:** 2026-04-03

## Summary

Add factory functions that create `ActorRecord` directly from creation data
and monster templates, removing the need for legacy `Character` as an
intermediary. This is a prerequisite for removing `Character` entirely.

## Factory Functions

### `create_player_actor(name, class_name, stats, ...) -> ActorRecord`
- Accepts character creation output (name, class, stat array, skills)
- Maps class data from `data/classes.json` for HP, BAB, proficiency
- Initializes body state, turn resources, empty inventory

### `create_monster_actor(template, position, ...) -> ActorRecord`
- Accepts a monster template dict (from `data/monsters.json`)
- Maps D&D stats to Ember: str->MIG, dex->AGI, con->END, etc.
- Sets HP, AC (in raw_payload), BAB from CR, skills from attacks

## Acceptance Criteria

- **AC-01:** `create_player_actor()` returns a valid combat-ready ActorRecord.
- **AC-02:** `create_monster_actor()` maps stats correctly to Ember keys.
- **AC-03:** Both factories produce actors with valid BodyState.
- **AC-04:** Round-trip serialization works: `to_dict() -> from_dict()`.
- **AC-05:** No `Character` import needed to create actors.

## Files

- MODIFIED: `engine/kernel/actor_records.py` (add factories)
- NEW: `tests/test_actor_record_lifecycle.py`

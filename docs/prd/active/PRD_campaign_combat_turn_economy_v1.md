# PRD: Campaign Combat And Turn Economy Cutover
**Project:** Ember RPG  
**Phase:** 1  
**Author:** Codex  
**Date:** 2026-04-03  
**Status:** Implemented  

---

## 1. Purpose
Standardize the campaign-facing combat contract on Ember stats and D&D-style turn resources. The client must stop presenting AP as the authoritative combat currency and instead render action, bonus action, reaction, and movement state.

## 2. Scope
- In scope: actor serialization for turn resources, combat payload display contract, Ember-stat combat math and saving throws, combat debug tracing.
- Out of scope: rewriting every legacy gameplay handler, introducing a new tactical transport, or changing authored encounter content.

## 3. Functional Requirements (FR)
FR-01: Kernel actor serialization must persist turn resources instead of action-point counters as the canonical actor-state contract.
FR-02: Kernel combat math and effect saving throws must resolve Ember stats (`MIG/AGI/END/MND/INS/PRE`) as primary authorities.
FR-03: Campaign-facing combat payloads and client surfaces must display D&D turn resources instead of AP.
FR-04: Kernel strike outcomes surfaced through the gameplay handler must emit structured combat debug traces.

## 4. Data Structures
```python
@dataclass
class TurnResources:
    action_available: bool = True
    bonus_action_available: bool = True
    reaction_available: bool = True
    movement_remaining: int = 6
    speed: int = 6
```

## 5. Public API
- `ActorRecord.turn_resources`
  - Preconditions: actor exists.
  - Postconditions: serializes canonical turn resources.
- `CombatStateMixin._combat_state()`
  - Preconditions: combat exists.
  - Postconditions: each combatant includes turn-resource state for the client shell.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Given an `ActorRecord`, when it is serialized and restored, then canonical turn resources round-trip without AP root fields.
AC-02 [FR-02]: Given combat math and effect saving throws, when Ember-only stats are present, then no D&D stat keys are required for attack, defense, or saving throw resolution.
AC-03 [FR-03]: Given a combat payload on the Godot shell, when combat rows and status strips render, then they show action/bonus/reaction/movement instead of AP.
AC-04 [FR-04]: Given a resolved strike through the gameplay handler, when a wound is built, then debug traces include hit part, armor absorption, and effective damage.

## 7. Performance Requirements
- Combat payload formatting must remain sub-5 ms per action on local hardware.

## 8. Error Handling
- Missing turn-resource fields fall back to safe defaults (`action=true`, `movement=6`).
- Combat math must fall back to Ember stats rather than D&D aliases.

## 9. Integration Points
- `frp-backend/engine/kernel/actor_records.py`
- `frp-backend/engine/kernel/combat_math.py`
- `frp-backend/engine/kernel/effects.py`
- `frp-backend/engine/api/handlers/combat_state.py`
- `godot-client/scripts/ui/status_bar.gd`
- `godot-client/scripts/ui/combat_overlay.gd`
- `godot-client/scripts/ui/character_panel.gd`

## 10. Test Coverage Target
- 100% branch coverage for turn-resource serialization helpers.
- Explicit tests for Ember-stat combat math and client render expectations.

## Changelog
- 2026-04-03: Added canonical Ember-stat and D&D turn-resource requirements for campaign combat.

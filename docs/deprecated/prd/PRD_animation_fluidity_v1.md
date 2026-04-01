# PRD: Animation Fluidity v1
**Project:** Ember RPG  
**Phase:** Director Mode Recovery  
**Author:** Codex  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Raise VQR `Animation Fluidity` from `1` to `3` in the first pass by replacing raw teleport presentation with lightweight motion and transitions that fit the existing architecture.

## 2. Scope
- In scope: movement lerp, selection or action flashes, lightweight panel transitions, and camera smoothing.
- Out of scope: frame-based combat animation pipelines, blend trees, or bespoke death sequences.

## 3. Functional Requirements
FR-01: Player and visible world entities SHALL no longer present as pure teleports during ordinary movement.
FR-02: Click-driven interaction SHALL support a lightweight motion or flash acknowledgement.
FR-03: Camera movement SHALL avoid abrupt snapping where smoothing can be added safely.
FR-04: Motion effects SHALL not interfere with backend-authoritative position updates.

## 4. Data Structures
```python
class MotionState(TypedDict):
    from_tile: tuple[int, int]
    to_tile: tuple[int, int]
    started_at_ms: int
    duration_ms: int
```

## 5. Public API
No external API change.
Internal consumers MAY add transient motion state inside `entity_layer.gd`, `world_view.gd`, or camera helpers.

## 6. Acceptance Criteria
AC-01 [FR-01]: Ordinary movement is visibly smoother than the current teleport baseline.
AC-02 [FR-02]: Clicked targets or issued actions produce a visible acknowledgement.
AC-03 [FR-03]: Camera follow feels steadier during movement.
AC-04 [FR-04]: Final positions remain backend-authoritative and do not drift.

## 7. Performance Requirements
- Motion work SHALL preserve responsive input and not leave stale tweens piling up.

## 8. Error Handling
- If a tween or transition is interrupted by a fresh authoritative update, the entity snaps to the correct final state cleanly.

## 9. Integration Points
- `godot-client/scripts/world/entity_layer.gd`
- `godot-client/scripts/world/world_view.gd`
- `godot-client/scripts/world/camera_controller.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/tests/run_headless_tests.gd`

## 10. Test Coverage Target
- Extend headless coverage around motion state setup, camera follow rules, and interruption safety where feasible.

## Changelog
- 2026-03-28: Initial Director Mode animation-fluidity recovery PRD.

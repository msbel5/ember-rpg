# PRD: Interaction Feedback v1
**Project:** Ember RPG  
**Phase:** Director Mode Recovery  
**Author:** Codex  
**Date:** 2026-03-28  
**Status:** Draft  

---

## 1. Purpose
Raise VQR `Interaction Feedback` from `3` to `4` in the first pass by making clicks, movement, and panel actions visibly acknowledged in the Godot client.

## 2. Scope
- In scope: hover and selection clarity, click acknowledgement, movement confirmation, action flashes, button busy states, and error visibility.
- Out of scope: full combat animation choreography or particle-heavy impact effects.

## 3. Functional Requirements
FR-01: World clicks SHALL produce an immediate visual acknowledgement.
FR-02: Selected or hovered tiles and entities SHALL remain readable long enough for the player to understand the target.
FR-03: Movement and interaction outcomes SHALL produce more than narrative-only feedback.
FR-04: Busy states for title load, save/load panel actions, and command submission SHALL remain visible and non-ambiguous.

## 4. Data Structures
```python
class InteractionFeedbackState(TypedDict):
    selected_tile: tuple[int, int] | None
    hovered_tile: tuple[int, int] | None
    last_command: str
    is_busy: bool
```

## 5. Public API
No external API change.
Internal surfaces:
- `godot-client/scripts/world/selection_overlay.gd`
- `godot-client/scripts/world/world_view.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/ui/save_load_panel.gd`

## 6. Acceptance Criteria
AC-01 [FR-01]: A world click produces a visible target or tile acknowledgement before the backend narrative arrives.
AC-02 [FR-02]: Hover and selection states remain easy to see on both terrain and entity targets.
AC-03 [FR-03]: Movement or interaction produces visible confirmation beyond text alone.
AC-04 [FR-04]: Title and in-session save/load actions cannot be silently double-triggered.

## 7. Performance Requirements
- Feedback effects SHALL feel immediate and complete within normal command latency.

## 8. Error Handling
- Failed commands SHALL surface a clear inline error without leaving stale feedback states behind.

## 9. Integration Points
- `godot-client/scripts/world/selection_overlay.gd`
- `godot-client/scripts/world/world_view.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/ui/command_bar.gd`
- `godot-client/scripts/ui/save_load_panel.gd`
- `godot-client/tests/run_headless_tests.gd`

## 10. Test Coverage Target
- Extend headless tests for selection persistence, command acknowledgement, and busy-state disablement.

## Changelog
- 2026-03-28: Initial Director Mode interaction-feedback recovery PRD.

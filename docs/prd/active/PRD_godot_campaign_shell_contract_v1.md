# PRD: Godot Campaign Shell Contract Cutover
**Project:** Ember RPG  
**Phase:** 1  
**Author:** Codex  
**Date:** 2026-04-03  
**Status:** Implemented  

---

## 1. Purpose
Define the campaign-only Godot shell contract. The title screen, gameplay shell, minimap, combat overlay, and save/load surfaces must consume campaign snapshots only and must stop relying on legacy session resync branches.

## 2. Scope
- In scope: backend autoload routes, GameState normalization, title shell, world sync, save sync, minimap summaries, combat overlay, headless authority tests.
- Out of scope: websocket diffing, visual theme redesign, non-campaign tools.

## 3. Functional Requirements (FR)
FR-01: `backend.gd` must expose campaign-only runtime methods used by the shell.
FR-02: `game_session.gd`, world sync, and save sync must stop branching on legacy sessions.
FR-03: The title shell must expose genre-card creation affordances and a dossier summary node used by automated proof.
FR-04: The minimap must explicitly reserve “Scene Read” copy for local surveys and “World Graph / Reachable” copy for macro travel.
FR-05: The headless Godot proof lane must pass without the `EntityLayer` compile/runtime break.

## 4. Data Structures
```gdscript
var combatant_turn_resources := {
    "action_available": true,
    "bonus_action_available": true,
    "reaction_available": true,
    "movement_remaining": 6,
    "speed": 6,
}
```

## 5. Public API
- `Backend.submit_campaign_command(campaign_id, input_text, callback, shortcut="", args={})`
- `Backend.list_player_campaign_saves(player_id, callback)`
- `Backend.delete_campaign_save(save_id, callback)`
- `GameState.update_from_response(data)`
  - Preconditions: accepts campaign snapshot or creation-state payload.
  - Postconditions: updates only campaign-facing runtime slices.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Given the backend probe, when the title shell or save browser requests data, then only campaign routes are used.
AC-02 [FR-02]: Given the gameplay shell, when a command resolves, then no legacy session resync routes are invoked.
AC-03 [FR-03]: Given the title shell creation wizard, when the shell opens, then `GenreCards/FantasyCard` and `DossierSection/DossierText` exist.
AC-04 [FR-04]: Given empty local map state, when the minimap renders, then visible copy contains `Scene Read`; given world-graph state, visible copy contains `World Graph` and `Reachable`.
AC-05 [FR-05]: Given the headless Godot test runner, when gameplay scenes instantiate, then `EntityLayer` compiles and `WorldViewportContainer` renders entities.

## 7. Performance Requirements
- Shell refresh on state updates must stay under one frame on local headless tests.

## 8. Error Handling
- Missing campaign IDs render clear shell errors.
- Missing map payloads keep placeholder copy visible instead of crashing.
- Missing turn-resource payloads fall back to safe combat defaults.

## 9. Integration Points
- `godot-client/autoloads/backend.gd`
- `godot-client/autoloads/game_state.gd`
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/ui/session_world_sync.gd`
- `godot-client/scripts/ui/session_save_sync.gd`
- `godot-client/scripts/ui/minimap_panel.gd`
- `godot-client/tests/run_headless_tests.gd`

## 10. Test Coverage Target
- Full headless coverage of title flow, continue flow, combat overlay, minimap state, and save/load shell actions.

## Changelog
- 2026-04-03: Added campaign-only Godot shell contract and headless authority requirements.

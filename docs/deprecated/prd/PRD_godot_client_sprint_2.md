# PRD: Godot Client Sprint 2

## Objective

Wire the title flow and runtime world state to the existing FastAPI backend using the normalized facade.

## Scope

- Title screen session creation flow
- Session bootstrap with `scene/enter` and `get_map`
- Per-turn resync using `submit_action` then `get_session`
- Conditional inventory refresh

## Files

- `godot-client/autoloads/backend.gd`
- `godot-client/autoloads/game_state.gd`
- `godot-client/scenes/title_screen.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/net/response_normalizer.gd`
- `godot-client/scripts/world/world_view.gd`

## Node Impact

- `TitleScreen` remains root for entry flow.
- `GameSession` becomes a passive consumer of normalized `GameState`.

## GDScript Structure

- `response_normalizer.gd` converts backend payloads into render-ready dictionaries.
- `title_screen.gd` owns creation/finalize flow and scene transition only.
- `game_session.gd` owns bootstrap, command dispatch, and error messaging only.

## Acceptance Criteria

- Create character and enter the world from the title screen.
- Submit `look around` and receive narrative update plus session resync.
- Backend timeout or 404 surfaces in UI and does not crash the client.

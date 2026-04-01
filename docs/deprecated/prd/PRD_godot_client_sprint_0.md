# PRD: Godot Client Sprint 0

## Objective

Stabilize the existing Godot client so it boots headless, matches the real backend API, and has a minimal automated verification harness.

## Scope

- Fix parser and startup blockers.
- Correct HTTP route mismatches.
- Normalize backend payload drift in `GameState`.
- Remove authoritative client-side movement assumptions.
- Add a minimal headless test runner.

## Files

- `godot-client/scenes/title_screen.gd`
- `godot-client/autoloads/backend.gd`
- `godot-client/autoloads/game_state.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/asset/asset_bootstrap.gd`
- `godot-client/tests/run_headless_tests.gd`
- `godot-client/tests/doubles/backend_probe.gd`
- `tools/asset_pipeline.py`

## Node Impact

- No major scene tree redesign in this sprint.
- Existing `TitleScreen` and `GameSession` trees remain intact.

## GDScript Structure

- `Backend` exposes corrected `get_inventory`, `save_game`, `load_game`, and `list_saves`.
- `GameState` accepts `combat`, `map`, `world_entities`, quest payloads, and inventory payloads.
- `GameSession` uses backend-returned position instead of predicted movement.
- `AssetBootstrap` resolves runtime asset and token lookup policy.

## Acceptance Criteria

- `godot.console.exe --headless --path godot-client --quit` exits successfully.
- Headless tests verify:
  - save/load/list/inventory routes
  - payload normalization
  - scene instantiation
  - token fallback behavior

## Test Commands

- `& 'C:\Tools\Scoop\apps\godot\current\godot.console.exe' --headless --path 'C:\Users\msbel\projects\ember-rpg\godot-client' --quit`
- `& 'C:\Tools\Scoop\apps\godot\current\godot.console.exe' --headless --path 'C:\Users\msbel\projects\ember-rpg\godot-client' --script res://tests/run_headless_tests.gd`

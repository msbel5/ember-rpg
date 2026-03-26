# PRD: Godot Client Sprint 6

## Objective

Complete the gameplay vertical slice with combat, quests, save/load, visual polish, and export readiness.

## Scope

- Combat panel
- Quest panel
- Save/load panel
- Hover and selection polish
- Desktop and Web export readiness

## Files

- `godot-client/scenes/components/combat_panel.tscn`
- `godot-client/scenes/components/quest_panel.tscn`
- `godot-client/scenes/components/save_load_panel.tscn`
- `godot-client/scripts/ui/combat_panel.gd`
- `godot-client/scripts/ui/quest_panel.gd`
- `godot-client/scripts/ui/save_load_panel.gd`
- `godot-client/scenes/game_session.gd`
- `godot-client/export_presets.cfg`

## Nodes

- `OverlayCanvas` hosts modal save/load and combat overlays.
- `Sidebar` quest surface becomes fully interactive.

## GDScript Structure

- Combat, quest, and save/load components consume normalized `GameState` and `Backend`.
- `game_session.gd` remains the only high-level coordinator for scene-wide transitions.

## Acceptance Criteria

- Full loop works: create, explore, talk, fight, loot, inspect inventory, accept quest, save, load, continue.
- No critical visual blockers remain.
- Web export smoke passes if export templates are installed locally.

# PRD: Godot Client Sprint 4

## Objective

Split the monolithic gameplay scene into reusable panels and reach terminal command parity through the new UI shell.

## Scope

- Narrative panel
- Inventory panel
- Status bar
- Minimap
- Command bar and command history

## Files

- `godot-client/scenes/components/status_bar.tscn`
- `godot-client/scenes/components/narrative_panel.tscn`
- `godot-client/scenes/components/inventory_panel.tscn`
- `godot-client/scenes/components/minimap_panel.tscn`
- `godot-client/scenes/components/command_bar.tscn`
- `godot-client/scripts/ui/status_bar.gd`
- `godot-client/scripts/ui/narrative_panel.gd`
- `godot-client/scripts/ui/inventory_panel.gd`
- `godot-client/scripts/ui/minimap_panel.gd`
- `godot-client/scripts/ui/command_bar.gd`
- `godot-client/scenes/game_session.tscn`
- `godot-client/scenes/game_session.gd`

## Nodes

- `Sidebar` becomes a dedicated stack of UI components.
- `CommandBar` becomes its own reusable scene with input, send, and history affordances.

## GDScript Structure

- Each UI component subscribes to `GameState` directly.
- `game_session.gd` only coordinates top-level flows.
- All buttons and click actions still dispatch plain-text commands through the same submission method.

## Acceptance Criteria

- Narrative, inventory, status, minimap, and command bar update from live session state.
- Move, talk, attack, inventory, craft, rest, quest, save, and load commands all pass through the same text command path.

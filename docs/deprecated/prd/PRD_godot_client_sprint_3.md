# PRD: Godot Client Sprint 3

## Objective

Render authoritative entities on top of the backend map and translate clicks into backend-compatible commands.

## Scope

- Render player, NPCs, enemies, and items as `Sprite2D`.
- Use `world_entities` first and fall back to grouped `entities`.
- Add click handling for move, talk, attack, examine, and pick-up intents.

## Files

- `godot-client/scripts/world/entity_layer.gd`
- `godot-client/scripts/world/entity_sprite_catalog.gd`
- `godot-client/scripts/world/world_view.gd`
- `godot-client/scenes/game_session.gd`

## Nodes

- `EntityLayer (Node2D)` holds runtime `Sprite2D` and hit target nodes.
- `SelectionLayer (Node2D)` draws hover and selected tile feedback.

## GDScript Structure

- `entity_sprite_catalog.gd` maps normalized entity templates to placeholder or generated sprite paths.
- `entity_layer.gd` owns creation, update, and cleanup of entity nodes.
- `world_view.gd` emits semantic clicks to `game_session.gd`.

## Acceptance Criteria

- Player, NPCs, enemies, and items render at backend-provided coordinates.
- Clicking empty ground submits a move command.
- Clicking an NPC, enemy, or item produces the expected command string.

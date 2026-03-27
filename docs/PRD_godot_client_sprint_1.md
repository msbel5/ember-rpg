# PRD: Godot Client Sprint 1

## Objective

Replace the ad hoc map panel with a real top-down world shell built on `TileMapLayer`, `Node2D`, and `Camera2D`.

## Scope

- Build the new gameplay scene tree for world rendering.
- Add placeholder 16x16 terrain tiles.
- Add an authoritative follow camera with scroll-wheel zoom.
- Keep entity rendering simple and placeholder-only for now.

## Files

- `godot-client/scenes/game_session.tscn`
- `godot-client/scenes/game_session.gd`
- `godot-client/scripts/world/world_view.gd`
- `godot-client/scripts/world/tile_catalog.gd`
- `godot-client/scripts/world/tilemap_controller.gd`
- `godot-client/scripts/world/entity_layer.gd`
- `godot-client/scripts/world/camera_controller.gd`

## Scene Tree

```text
GameSession (Control)
  Background
  MainMargin
    MainVBox
      StatusBar
      ContentSplit
        WorldPane
          WorldViewportContainer
            WorldViewport
              WorldRoot
                TerrainLayer
                EntityLayer
                SelectionLayer
                WorldCamera
        Sidebar
          NarrativePanel
      CommandBar
```

## GDScript Structure

- `world_view.gd` wires the world nodes and forwards click/zoom/follow events.
- `tile_catalog.gd` owns runtime placeholder texture generation and tile id mapping.
- `tilemap_controller.gd` paints `GameState.map_data` into `TileMapLayer`.
- `entity_layer.gd` renders a player marker and placeholder world markers.
- `camera_controller.gd` clamps zoom steps and centers on the player tile.

## Acceptance Criteria

- Game scene instantiates with the new world tree.
- Placeholder terrain appears even without backend map data.
- Camera follows the current player tile.
- Mouse wheel zooms in and out with discrete steps.

## Test Focus

- Scene instantiation
- Camera zoom clamp
- Placeholder tile population
- Player-centered initial framing

# PRD: Ember RPG Godot 4.x Client

**Project:** Ember RPG  
**Status:** Active implementation  
**Date:** 2026-03-27  
**Target Engine:** Godot 4.6.x  
**Primary Platforms:** Windows desktop first, Web export second  

## 1. Product Summary

The Godot client is a RimWorld-style 16x16 pixel top-down frontend for Ember RPG. The FastAPI backend remains the source of truth for rules, state transitions, combat resolution, saves, quests, and narration. The client is responsible for session bootstrap, HTTP transport, rendering map and entities, and presenting narrative and game UI without duplicating gameplay logic.

The terminal client is the parity baseline. The Godot client must support the same command surface by routing every action through the same backend endpoints used by the terminal flow.

## 2. Current Reality

- FastAPI backend is already stable with `1954+` tests and a passing 500-turn chaos validation loop.
- The terminal ASCII client is playable and acts as the contract reference.
- The Godot project already contains `Backend`, `GameState`, `TitleScreen`, `GameSession`, a placeholder map renderer, and generated assets, but it needs architectural cleanup to become a proper top-down client.
- The narration proxy is available through the existing backend stack; the Godot client should treat narration as opaque backend output.

## 3. Goals

- Connect to the existing FastAPI backend over HTTP without changing the public API first.
- Render terrain from backend map data through `TileMapLayer`.
- Render player, NPCs, enemies, and world items as `Sprite2D` nodes.
- Provide gameplay panels for narrative, inventory, status, minimap, combat, and quests.
- Reuse or generate pixel-art assets through `tools/asset_pipeline.py`, with cache-first loading.
- Preserve terminal command parity through a single command submission path.
- Support camera follow and mouse-wheel zoom with pixel-stable rendering.

## 4. Non-Goals

- No client-side gameplay rules, combat simulation, or pathfinding authority.
- No multiplayer, mobile, or real-time networking in this rollout.
- No mandatory runtime asset generation on Web builds.
- No replacement of the current backend API unless an unblocker is discovered during implementation.

## 5. Backend Contract

The client must normalize the backend as it exists today.

### Session bootstrap

- `POST /game/session/creation/start`
- `POST /game/session/creation/{creation_id}/finalize`
- fallback support for `POST /game/session/new`

### Scene and turn loop

- `POST /game/scene/enter`
- `POST /game/session/{session_id}/action`
- `GET /game/session/{session_id}`
- `GET /game/session/{session_id}/map`
- `GET /game/session/{session_id}/inventory`

### Persistence

- `POST /game/session/{session_id}/save`
- `POST /game/session/load/{save_id}`
- `GET /game/saves/{player_id}`
- `DELETE /game/session/{session_id}`

### Payload normalization rules

- Treat `combat` as the authoritative combat payload and normalize it into internal `combat_state`.
- Accept both `map_data` and `map` and normalize them into `GameState.map_data`.
- Accept `entities` as either grouped dictionaries or flat lists.
- Prefer `world_entities` from session state when present.
- Use `player.position` and `player.facing` as the authoritative camera target.

## 6. Scene Architecture

The target runtime scene tree for gameplay is:

```text
GameSession (Control)
  Background (ColorRect)
  MainMargin (MarginContainer)
    MainVBox (VBoxContainer)
      StatusBar (PanelContainer)
      ContentSplit (HSplitContainer)
        WorldPane (PanelContainer)
          WorldViewportContainer (SubViewportContainer)
            WorldViewport (SubViewport)
              WorldRoot (Node2D)
                TerrainLayer (TileMapLayer)
                EntityLayer (Node2D)
                SelectionLayer (Node2D)
                WorldCamera (Camera2D)
        Sidebar (VBoxContainer)
          NarrativePanel (PanelContainer)
          InventoryPanel (PanelContainer)
          MinimapPanel (PanelContainer)
          QuestPanel (PanelContainer)
      CommandBar (PanelContainer)
  OverlayCanvas (CanvasLayer)
```

## 7. Runtime Systems

### Backend facade

`godot-client/autoloads/backend.gd`

- Owns all HTTP calls.
- Owns request error mapping.
- Owns route normalization for save/load/list endpoints.
- Exposes narrowly scoped methods instead of leaking raw URLs into scene scripts.

### State store

`godot-client/autoloads/game_state.gd`

- Stores normalized session, player, map, inventory, combat, quest, and narrative state.
- Emits rendering-friendly signals.
- Does not perform prediction or gameplay simulation.

### World renderer

`godot-client/scripts/world/*`

- `tile_catalog.gd` maps tile ids to atlas indices and placeholder textures.
- `tilemap_controller.gd` paints backend map data into `TileMapLayer`.
- `entity_layer.gd` owns `Sprite2D` instances and click targets.
- `camera_controller.gd` follows the authoritative player tile and applies discrete zoom steps.

### UI layer

`godot-client/scripts/ui/*`

- Narrative log is driven from normalized backend text.
- Status, inventory, minimap, combat, and quest panels subscribe to `GameState`.
- Command input remains the single action submission surface.

### Asset bootstrap

`godot-client/scripts/asset/asset_bootstrap.gd`

- Resolves runtime token from `HF_TOKEN` then `HUGGINGFACE_API_KEY`.
- Resolves generated assets from `user://assets/generated/`, then `res://assets/generated/`, then placeholders.
- Runtime generation remains optional and desktop-only.

## 8. Visual Direction

- Pixel-art top-down camera with 16x16 world tiles.
- Crisp nearest-neighbor rendering with stable integer zoom levels.
- Earthy low-fantasy palette and readable high-contrast UI.
- RimWorld-style informational layout: world view on the left, narrative and systems on the right, command bar along the bottom.

## 9. Core UX Requirements

- Session creation must flow from the title screen into the world without forcing manual backend setup beyond base URL configuration.
- The world must remain playable through text input even if click interactions are unavailable or incomplete.
- Mouse interaction should synthesize the same commands the terminal client accepts.
- Backend errors must be surfaced in UI without crashing the scene.
- The client must remain usable with placeholder art if generated assets are absent.

## 10. Asset Strategy

- Bundled generated assets live in `res://assets/generated/`.
- Runtime desktop cache lives in `user://assets/generated/`.
- `tools/asset_pipeline.py` remains the authoritative generator.
- Asset generation should be asynchronous and non-blocking.
- Web builds never invoke Python at runtime and rely on bundled or placeholder assets.

## 11. Quality Bar

A sprint is only complete when:

- Headless Godot boot succeeds.
- Sprint-targeted headless tests pass.
- Manual desktop playtest for the sprint acceptance path passes.
- No reproduced crash, parser error, blocking UI defect, or backend/client state desync remains in that sprint scope.

The rollout is considered production-ready when the full vertical slice works end to end on desktop and Web export smoke is green if export prerequisites exist locally.

## 12. Sprint Structure

- Sprint 0: boot and contract stabilization
- Sprint 1: world shell, `TileMapLayer`, camera
- Sprint 2: backend session bootstrap and map sync
- Sprint 3: entity rendering and click interactions
- Sprint 4: UI panels and command parity
- Sprint 5: asset pipeline integration and cache policy
- Sprint 6: combat, quests, save/load, polish, export readiness

Each sprint has a dedicated implementation PRD in `docs/PRD_godot_client_sprint_<n>.md`.

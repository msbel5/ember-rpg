# Ember RPG — Godot Client

2D game client for Ember RPG, built with Godot 4.6 (Compatibility renderer).

## Requirements

- Godot 4.6+ (Standard, not .NET)
- Backend server running (see `../frp-backend/README.md`)

## Setup

1. Open `project.godot` in Godot
2. Edit `autoloads/backend.gd` line 5 — set your backend URL:
   ```gdscript
   const DEFAULT_URL = "http://YOUR_PI_IP:8765"
   ```
3. Press F5 to run

## Controls

| Key | Action |
|-----|--------|
| Enter | Send text command |
| M | Toggle tile map view |
| I | Toggle inventory (planned) |
| Click entity | Context menu (examine, talk, trade) |
| Click tile | Move to tile |

## Structure

```
godot-client/
  autoloads/
    backend.gd      # HTTP client for FastAPI backend
    game_state.gd    # Global game state singleton
  scenes/
    title_screen.tscn/.gd    # Title + character creation
    game_session.tscn/.gd    # Main game screen
  scripts/
    tile_map_renderer.gd     # Tile map rendering from backend data
  assets/
    fonts/       # Game fonts
    sprites/     # Entity sprites (NPC, monster, item)
    tiles/       # Tile textures (grass, cobblestone, etc.)
```

## Backend API

The client communicates with the backend via REST:
- `POST /game/session/new` — Create game session
- `POST /game/session/{id}/action` — Send player action
- `POST /game/scene/enter` — Enter a new scene (map + entities + narrative)
- `GET /game/session/{id}/inventory` — Get player inventory

See `../frp-backend/README.md` for full API reference.

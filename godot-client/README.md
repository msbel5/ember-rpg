# Ember RPG — Godot Client

Top-down 2D game client built with Godot 4.6 (Compatibility renderer).

## Requirements

- Godot 4.6+ (Standard, not .NET)
- Backend server running at `http://127.0.0.1:8000`

## Setup

1. Open `project.godot` in Godot
2. Edit `autoloads/backend.gd` line 5 — set your backend URL
3. Press F5 to run

## Controls

| Key | Action |
|-----|--------|
| Enter | Focus command bar / send command |
| Arrow Keys / WASD | Move (when not typing) |
| I | Open inventory (when not typing) |
| F5 / Ctrl+S | Quick save |
| F9 / Ctrl+L | Open save/load panel |
| Escape | Close panels |
| F12 | Capture visual proof screenshot |
| Click entity | Context action (examine, talk, trade) |
| Click tile | Move to tile |

## UI Layout

```
+--StatusBar (HP/SP/AP/Location)---------------------------+
|                          |  [Tabs]                       |
|   World Viewport         |  Narrative | Hero | Town |    |
|   (top-down tile map)    |  Quests | Items | Map         |
|                          |                               |
+--CommandBar (input + Act/Save/Loads + roster)------------+
```

The sidebar uses **TabContainer** — each tab shows one panel at a time (no scrolling).

## Structure

```
godot-client/
  autoloads/
    backend.gd         # HTTP client (campaign-first routes)
    game_state.gd      # Global state singleton
  scenes/
    title_screen.*     # Title + character creation wizard
    game_session.*     # Main gameplay screen
    components/        # UI panel scenes (narrative, inventory, etc.)
  scripts/
    ui/                # Panel logic (command_bar, status_bar, etc.)
    world/             # Tile rendering, entity layer, camera, overlay
    net/               # Response normalization
    asset/             # Sprite/tile catalog, HF asset bootstrap
  assets/
    fonts/             # Game fonts
    sprites/           # Hand-drawn entity sprites
    tiles/             # Tile textures
    generated/         # AI-generated sprites and tiles
    ui/                # UI bar textures
  tests/
    run_headless_tests.gd  # 183 headless tests
    automation/            # Desktop automation harness
```

## Backend API (Campaign-First)

> **Note**: Legacy `/session/` routes are deprecated. Use campaign routes.

- `POST /game/campaigns/create` — Start campaign creation
- `POST /game/campaigns/{id}/commands` — Send player command
- `GET /game/campaigns/{id}` — Get campaign snapshot
- `GET /game/campaigns/{id}/settlement` — Get settlement state
- `POST /game/campaigns/{id}/save` — Save campaign
- `GET /game/campaigns/{id}/saves` — List saves
- `POST /game/campaigns/load/{save_id}` — Load save

## Content Adapters

- `fantasy_ember` — Medieval fantasy (default)
- `scifi_frontier` — Space opera variant

# PRD: Godot 4.6 Client — Ember RPG
**Version:** 1.0  
**Status:** Draft  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Engine:** Godot 4.6 (GDScript 2.0)  
**Backend:** FastAPI — http://localhost:8765

---

## 1. Overview

The Ember RPG Godot client is a 2D pixel-art RPG frontend that communicates with the FastAPI backend via HTTP polling. The player types natural language commands ("attack the goblin", "open the chest") into a text input field. The backend resolves all game mechanics and returns DM narrative, which the client displays in a scrolling story panel.

The client renders the game world visually (tile map, NPCs, combat HUD) but contains **zero game logic** — all rules, dice rolls, and narrative generation happen on the backend.

---

## 2. Goals

- **G1** — Playable in browser (Web export) and desktop (PC)
- **G2** — Natural language input drives all gameplay
- **G3** — Tile-based world renders backend map data
- **G4** — Combat is visual: HP bars, AP indicators, turn order
- **G5** — Zero duplicated logic — client is a pure render/input layer
- **G6** — Works without internet — localhost backend only (Phase 1)

---

## 3. Non-Goals (Phase 1)

- No multiplayer
- No mobile (Phase 2)
- No WebSocket (Phase 2 — HTTP polling sufficient for turn-based)
- No animation system
- No audio (Phase 2)
- No inventory drag-and-drop UI

---

## 4. Architecture

```
[Player Input]
      │
      ▼
 InputHandler (GDScript)
      │  text → ParsedAction
      ▼
 HTTPClient (GDScript)
      │  POST /game/session/{id}/action
      ▼
 FastAPI Backend
      │  ActionResult JSON
      ▼
 GameStateManager (GDScript)
      │  updates local state
      ├──▶ NarrativePanel.append(text)
      ├──▶ CombatHUD.refresh(combat_state)
      ├──▶ TileRenderer.draw(map_data)
      └──▶ PlayerStatusBar.refresh(player)
```

---

## 5. Scene Structure

```
res://
├── scenes/
│   ├── TitleScreen.tscn       # New game / Load / Quit
│   ├── GameSession.tscn       # Main game scene (root during play)
│   ├── CombatHUD.tscn         # Combat overlay (shown only in combat)
│   ├── DialogueBox.tscn       # NPC dialogue (shown only in dialogue scene)
│   └── MapViewer.tscn         # Tile map renderer (embedded in GameSession)
├── scripts/
│   ├── http_client.gd         # All backend HTTP calls
│   ├── game_state.gd          # Singleton: current session state
│   ├── input_handler.gd       # Text input → HTTP call → state update
│   ├── narrative_panel.gd     # Scrolling DM text display
│   ├── combat_hud.gd          # HP bars, AP dots, turn indicator
│   ├── tile_renderer.gd       # Renders MapData.tiles[][] grid
│   └── player_status.gd       # Level, HP, XP bar, class label
├── assets/
│   ├── tiles/                 # 16×16 or 32×32 pixel art tiles
│   ├── sprites/               # Character/NPC sprites
│   └── fonts/                 # Pixel font (e.g. Press Start 2P)
└── autoloads/
    ├── GameState.gd            # Autoload singleton
    └── Backend.gd              # Autoload: HTTP client wrapper
```

---

## 6. Scenes — Detailed Spec

### 6.1 TitleScreen

**Layout:**
- Game logo (top center)
- `[New Game]` button → opens character creation dialog
- `[Continue]` button (grayed out if no saved session)
- `[Quit]` button

**Character Creation Dialog (modal):**
- Name: TextEdit (single line)
- Class: OptionButton — Warrior / Rogue / Mage / Priest
- `[Start Adventure]` → POST `/game/session/new` → transition to GameSession

**Transition:** Fade to black → load GameSession scene.

---

### 6.2 GameSession (Main Scene)

**Layout (1280×720 default):**

```
┌─────────────────────────────────────────────────┐
│  [Player Status Bar]  Level 3 Warrior  HP 18/20  │
├──────────────────┬──────────────────────────────┤
│                  │                               │
│   MAP VIEWER     │    NARRATIVE PANEL           │
│   (tile grid)    │    (scrolling DM text)       │
│                  │                               │
│                  │                               │
├──────────────────┴──────────────────────────────┤
│  > [Text Input Field]              [Send Button] │
└─────────────────────────────────────────────────┘
```

**Components:**
- `MapViewer` (left panel, 640px wide) — renders current tile map
- `NarrativePanel` (right panel) — scrolling label, new text appended at bottom
- `PlayerStatusBar` (top) — name, class, level, HP bar, XP bar
- `TextInput` (bottom) — LineEdit, Enter key = submit
- `CombatHUD` (overlay, hidden unless `scene=combat`) — shown over MapViewer
- `DialogueBox` (overlay, shown when `scene=dialogue`)

---

### 6.3 CombatHUD

Shown as an overlay on MapViewer when `combat_state != null`.

**Layout:**
```
┌─────────────────────────┐
│ ROUND 3  Active: Aria   │
│                         │
│ Aria      ████████ 18/20 AP: ●●○  │
│ Goblin    ████░░░░  5/8  │
│ Skeleton  ██░░░░░░  3/10 │
└─────────────────────────┘
```

**Behavior:**
- Refresh on every `ActionResult` that contains `combat_state`
- Hide when `combat_state.ended == true` (brief flash "Combat ended" then hide)
- AP: filled circles (●) for remaining AP, empty (○) for spent

---

### 6.4 DialogueBox

Shown when backend returns `scene = "dialogue"`.

**Layout:**
- NPC name label (top)
- NPC portrait (placeholder sprite for Phase 1)
- Narrative text box (what NPC said, from `ActionResult.narrative`)
- Text input still active (player types replies)

**Behavior:**
- Hide when scene changes away from `dialogue`

---

### 6.5 MapViewer / TileRenderer

Renders tile data from `GET /game/map/{session_id}` (Phase 2 — see §10).

**Phase 1 fallback:** Display a static placeholder tile grid (grass/stone pattern) labeled with current `location` name. Full tile rendering in Phase 2 when map endpoint is stable.

**Tile types → sprite mapping:**
| `tile_type` | Sprite |
|---|---|
| `floor` | stone_floor.png |
| `wall` | stone_wall.png |
| `door` | door_closed.png |
| `chest` | chest_closed.png |
| `stairs` | stairs_down.png |
| `empty` | void.png |

**Tile size:** 32×32px (scalable). Grid max: 40×40 tiles visible.

---

## 7. HTTP Client — Backend API Contract

All calls are JSON over HTTP. Base URL: `http://localhost:8765` (configurable in Project Settings).

### 7.1 New Session
```
POST /game/session/new
Body: { "player_name": "Aria", "player_class": "warrior" }

Response: {
  "session_id": "uuid",
  "narrative": "string",
  "player": { "name", "level", "hp", "max_hp", "spell_points", "max_spell_points", "xp", "classes" },
  "scene": "exploration",
  "location": "Stone Bridge Tavern"
}
```

### 7.2 Submit Action
```
POST /game/session/{session_id}/action
Body: { "input": "attack the goblin" }

Response: {
  "narrative": "string",
  "scene": "combat" | "exploration" | "dialogue" | "rest",
  "player": { ... },
  "combat_state": null | {
    "round": int,
    "active": "name" | null,
    "ended": bool,
    "combatants": [{ "name", "hp", "max_hp", "ap", "dead" }]
  },
  "level_up": null | { "new_level": int, "... bonus fields" }
}
```

### 7.3 Get Session State (polling)
```
GET /game/session/{session_id}
Response: { "session_id", "scene", "location", "player", "in_combat", "turn" }
```

### 7.4 Delete Session
```
DELETE /game/session/{session_id}
Response: { "message": "Session deleted" }
```

---

## 8. GameState Singleton (game_state.gd)

Central state store. Updated after every HTTP response.

```gdscript
# Fields
var session_id: String
var player: Dictionary       # From API player object
var scene: String            # "exploration" | "combat" | "dialogue" | "rest"
var location: String
var combat_state: Dictionary  # null if not in combat
var narrative_history: Array[String]  # Last 50 lines
var level_up_pending: Dictionary      # null if no level-up

# Signals
signal state_updated
signal combat_started
signal combat_ended
signal level_up_occurred(new_level: int)
signal narrative_received(text: String)
```

---

## 9. Input Flow (input_handler.gd)

```
1. Player types "attack the goblin" + Enter
2. InputHandler.on_submit(text)
3. Backend.post_action(session_id, text)  → awaits response
4. GameState.update_from_response(result)
5. Signals fire → UI components refresh
6. TextInput.clear()
7. TextInput.grab_focus()
```

**Error handling:**
- HTTP 404 (session expired): show "Session lost. Start a new game?" dialog
- HTTP 500: append "[Error: backend unreachable]" to narrative panel
- Timeout (>5s): append "[The DM is thinking...]" then retry once

---

## 10. Phased Delivery

| Phase | Scope | Backend Dep |
|---|---|---|
| **1a** | TitleScreen + GameSession shell + NarrativePanel + TextInput | `/session/new`, `/action` |
| **1b** | CombatHUD + PlayerStatusBar live updates | `combat_state` in ActionResult |
| **1c** | DialogueBox (NPC dialogue scene) | `scene=dialogue` |
| **2a** | TileRenderer with real map data | `GET /game/map/{id}` (TBD) |
| **2b** | Save/Load session persistence | `GET /game/session/{id}` |
| **2c** | Inventory panel | Item endpoints (TBD) |

---

## 11. Acceptance Criteria

| ID | Criterion | Verifiable By |
|---|---|---|
| AC1 | New game dialog creates session; opening narrative appears in ≤2s | Manual + HTTP log |
| AC2 | Typing "attack" → combat starts; CombatHUD appears with HP bars | Manual play |
| AC3 | Player HP bar reflects `player.hp / player.max_hp` after every action | Unit: mock API response |
| AC4 | `scene=combat` shows CombatHUD; `scene=exploration` hides it | Automated scene test |
| AC5 | Narrative panel auto-scrolls to latest text | Manual |
| AC6 | Enter key submits action; text field clears and refocuses | Manual |
| AC7 | Level-up flashes level-up panel with new level number | Mock `level_up` response |
| AC8 | Web export runs in Chrome/Firefox without errors | Export + browser test |
| AC9 | Backend unreachable → error message in narrative, game does not crash | Disconnect backend, submit action |
| AC10 | Session delete called on Quit; no orphaned sessions on server | HTTP log |

---

## 12. Asset Requirements (Phase 1)

| Asset | Format | Notes |
|---|---|---|
| Tile set (floor, wall, door, chest, stairs) | PNG 32×32 | Placeholder OK for Phase 1 |
| Player sprites (warrior, rogue, mage, priest) | PNG 32×32 | Static, no animation Phase 1 |
| Enemy sprites (goblin, orc, skeleton) | PNG 32×32 | Static |
| Pixel font | TTF/OTF | Press Start 2P or similar |
| UI skin | PNG nine-patch | Dark fantasy style |

---

## 13. Technical Constraints

- Godot 4.6 — GDScript 2.0 only (no C#)
- `HTTPRequest` node for all API calls (built-in, no addons)
- `JSON.parse_string()` for response parsing
- Project settings: `window/size/viewport_width=1280`, `viewport_height=720`
- Web export: HTML5 template, no threads (Godot 4.6 Web limitation)
- Backend URL in `ProjectSettings` under `ember_rpg/backend_url` (default: `http://localhost:8765`)
- No third-party addons for Phase 1

---

## 14. Open Questions

| # | Question | Owner | Status |
|---|---|---|---|
| OQ1 | Will `/game/map/{id}` endpoint be added to backend? | Alcyone (backend) | Pending |
| OQ2 | Save/load via file or backend? | Mami | Pending |
| OQ3 | Target tile size: 16×16 or 32×32? | Mami | Pending |
| OQ4 | NPC portrait art style? | Mami | Pending |

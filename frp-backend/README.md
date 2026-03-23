# 🔥 Ember RPG — Backend

> **"You don't need a DM at the table. You need one in the machine."**

Ember RPG is an AI-powered tabletop RPG engine. A **Living DM** — backed by `claude-haiku-4.5` via the GitHub Copilot API — generates atmospheric narrative on the fly, reacting to every player action. No scripted dialogue trees. No hand-authored scenes. Just you, your choices, and a dungeon master that never sleeps.

---

## Table of Contents

1. [What Is Ember RPG?](#what-is-ember-rpg)
2. [Architecture Overview](#architecture-overview)
3. [Quick Start](#quick-start)
4. [API Reference](#api-reference)
5. [systemd Service](#systemd-service)
6. [Godot Client Integration](#godot-client-integration)
7. [Test Suite](#test-suite)
8. [Tech Stack](#tech-stack)

---

## What Is Ember RPG?

Ember RPG is a dark-fantasy RPG backend that replaces a human Dungeon Master with a **Living DM** — an AI agent that:

- Generates immersive 1–3 sentence narrative for every action
- Tracks world state, NPC memory, and player progress
- Reacts dynamically to combat, discovery, and dialogue
- Orchestrates full scene entry (map generation + entity placement + narrative) in one call
- Falls back to template-based responses if the LLM is unavailable

The backend is a **FastAPI REST server**. Any client (Godot, web, CLI) speaks JSON. Streaming endpoints let you render narrative token-by-token for theatrical effect.

---

## Architecture Overview

```
frp-backend/
├── main.py                   # App entry point, router wiring
├── engine/
│   ├── api/                  # HTTP layer
│   │   ├── routes.py         # Session + action + LLM status routes
│   │   ├── scene_routes.py   # Scene enter (full + streaming)
│   │   ├── shop_routes.py    # Merchant buy/sell
│   │   ├── save_routes.py    # Save/load persistence
│   │   ├── npc_memory_routes.py
│   │   ├── game_engine.py    # Action processing, session lifecycle
│   │   ├── game_session.py   # Session state container
│   │   └── models.py         # Pydantic request/response models
│   ├── core/                 # Domain logic
│   │   ├── dm_agent.py       # DMAgent — narrates events, classifies scenes
│   │   ├── character.py      # Character stats, XP, leveling
│   │   └── combat.py         # Combat resolution
│   ├── llm/                  # LLM abstraction
│   │   └── __init__.py       # LLMRouter → GitHub Copilot API (claude-haiku-4.5)
│   ├── orchestrator/         # Scene orchestration pipeline
│   │   └── __init__.py       # SceneOrchestrator: map + entities + narrative
│   ├── npc/                  # NPC AI + memory
│   ├── save/                 # Save file management (JSON, versioned)
│   ├── world_state/          # World state tracking, location memory
│   ├── world/                # World routes (world_routes.py)
│   └── map/                  # Procedural map generation (dungeon/town)
├── data/                     # Static JSON: items, NPC templates, abilities
└── tests/                    # pytest suite (731 tests)
```

### How Modules Connect

```
Client Request
      │
      ▼
  FastAPI (main.py)
      │
      ├─── /game/session/*   ──▶  GameEngine ──▶ DMAgent (narrate)
      │                                       └▶ LLMRouter (claude-haiku-4.5)
      │
      ├─── /game/scene/*     ──▶  SceneOrchestrator
      │                            ├─ MapGenerator (dungeon/town)
      │                            ├─ NPCPlacer
      │                            └─ LLMRouter (streaming narrative)
      │
      ├─── /game/shop/*      ──▶  Shop logic (items.json + npc_templates.json)
      │                            └─ GameSession (gold/inventory mutation)
      │
      ├─── /game/save*       ──▶  SaveManager (JSON files in saves/)
      │
      └─── /game/world/*     ──▶  WorldState (location/NPC memory)
```

**Key design decisions:**
- Sessions live **in-memory** during runtime; autosaved to `saves/` on every action
- On restart, sessions are transparently restored from disk when queried
- LLM is **optional** — all endpoints fall back to deterministic templates if the API is unavailable
- Scene entry is fully **parallelisable**: map generation and LLM narrative are independent

---

## Quick Start

### Prerequisites
- Python 3.11+
- A GitHub Copilot subscription (for LLM narrative) — or run without it for template mode

### Install

```bash
git clone https://github.com/msbel5/frp-game.git
cd frp-game/frp-backend

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8765 --reload
```

API is live at `http://localhost:8765`. Swagger UI at `http://localhost:8765/docs`.

### First Request

```bash
# Create a session
curl -s -X POST http://localhost:8765/game/session/new \
  -H "Content-Type: application/json" \
  -d '{"player_name": "Kael", "player_class": "warrior", "location": "Ashveil Town"}' | jq .

# Take an action (replace SESSION_ID with the id from the response above)
curl -s -X POST http://localhost:8765/game/session/SESSION_ID/action \
  -H "Content-Type: application/json" \
  -d '{"input": "look around"}' | jq .narrative
```

---

## API Reference

All routes are prefixed with `/game` unless noted. Base URL: `http://localhost:8765`.

---

### Sessions

#### `POST /game/session/new`
Create a new game session and receive an opening narrative.

```bash
curl -X POST http://localhost:8765/game/session/new \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "Kael",
    "player_class": "warrior",
    "location": "Ashveil Dungeon"
  }'
```

**Response:**
```json
{
  "session_id": "abc123",
  "narrative": "You stand at the entrance of Ashveil Dungeon. Cold air drifts from the dark passage ahead.",
  "player": { "name": "Kael", "hp": 20, "max_hp": 20, "level": 1 },
  "scene": "exploration",
  "location": "Ashveil Dungeon"
}
```

---

#### `POST /game/session/{session_id}/action`
Send a player action (free text). Returns narrative + updated state.

```bash
curl -X POST http://localhost:8765/game/session/abc123/action \
  -H "Content-Type: application/json" \
  -d '{"input": "attack the goblin with my sword"}'
```

**Response:**
```json
{
  "narrative": "Your blade catches the goblin across the shoulder. It snarls and lunges.",
  "scene": "combat",
  "player": { "name": "Kael", "hp": 17, "max_hp": 20, "level": 1 },
  "combat": { "active": true, "enemy": "goblin", "enemy_hp": 4 },
  "state_changes": { "damage_dealt": 6 },
  "level_up": null
}
```

---

#### `GET /game/session/{session_id}`
Get full session state.

```bash
curl http://localhost:8765/game/session/abc123
```

---

#### `DELETE /game/session/{session_id}`
End and remove a session.

```bash
curl -X DELETE http://localhost:8765/game/session/abc123
```

---

#### `GET /game/session/{session_id}/map`
Get the procedurally generated tile map for the current location.

```bash
curl "http://localhost:8765/game/session/abc123/map?seed=42"
```

---

### Scene Orchestration

#### `POST /game/scene/enter`
Full scene entry: generates map + places entities + streams LLM narrative. Returns all at once as JSON.

```bash
curl -X POST http://localhost:8765/game/scene/enter \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc123",
    "location": "Thornwood Village",
    "location_type": "town",
    "time_of_day": "evening",
    "player_name": "Kael",
    "player_level": 2,
    "is_first_visit": true
  }'
```

Valid `location_type`: `town`, `dungeon`, `tavern`, `wilderness`, `cave`  
Valid `time_of_day`: `morning`, `afternoon`, `evening`, `night`

---

#### `POST /game/scene/enter/stream`
Same as above but responses stream as **NDJSON** (newline-delimited JSON).

```bash
curl -N -X POST http://localhost:8765/game/scene/enter/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc123",
    "location": "Ember Catacombs",
    "location_type": "dungeon",
    "time_of_day": "night",
    "player_name": "Kael",
    "player_level": 3,
    "is_first_visit": false
  }'
```

**Stream events:**
```
{"event": "map_ready", "data": {...}}
{"event": "narrative", "data": "Crumbling stone arches..."}
{"event": "entities_ready", "data": [...]}
{"event": "scene_complete", "data": {...}}
```

---

#### `GET /game/scene/available-types`
List valid location types and time-of-day values.

```bash
curl http://localhost:8765/game/scene/available-types
```

---

### Shop / Merchants

#### `GET /game/shop/{npc_id}`
Get merchant inventory. Items priced at buy (full value) and sell (60% value).

```bash
curl http://localhost:8765/game/shop/merchant_aldric
```

**Response:**
```json
{
  "npc_id": "merchant_aldric",
  "npc_name": "Aldric the Trader",
  "items": [
    { "id": "health_potion", "name": "Health Potion", "buy_price": 50, "sell_price": 30, "type": "consumable" }
  ]
}
```

---

#### `POST /game/shop/{npc_id}/buy`
Purchase an item. Deducts gold, adds to inventory.

```bash
curl -X POST http://localhost:8765/game/shop/merchant_aldric/buy \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc123",
    "item_id": "health_potion",
    "quantity": 2
  }'
```

---

#### `POST /game/shop/{npc_id}/sell`
Sell an item back to a merchant at 60% of its value.

```bash
curl -X POST http://localhost:8765/game/shop/merchant_aldric/sell \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc123",
    "item_id": "iron_sword",
    "quantity": 1
  }'
```

---

### Save / Load

#### `POST /game/session/{session_id}/save`
Explicitly save session state.

```bash
curl -X POST http://localhost:8765/game/session/abc123/save \
  -H "Content-Type: application/json" \
  -d '{"player_id": "Kael"}'
```

**Response:**
```json
{ "save_id": "save_abc123_1234567890", "timestamp": "2025-01-01T12:00:00", "schema_version": "1.0" }
```

> **Note:** Sessions are also **autosaved** on every action — explicit saves are for checkpointing.

---

#### `GET /game/saves/{player_id}`
List all saves for a player.

```bash
curl http://localhost:8765/game/saves/Kael
```

---

#### `GET /game/saves/file/{save_id}`
Get metadata for a specific save file.

```bash
curl http://localhost:8765/game/saves/file/save_abc123_1234567890
```

---

#### `POST /game/session/load/{save_id}`
Load session data from a save file.

```bash
curl -X POST http://localhost:8765/game/session/load/save_abc123_1234567890
```

---

#### `DELETE /game/saves/{save_id}`
Delete a save file.

```bash
curl -X DELETE http://localhost:8765/game/saves/save_abc123_1234567890
```

---

### LLM Status

#### `GET /game/llm/status`
Check if the LLM (claude-haiku-4.5) is reachable and return a test narrative.

```bash
curl http://localhost:8765/game/llm/status
```

**Response:**
```json
{
  "available": true,
  "model": "claude-haiku-4-5",
  "test_response": "Before you lies a shadowed corridor, torchlight flickering against damp stone walls."
}
```

---

## systemd Service

A user-level systemd service is provided for auto-start on boot.

**Service file:** `~/.config/systemd/user/ember-backend.service`

```ini
[Unit]
Description=Ember RPG FastAPI Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/msbel/.openclaw/workspace/projects/frp-game/frp-backend
ExecStart=/home/msbel/.openclaw/workspace/projects/frp-game/frp-backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

### Enable & Start

```bash
systemctl --user daemon-reload
systemctl --user enable ember-backend
systemctl --user start ember-backend

# Check status
systemctl --user status ember-backend

# Tail logs
journalctl --user -u ember-backend -f
```

### Enable at Login (without requiring active session)

```bash
sudo loginctl enable-linger $USER
```

---

## Godot Client Integration

The Ember RPG backend is designed to pair with a Godot 4 client. Three integration patterns are supported:

### 1. REST Polling (current stable approach)

Make HTTP requests from Godot using `HTTPRequest`. Poll `/game/session/{id}` periodically to sync state.

```gdscript
var http = HTTPRequest.new()
add_child(http)

func take_action(session_id: String, text: String):
    var body = JSON.stringify({"input": text})
    var headers = ["Content-Type: application/json"]
    http.request("http://localhost:8765/game/session/%s/action" % session_id,
                 headers, HTTPClient.METHOD_POST, body)

func _on_request_completed(result, response_code, headers, body):
    var json = JSON.parse_string(body.get_string_from_utf8())
    $NarrativeLabel.text = json["narrative"]
```

### 2. Scene Entry with Streaming (recommended for cinematic UX)

Use `HTTPClient` in a thread or `await` to consume the NDJSON stream from `/game/scene/enter/stream`. Render narrative tokens progressively as they arrive for a typewriter effect.

```gdscript
# Pseudo-code — adapt to your Godot HTTP client setup
func stream_scene_entry(session_id: String, location: String):
    # POST to /game/scene/enter/stream
    # Read response line-by-line
    # On each JSON line: check event type
    #   "map_ready"     → render tile map
    #   "narrative"     → append text to narrative box
    #   "entities_ready" → spawn NPC/enemy nodes
    #   "scene_complete" → unlock player input
    pass
```

### 3. WebSocket (roadmap)

A WebSocket upgrade is planned for real-time bidirectional communication — enabling push notifications (combat events, world changes, NPC reactions) without polling. The FastAPI backend already has an async foundation. ETA: post-MVP.

### Recommended Session Flow

```
Godot Startup
    │
    ├── POST /game/session/new  →  store session_id
    │
    ├── POST /game/scene/enter/stream  →  render opening scene
    │
    ├── Player input
    │    └── POST /game/session/{id}/action  →  update narrative + stats UI
    │
    ├── Enter new area
    │    └── POST /game/scene/enter/stream  →  re-render scene
    │
    └── On exit
         └── POST /game/session/{id}/save  →  checkpoint
```

---

## Test Suite

Ember RPG ships with **731 tests** covering all modules.

```bash
# Run full suite
cd frp-backend
source venv/bin/activate
pytest

# Verbose with coverage
pytest -v --tb=short

# Run specific module
pytest tests/test_game_engine.py -v

# Run with parallel workers
pytest -n auto
```

Tests cover:
- `engine/core` — DMAgent narration, character leveling, combat resolution
- `engine/api` — All HTTP endpoints via FastAPI `TestClient`
- `engine/orchestrator` — Scene assembly pipeline
- `engine/llm` — LLM router, fallback behavior
- `engine/save` — Save/load round-trips, schema migration
- `engine/npc` — NPC memory, dialogue generation
- `engine/world_state` — Location tracking, world context

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Web framework** | [FastAPI](https://fastapi.tiangolo.com/) |
| **Python version** | 3.11+ |
| **LLM** | `claude-haiku-4-5` via GitHub Copilot API |
| **Data validation** | [Pydantic v2](https://docs.pydantic.dev/) |
| **ASGI server** | [Uvicorn](https://www.uvicorn.org/) |
| **Persistence** | JSON save files (`saves/`) |
| **Map generation** | Custom procedural dungeon/town generator |
| **Testing** | [pytest](https://pytest.org/) — 731 tests |
| **Process manager** | systemd user service |

### LLM Integration Notes

The LLM is accessed via the `engine/llm` module, which wraps the GitHub Copilot API using `claude-haiku-4-5` (fast, low-latency). The model is configured via the `MODEL_FAST` constant.

- **With LLM available:** Dynamic, atmospheric narrative unique to each action
- **Without LLM:** Graceful fallback to deterministic template strings — game is fully playable

No OpenAI API key required. Uses GitHub Copilot authentication.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PYTHONUNBUFFERED` | Disable Python output buffering (set by systemd) | `1` |

LLM credentials are sourced from GitHub Copilot token discovery (standard Copilot CLI/VS Code auth). No additional `.env` setup required for local development.

---

## License

MIT — see [LICENSE](LICENSE) if present.

---

*Built with ☕ and too many dungeon crawls.*

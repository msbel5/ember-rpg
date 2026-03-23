# Ember RPG

A 2D fantasy role-playing game powered by AI. A Living Dungeon Master generates narrative, responds to natural language, and remembers every choice you make.

## What Makes This Different

| Feature | AI Dungeon | BG3 | Ember RPG |
|---------|:---:|:---:|:---:|
| Real game mechanics (dice, HP, combat) | No | Yes | **Yes** |
| AI-generated narrative | Yes | No | **Yes** |
| Persistent NPC memory | No | No | **Yes** |
| World state consequences | No | Partial | **Yes** |
| Open source | No | No | **Yes** |

## Architecture

```
Godot 4.6 Client (PC/Web)
    |
    | HTTP REST API
    |
FastAPI Backend (Python 3.13)
    |
    +-- Game Engine (deterministic rules, combat, magic)
    +-- Scene Orchestrator (map gen, entity placement, narrative)
    +-- LLM Router (Claude Haiku / Sonnet via Copilot API)
    +-- World State Ledger (persistent consequences)
    +-- NPC Memory (per-NPC conversation history)
    +-- Save/Load System (session persistence)
```

## Quick Start

### Backend (Raspberry Pi or any Linux)
```bash
cd frp-backend
python -m venv ../venv && source ../venv/bin/activate
pip install -r requirements.txt
python main.py
# API running at http://localhost:8000
```

### Client (Windows/Mac/Linux)
1. Install [Godot 4.6](https://godotengine.org/download)
2. Open `godot-client/project.godot`
3. Set backend URL in `autoloads/backend.gd`
4. Press F5 to play

## Project Structure

```
ember-rpg/
  docs/           # PRDs, GDD, research (19 PRDs)
  frp-backend/    # Python backend (830+ tests, 96% coverage)
  godot-client/   # Godot 4.6 game client
  ROADMAP.md      # Development roadmap
```

## Current State

- **Backend**: 830+ tests, LLM-powered DM, NPC memory, combat, save/load
- **Client**: Tile map, entity rendering, fade-in reveal, AI narrative display
- **Phase**: Active development — backend production-ready, client in progress

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Game Client | Godot 4.6 (GDScript, Compatibility renderer) |
| Backend | Python 3.13, FastAPI, Uvicorn |
| AI Models | Claude Haiku 4.5 (narrative), Claude Sonnet 4.6 (key moments) |
| Database | JSON files + SQLite (save system) |
| Hosting | Raspberry Pi 5 (backend), any PC (client) |
| CI/CD | GitHub Actions (planned) |

## Documentation

All design documents are in `docs/`:
- `PRD_STANDARD.md` — Template all PRDs follow
- `PRD_*.md` — 19 Product Requirement Documents
- `GDD_v2.md` — Game Design Document
- `RESEARCH.md` — Market research and competitor analysis
- `ROADMAP.md` — Development phases and milestones

## License

Open source — code is free, game assets are proprietary.

## Credits

Built by [msbel5](https://github.com/msbel5) with Alcyone (AI companion on Raspberry Pi 5).

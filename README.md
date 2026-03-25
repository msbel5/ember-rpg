# Ember RPG

A 2D fantasy RPG with **AI-generated unique art**, **real tabletop mechanics**, and a **living world simulation** inspired by Dwarf Fortress. Every playthrough looks different, feels different, and tells a unique story.

## What Makes This Different

| Feature | AI Dungeon | BG3 | Dwarf Fortress | Ember RPG |
|---------|:---:|:---:|:---:|:---:|
| Real game mechanics (dice, stats, combat) | No | Yes | No | **Yes** |
| AI-generated narrative | Yes | No | No | **Yes** |
| AI-generated unique art | No | No | No | **Yes** |
| Persistent NPC memory | No | No | Yes | **Yes** |
| World simulation (DF-style) | No | Scripted | **Yes** | **Yes** |
| Consequence cascading | No | Partial | **Yes** | **Yes** |
| Open source | No | No | Yes | **Yes** |

## Architecture

```
Godot 4.6 Client (PC/Web)
    |
    | HTTP REST API
    |
FastAPI Backend (Python 3.11+)
    |
    +-- GameSession (canonical runtime state: world, map, entities, quests, inventory)
    +-- Game Engine (deterministic rules, combat, crafting, world tick)
    +-- LLM Router (Claude Haiku / Sonnet / GPT fallback via Copilot API)
    +-- Living World Systems (NPC schedules, rumors, economy, consequences)
    +-- Full-Fidelity Save/Load (named slots + autosave restore)
    +-- Terminal + Client Surfaces (shared map/spatial state)
```

## Quick Start

### Backend (Raspberry Pi or any Linux)
```bash
cd frp-backend
python3 -m venv ../venv && source ../venv/bin/activate
pip install -r requirements.txt
python3 main.py
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

## Current State (March 2026)

- **Backend**: 1700+ tests, deterministic combat/magic/crafting, named-slot save/load, autosave restore, living-world NPC simulation
- **Runtime**: `GameSession` is the canonical state for API, autosave, inventory/equipment, quests, and top-down rendering
- **Living World**: NPC schedules and patrols move on the live spatial index every action; rumors, caravans, economy, and quest timers tick in the same loop
- **Client**: First-person POV + tile map, AI narrative, shared session map rendering, live inventory/equipment state
- **AI Art**: HuggingFace Flux Schnell integration tested (free, ~3s/image)
- **Inspiration**: Dwarf Fortress (world sim), BBC Hitchhiker's Guide (illustrated text adventure), Doom (POV)
- **Phase**: Active development — backend core loop unified, Godot presentation and content breadth expanding

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Game Client | Godot 4.6 (GDScript, Compatibility renderer) |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| AI Models | Claude Haiku 4.5 (narrative), Claude Sonnet 4.6 (key moments) |
| Persistence | JSON save slots + autosave snapshots |
| Hosting | Raspberry Pi 5 (backend), any PC (client) |
| CI/CD | GitHub Actions (planned) |

## Documentation

All design documents are in `docs/`:
- `PRD_STANDARD.md` — Template all PRDs follow
- `PRD_*.md` — 20 Product Requirement Documents
- `PRD_asset_pipeline.md` — **NEW** AI-generated layered art system
- `GDD_v3.md` — **NEW** Game Design Document (DF-inspired world sim + AI art)
- `GDD_v2.md` — Core mechanics reference
- `RESEARCH.md` — Market research and competitor analysis
- `ROADMAP.md` — Development phases and milestones

## License

Open source — code is free, game assets are proprietary.

## Credits

Built by [msbel5](https://github.com/msbel5) with Alcyone (AI companion on Raspberry Pi 5).

# Ember RPG

A top-down RPG with **deterministic world simulation**, **real tabletop mechanics**, and an **AI enrichment layer**. Inspired by Daggerfall, Bard's Tale, Dwarf Fortress, RimWorld, Zork, and Hitchhiker's Guide to the Galaxy.

## Design Philosophy

**Deterministic first, AI second.** The game engine runs a fully algorithmic world — NPCs have schedules, economies tick, quests trigger from world state, combat resolves with dice. The entire game works without any LLM calls. AI layers (DM narration, NPC conversation, world description) are hooked in via API interfaces to enrich — not replace — the deterministic simulation.

Each conscious entity (NPC, DM) will have its own persistent session so it remembers context across interactions. The LLM layer makes the world feel alive; the deterministic layer makes it actually alive.

## Architecture

```
Godot 4.6 Client (PC)
    |
    | HTTP REST API (campaign-first routes)
    |
FastAPI Backend (Python 3.11+)
    |
    +-- CampaignSession (canonical state: world, map, entities, quests, inventory)
    +-- Game Engine (deterministic rules, combat, crafting, world tick)
    +-- LLM Router (Claude / GPT via Copilot API — optional enrichment)
    +-- Living World (NPC schedules, rumors, economy, consequences)
    +-- Save/Load (named slots + autosave)
    +-- Content Adapters (fantasy_ember, scifi_frontier)
```

## Quick Start

### Backend
```bash
cd frp-backend
python3 -m venv ../venv && source ../venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Client
1. Install [Godot 4.6](https://godotengine.org/download)
2. Open `godot-client/project.godot`
3. Set backend URL in `autoloads/backend.gd` line 5
4. Press F5 to play

## Project Structure

```
ember-rpg/
  docs/              # 53 PRDs, GDD, QA artifacts, research
  docs/qa/           # VQR scorecard, bug registry, play logs
  frp-backend/       # Python backend (1700+ tests, 96% coverage)
  godot-client/      # Godot 4.6 game client (183 headless tests)
```

## Current State (March 2026)

- **Backend**: Deterministic combat, magic (50+ spells), crafting, economy, living-world NPC simulation, campaign-first API, full save/load
- **Client**: Top-down tile map, tab-based sidebar (Narrative/Hero/Town/Quests/Items/Map), entity rendering with authored sprites, AI narrative panel
- **Adapters**: `fantasy_ember` (medieval fantasy), `scifi_frontier` (space opera)
- **VQS**: 5.0/10 — minimum demo bar reached, not impressive yet
- **Next**: Deterministic world generation, deeper interaction, animation, atmospheric density

## Roadmap Vision

1. **Now**: Algorithmic deterministic world (Daggerfall/DF quality procedural generation)
2. **Next**: API hooks for DM interface + NPC agent sessions (each NPC remembers)
3. **Then**: LLM enrichment layer on top of working deterministic base
4. **Future**: 3D world rendering (Bard's Tale 4 style), persistent universe

## Documentation

- `docs/PRD_IMPLEMENTATION_MATRIX.md` — Master doc governance (authoritative vs superseded)
- `docs/PRD_STANDARD.md` — Template all PRDs follow
- `docs/PRD_godot_client.md` — Current client contract
- `docs/qa/vqr_scorecard.md` — Visual quality tracking
- `docs/qa/bug_registry.md` — Known issues

> **Note**: Many early PRDs (living_simulation_v1, world_generation_v2, map_generator, etc.) are **superseded** per the Implementation Matrix. See `PRD_IMPLEMENTATION_MATRIX.md` for which docs are authoritative.

## License

Open source — code is free, game assets are proprietary.

## Credits

Built by [msbel5](https://github.com/msbel5) with Alcyone (AI companion on Raspberry Pi 5).

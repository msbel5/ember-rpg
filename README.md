# Ember RPG

Ember RPG is a Godot-first colony-command RPG built on a deterministic Python backend. The shipped player surface is the Godot client; terminal-first and legacy compatibility paths are deprecated.
Ember is created by fully ai and this cause some problems, wordl tick and automation control tick syncs and everything correctly placed and moves but world stutters on every tick. Because ai can comprehend every tile and every object it passes every visual check but humans cannot percive or recall this much information.


https://github.com/user-attachments/assets/758a38c6-ffbb-43d0-b9ff-7b897a933017


## Current Product Surface

- Godot 4.6 client for title, creation, gameplay, save/load, and semantic desktop proof
- FastAPI backend with campaign-first routes and canonical kernel payload slices
- Two active adapters: `fantasy_ember` and `scifi_frontier`
- Deterministic simulation for actors, effects, jobs, colony pressure, stores, travel, and systems closure

## Local Quick Start

### Backend

```bash
cd frp-backend
python -m venv ..\\venv
..\\venv\\Scripts\\activate
pip install -r requirements.txt
python dev_server.py --port 8741
```

### Godot Client

1. Install [Godot 4.6](https://godotengine.org/download).
2. Open [project.godot](C:/Users/msbel/projects/ember-rpg/godot-client/project.godot).
3. Press `F5`.
4. In debug/editor runs, `BackendRuntime` will prefer `EMBER_RPG_BACKEND_URL`, then the configured URL, then managed local bootstrap on port `8741`.

## Repo Layout

```text
ember-rpg/
  docs/              authoritative PRDs, architecture docs, QA signoff, generated matrix
  frp-backend/       FastAPI backend, deterministic runtime, tests, audit tools
  godot-client/      Godot scenes, autoloads, UI/gameplay scripts, automation fixtures
  tools/             local developer reset and support scripts
```

## Documentation

- [PRD_IMPLEMENTATION_MATRIX.md](C:/Users/msbel/projects/ember-rpg/docs/PRD_IMPLEMENTATION_MATRIX.md): generated authoritative documentation inventory
- [ember_mechanics_canon_v1.md](C:/Users/msbel/projects/ember-rpg/docs/architecture/ember_mechanics_canon_v1.md): canonical DF + GemRB synthesis map
- [PRD_godot_client.md](C:/Users/msbel/projects/ember-rpg/docs/prd/active/PRD_godot_client.md): active Godot runtime contract
- [PRD_automation_authority_v1.md](C:/Users/msbel/projects/ember-rpg/docs/prd/active/PRD_automation_authority_v1.md): semantic automation authority
- [runtime_authority.md](C:/Users/msbel/projects/ember-rpg/docs/architecture/runtime_authority.md): canonical live runtime slice rules
- [godot-crpg-shell-authority](C:/Users/msbel/projects/ember-rpg/.agents/skills/godot-crpg-shell-authority/SKILL.md): project-local shell authority checklist for any Godot shell rewrite or review

Active PRDs live only under `docs/prd/active`. Superseded PRDs and planning notes live under `docs/deprecated`.

## Verification Lanes

- Manual Godot runtime from a clean reset is the primary truth lane
- Backend targeted pytest for campaign creation, save/load, and runtime projections
- Headless Godot regression via `godot-client/tests/run_headless_tests.gd`
- Semantic desktop proof via `godot-client/tests/automation`
- Long `100` / `500` turn chaos runs are soak lanes, not the default release gate

## License

Source code is open; shipped game assets remain proprietary unless explicitly marked otherwise.

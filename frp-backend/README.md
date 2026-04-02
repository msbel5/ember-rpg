# Ember RPG — Backend

FastAPI backend for Ember RPG’s deterministic campaign runtime. The active product surface is campaign-first and Godot-first; terminal-first play and backwards-compatibility shims are deprecated.

## Current Responsibilities

- Campaign creation and finalization
- Canonical runtime slices: `world_state`, `game_state`, `actors`, `jobs`, `reactions`, `worksites`, `colony_pressure`, `production_ledger`, `stores`, `systems`
- Deterministic command routing, travel, save/load, and runtime projection
- Content adapters for `fantasy_ember` and `scifi_frontier`
- Optional enrichment hooks without replacing deterministic authority

## Quick Start

```bash
cd frp-backend
python -m venv ..\\venv
..\\venv\\Scripts\\activate
pip install -r requirements.txt
python dev_server.py --port 8741
```

Interactive docs are available at [http://127.0.0.1:8741/docs](http://127.0.0.1:8741/docs).

## Active Route Families

Base URL: `http://127.0.0.1:8741/game`

- `GET /health/campaign-client`
- `GET /campaigns/creation/catalog`
- `POST /campaigns/creation/start`
- `POST /campaigns/creation/{creation_id}/answer`
- `POST /campaigns/creation/{creation_id}/reroll`
- `POST /campaigns/creation/{creation_id}/save-roll`
- `POST /campaigns/creation/{creation_id}/swap-roll`
- `POST /campaigns/creation/{creation_id}/finalize`
- `GET /campaigns/{campaign_id}`
- `GET /campaigns/{campaign_id}/region`
- `GET /campaigns/{campaign_id}/settlement`
- `POST /campaigns/{campaign_id}/commands`
- `POST /campaigns/{campaign_id}/save`
- `GET /campaigns/saves`
- `POST /campaigns/load/{save_id}`

Legacy `/session/*` routes remain only for deprecated tooling and are not part of the active shipped Godot loop.

## Local Verification

```bash
python -m pytest tests/test_campaign_api_v2.py tests/test_campaign_creation_v2.py tests/test_campaign_save_load_v2.py -q
python -m pytest tests/test_doc_inventory.py -q
```

## Important Docs

- [PRD_save_load.md](C:/Users/msbel/projects/ember-rpg/docs/prd/active/PRD_save_load.md)
- [PRD_macro_society_runtime_v1.md](C:/Users/msbel/projects/ember-rpg/docs/prd/active/PRD_macro_society_runtime_v1.md)
- [runtime_authority.md](C:/Users/msbel/projects/ember-rpg/docs/architecture/runtime_authority.md)
- [runtime_module_map.md](C:/Users/msbel/projects/ember-rpg/docs/runtime_module_map.md)

## Notes

- Default local port is `8741`.
- Canonical saves live under `frp-backend/saves`.
- `tools/reset_dev_state.py` is the clean baseline reset used by desktop and headless proof lanes.

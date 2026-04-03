# Ember RPG — Backend

Deterministic kernel RPG backend. HTTP for bootstrap/creation/save/load, WebSocket for live runtime.

## Architecture

- **Kernel** (`engine/kernel/`) — single source of truth for all game rules
- **CampaignRuntime** (`engine/api/campaign/runtime.py`) — orchestration authority
- **WebSocket** (`engine/api/ws_campaign.py`) — primary live runtime transport
- **CampaignTickLoop** (`engine/api/campaign/tick_loop.py`) — async idle world simulation
- **Godot client** — thin state consumer and command sender

All legacy session-first routes have been deleted. There is one authority model.

## Quick Start

```bash
cd frp-backend
python -m venv ..\\venv
..\\venv\\Scripts\\activate
pip install -r requirements.txt
python dev_server.py --port 8741
```

## HTTP Routes (bootstrap/admin only)

Base: `http://127.0.0.1:8741/game`

- `GET /health/campaign-client`
- `GET /campaigns/creation/catalog`
- `POST /campaigns/creation/start` / `answer` / `reroll` / `save-roll` / `swap-roll` / `finalize`
- `POST /campaigns` (direct create)
- `GET /campaigns/{id}` / `DELETE /campaigns/{id}`
- `GET /campaigns/{id}/region/current` / `settlement/current`
- `POST /campaigns/{id}/save` / `GET saves` / `POST load/{save_id}` / `DELETE saves/{save_id}`

## WebSocket Transport (primary runtime)

Endpoint: `ws://127.0.0.1:8741/game/ws/campaigns/{campaign_id}`

- Client sends: `{"type": "command", "input": "attack goblin"}`
- Server pushes: `{"type": "state", ...}`, `{"type": "tick", ...}`, `{"type": "pong"}`

## Kernel-Authoritative Command Dispatch

Commands routed through campaign runtime:
- **Travel**: `travel <destination>`
- **Commander**: `assign`, `prioritize`, `build`, `draft`, `recruit`, `defend`
- **Commerce**: `buy <item>`, `sell <item>`, `rent room`, `identify <item>`
- **Medical**: `diagnose <target>`, `treat <target>`, `surgery <target>`
- **Avatar**: any other text routed to GameEngine

## Verification

```bash
python -m pytest tests/test_creation_contract.py tests/test_tick_loop.py tests/test_websocket_runtime.py tests/test_dialog_kernel_bridge.py tests/test_kernel_bridges.py tests/test_no_legacy_imports.py -v
```

## Notes

- Default local port is `8741`.
- Canonical saves live under `frp-backend/saves`.
- `tools/reset_dev_state.py` is the clean baseline reset used by desktop and headless proof lanes.

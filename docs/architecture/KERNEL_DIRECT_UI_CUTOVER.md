# Kernel Direct UI Cutover

## Current Backend Authority

- Rules authority lives in `frp-backend/engine/kernel/*`.
- Campaign lifecycle authority lives in `frp-backend/engine/api/campaign/runtime.py`.
- Command dispatch authority lives in `frp-backend/engine/api/campaign/runtime_commands.py`.
- HTTP remains active for creation, bootstrap, snapshot, save, load, and delete via `frp-backend/engine/api/campaign_routes.py`.
- WebSocket is the primary live runtime transport after campaign creation via `frp-backend/engine/api/ws_campaign.py`.

## Current Runtime Dispatch

`CampaignRuntime.run_command()` routes commands in this order:

1. `travel`
2. commander commands
3. dialog commands
4. commerce commands
5. medical commands
6. combat bridge
7. gameplay bridge
8. legacy avatar fallback through `GameEngine.process_action(...)`

Current specialized surfaces:

- Combat: `frp-backend/engine/api/combat_bridge.py`
- Equipment, inventory, craft, rest, spell: `frp-backend/engine/api/gameplay_bridge.py`
- Kernel gameplay helpers: `frp-backend/engine/kernel/gameplay.py`
- Dialog, commerce, medical: `frp-backend/engine/api/campaign_commands.py`

The avatar fallback still exists. Frontend cutover is blocked until the validation gates are green and the remaining backend cleanup is complete.

## Deleted Compatibility Surface

The backend now expects these deleted wrappers and handler shims to stay deleted:

- `frp-backend/engine/api/game_session.py`
- `frp-backend/engine/api/save_system.py`
- `frp-backend/engine/api/handlers/combat_handlers.py`
- `frp-backend/engine/api/handlers/exploration_handlers.py`
- `frp-backend/engine/api/handlers/helpers.py`
- `frp-backend/engine/api/handlers/inventory_handlers.py`
- `frp-backend/engine/api/handlers/social_handlers.py`

The guard tests fail if these files or imports are reintroduced.

## Current Validation Status

The current backend validation gate is green for the core runtime and guard-rail suites listed below.

Remaining non-blocking architectural gaps:

- progression still uses the data-driven `_check_level_up()` adapter in `engine/api/campaign/live_kernel.py`
- spell casting uses a thin adapter in `engine/kernel/gameplay.py` that bridges registry spell data into kernel `begin_casting()` / `resolve_cast()`
- combat runtime smoke must use canonical session/world actors; ad-hoc injection into `context.kernel_runtime["actors"]` is not stable because runtime snapshot generation rebuilds actors from session state before dispatch

## Validation Gates

Run these before any UI work:

```bash
python -m pytest frp-backend/tests/test_campaign_save_load_v2.py frp-backend/tests/test_combat_bridge.py frp-backend/tests/test_gameplay_commands.py frp-backend/tests/test_progression_integration.py frp-backend/tests/test_campaign_logic_live.py frp-backend/tests/test_runtime_gameplay_integration.py frp-backend/tests/test_no_legacy_imports.py frp-backend/tests/test_backend_runtime_contract.py -q
```

```bash
rg "engine\.api\.game_session|engine\.api\.save_system|combat_handlers|exploration_handlers|helpers\.py|inventory_handlers|social_handlers" frp-backend/engine -S
```

Runtime smoke expectations:

- create campaign succeeds
- `runtime.run_command(..., "rest")` returns `command_type == "rest"`
- a combat command resolves as `command_type == "combat"`
- save then load roundtrip succeeds
- idle/environmental tick suite is green
- pickup/drop runtime integration is green
- no deleted wrapper import or file has been reintroduced

## Release Rule

Godot shell and WS client work stay blocked unless the combined validation gate remains green after every backend merge.

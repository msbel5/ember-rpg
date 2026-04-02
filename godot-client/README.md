# Ember RPG — Godot Client

Godot 4.6 player-facing client for Ember RPG. This is the active shipped surface for title, creation, gameplay, save/load, and semantic UI proof.

## Requirements

- Godot 4.6+ (standard build, not .NET)
- Local backend available through `BackendRuntime`
- Default local backend port: `8741`

## Runtime Bootstrap

- `autoloads/backend.gd` is the HTTP client only.
- `autoloads/backend_runtime.gd` resolves and validates the backend URL for manual editor runs and automation.
- Resolution order:
  1. `EMBER_RPG_BACKEND_URL`
  2. configured project URL
  3. preferred local probe ports
  4. managed debug bootstrap

If the campaign contract is unavailable, the title scene blocks creation and shows backend diagnostics instead of opening an empty wizard.

## Play Loop

1. Run `python tools/reset_dev_state.py`
2. Open [project.godot](C:/Users/msbel/projects/ember-rpg/godot-client/project.godot)
3. Press `F5`
4. Create a new campaign or continue a canonical save

## Controls

| Key | Action |
| --- | --- |
| `Enter` | Focus command bar / activate current prompt |
| `WASD` / Arrow Keys | Camera pan or focused UI navigation |
| `Home` | Re-center camera on player |
| Mouse wheel | Zoom |
| Middle mouse drag | Pan camera |
| `F5` | Quicksave during gameplay |
| `F9` | Open save/load panel |
| `Esc` | Close modal overlay / cancel focused flow |
| `F12` | Capture visual proof screenshot |

## Active Layout

- `1600x900` is the primary desktop target.
- `1280x720` is supported as a degraded fallback.
- The gameplay shell is:
  - status bar on top
  - world viewport center-left
  - sidebar panels on the right
  - command / action bar on the bottom

## Project Structure

```text
godot-client/
  autoloads/          backend, backend_runtime, game_state
  scenes/             title screen, title menu, gameplay session
  scripts/ui/         creation, overlays, panels, save sync, theming
  scripts/world/      world viewport, camera, entity rendering, interaction
  tests/              headless regression and semantic desktop automation
```

## Automation

- Headless Godot is the authoritative UI regression lane.
- Win32 desktop is the semantic real-window proof lane.
- Critical scenarios must use semantic node visibility/text assertions instead of monitor-space clicks.

## Active Backend Contract

- `POST /game/campaigns/creation/start`
- `POST /game/campaigns/creation/{creation_id}/answer`
- `POST /game/campaigns/creation/{creation_id}/reroll`
- `POST /game/campaigns/creation/{creation_id}/finalize`
- `POST /game/campaigns/{campaign_id}/commands`
- `POST /game/campaigns/{campaign_id}/save`
- `GET /game/campaigns/saves`
- `POST /game/campaigns/load/{save_id}`

Legacy session-first gameplay is deprecated and not part of the active client contract.

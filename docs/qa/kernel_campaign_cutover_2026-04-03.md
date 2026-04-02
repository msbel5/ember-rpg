# Kernel Campaign Cutover QA Log

Date: 2026-04-03

## Scope

- Campaign-first API only
- Canonical save schema v3
- Ember stat routing in kernel combat/effects
- D&D turn resources in backend payloads and Godot shell
- Godot shell contract cutover away from legacy session routes

## Automated Proof

Backend pytest:

```powershell
cd C:\Users\msbel\projects\ember-rpg\frp-backend
pytest tests/test_actor_kernel.py tests/test_campaign_api_v2.py tests/test_campaign_save_load_v2.py -q
```

Result:

- `19 passed in 48.88s`

Godot headless:

```powershell
godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client --script res://tests/run_headless_tests.gd
```

Result:

- `All Godot headless tests passed.`

## Desktop Smoke

- Real Godot title shell launched on desktop.
- Visual proof artifacts captured:
  - `C:\Users\msbel\projects\ember-rpg\artifacts\desktop_smoke.png`
  - `C:\Users\msbel\projects\ember-rpg\artifacts\desktop_smoke_after_new_game.png`
- `computer_use` low-level tools worked for screen capture and click injection.
- `computer_task` remained broken in this environment with:
  - `Messages.create() got an unexpected keyword argument 'betas'`

## Notes

- Legacy `/game/session/*` and `/game/saves/*` runtime routes are no longer mounted in `main.py`.
- The repo still contains legacy modules on disk outside the active runtime path; this cutover removed runtime authority first.

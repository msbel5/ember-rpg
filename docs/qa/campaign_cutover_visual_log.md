# Campaign Cutover Visual Log

## Scope
- Date: 2026-03-27
- Backend target: `http://127.0.0.1:8000`
- Godot target: `godot-client/project.godot`
- Adapters exercised visually: `fantasy_ember`

## Evidence
- Title screen proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/title/title_screen_2026-03-27T18-51-04.png`
- Campaign creation proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T19-01-50.png`
- Settlement command proof (`Defend` -> `Fortified`):
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T19-02-31.png`
- Campaign save proof (`Quick Save`):
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T19-03-08.png`

## Findings
- Fixed: client was still pointed at stale backend port `8765`; updated to `8000`.
- Fixed: status bar and command bar were visually clipped because the sidebar layout overflowed the viewport; converted the sidebar to a scroll container.
- Fixed: campaign payload AP parsing crashed the status bar refresh path, which left the live location label stuck at `Unknown`.
- Verified: campaign creation, settlement quick action dispatch, narrative update, AP display, location label, and quick save all worked in the graphical client.

## Remaining Gaps
- `scifi_frontier` still needs the same non-headless visual pass.
- Full 100-turn visual pass and 30-minute free play per adapter are still pending.
- RimWorld benchmark evidence doc is not yet updated with screenshot-backed scores from this pass.

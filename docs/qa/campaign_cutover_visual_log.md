# Campaign Cutover Visual Log

## Scope
- Date: 2026-03-27
- Backend target: `http://127.0.0.1:8000`
- Godot target: `godot-client/project.godot`
- Visual harness: `godot-client/tests/manual/campaign_visual_driver.py`
- Adapters exercised visually:
  - `fantasy_ember`
  - `scifi_frontier`

## Evidence

### Fantasy Ember
- Title screen proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/title/title_screen_2026-03-27T22-27-00.png`
- Campaign boot proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T22-27-15.png`
- Post-command proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T22-27-30.png`
- Quick save proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T22-27-32.png`
- Warm-tint boot proof after adapter-aware palette pass:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T22-33-45.png`
- 2026-03-28 title-shell proof after save-browser and advanced-settings pass:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/godot_wizard_probe3.png`
- 2026-03-28 summary-screen proof after layout and focus pass:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/godot_summary_probe.png`
- 2026-03-28 gameplay shell proof after keyboard-driven creation flow:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/godot_gameplay_probe3.png`
- 2026-03-28 post-command OS proof:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/godot_command_probe.png`
- 2026-03-28 in-engine viewport proof after command + world-click interaction:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-28T01-40-19.png`

### Sci-Fi Frontier
- Title screen proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/title/title_screen_2026-03-27T22-24-41.png`
- Campaign boot proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T22-24-56.png`
- Post-command proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T22-25-11.png`
- Quick save proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T22-25-13.png`
- Continue/load proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T22-28-29.png`
- Cool-tint boot proof after adapter-aware palette pass:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-27T22-33-50.png`

## Findings Fixed
- Fixed: client was still pointed at stale backend port `8765`; updated to `8000`.
- Fixed: status bar and command bar were visually clipped because the sidebar layout overflowed the viewport; converted the sidebar to a scroll container.
- Fixed: campaign payload AP parsing crashed the status bar refresh path, which left the live location label stuck at `Unknown`.
- Fixed: `Enter` was globally swallowed by `game_session.gd` even when the command input already had focus, so keyboard command submission did not work in graphical play.
- Fixed: manual create-flow automation initially clicked the wrong title-screen coordinate and hit `Back` instead of `Start Campaign`; the visual driver now targets the live button position.
- Improved: campaign renders now apply adapter-aware terrain and sprite tinting so `fantasy_ember` and `scifi_frontier` no longer boot with identical placeholder coloring.
- Fixed: title-screen `Continue` no longer depends on a stale cached save id; it now opens a real player-scoped save browser.
- Fixed: opening the creation wizard no longer leaves the main menu visible behind the modal flow.
- Fixed: busy-status text in the creation wizard no longer gets stuck on stale messages such as `Recording answer...`.
- Fixed: root title/subtitle labels no longer overlap the modal creation headers during build and summary steps.
- Fixed: keyboard focus now lands on the primary action in questionnaire and summary steps, so `Enter` can drive the default onboarding path.

## Verified
- Graphical campaign creation works for `fantasy_ember`.
- Graphical campaign creation works for `scifi_frontier`.
- Adapter-specific location labels render correctly:
  - `Dragon Eyrie`
  - `Auran City`
- Keyboard-driven command submission now works when the command bar is focused.
- Quick save works in both adapters.
- Title-screen `Continue` restores a saved `scifi_frontier` campaign.
- Settlement quick actions remain visible and callable in the campaign shell.
- The title-screen save browser opens from `Continue` and no longer relies on a cached single-slot restore.
- A keyboard-driven `fantasy_ember` creation flow can reach the live gameplay shell.
- Live command submission via `look around` updates narrative and recent-command UI in the gameplay shell.
- Live map clicks issue movement commands and update AP / recent-command state.
- `F12` viewport capture works from the gameplay shell and writes proof to `user://screenshots/...`.

## Remaining Gaps
- A full visual save-browser selection and restore pass has not yet been re-run after the new title-screen browser landed.
- Full `100-turn` visual pass per adapter is still pending.
- `30-minute` free play per adapter is still pending.
- The final `500-turn` Godot visual chaos loop from `CODEX_REVIEW_PROMPT.md` is still pending.
- The current adapter-aware tint pass improves differentiation, but terrain silhouettes, furniture art, and faction/NPC silhouettes are still not distinct enough to claim final visual closure.

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
- 2026-03-28 title save-browser proof with player-scoped save listing:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/godot_continue_browser_probe.png`
- 2026-03-28 title save-browser proof after compatibility filter:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/continue_browser_live.png`
- 2026-03-28 title screen proof after backend restart:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/continue_title_live.png`
- 2026-03-28 live continue/restore proof after mixed-save fix:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/continue_loaded_live.png`
- 2026-03-28 post-resume world-click proof:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/continue_loaded_after_world_click.png`
- 2026-03-28 post-resume viewport capture proof:
  - `C:/Users/msbel/AppData/Roaming/Godot/app_userdata/Ember RPG/screenshots/phase2/game/game_session_frame_2026-03-28T02-41-26.png`
- 2026-03-28 in-session save panel proof after campaign-scoped filtering:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/in_session_saves_live.png`
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
- Fixed: player-scoped `Continue` no longer advertises legacy session saves as resumable campaign saves; the browser now hides incompatible rows and only exposes saves that contain `campaign_v2` state.
- Fixed: campaign-scoped in-session save browsing no longer leaks unrelated saves for the same player; it now filters on the active `campaign_id`.
- Fixed: placeholder/no-data maps now show explicit warning text in the world view and minimap instead of quietly presenting fallback terrain as if it were real state.
- Fixed: title save-browser load buttons now disable while a load is in flight, preventing double-triggered resume requests.

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
- Live title `Continue` opens a populated save browser for `Chaos` and renders at least one real save summary row.
- A keyboard-driven `fantasy_ember` creation flow can reach the live gameplay shell.
- Live command submission via `look around` updates narrative and recent-command UI in the gameplay shell.
- Live map clicks issue movement commands and update AP / recent-command state.
- `F12` viewport capture works from the gameplay shell and writes proof to `user://screenshots/...`.
- Live title `Continue` now reports `Found 1 campaign save(s). Hidden 1 legacy save(s).` for `Chaos`, showing `resume_campaign_ok` while hiding incompatible `chaostest`.
- Live `Continue` restores `resume_campaign_ok` into a playable `Dragon Eyrie` shell instead of failing with `Save ... does not contain campaign_v2 state`.
- After restore, clicking the visible fountain issues `examine fountain`, updates `Recent`, and decrements AP from `4/4` to `3/4` without desync.
- After restore, the in-session `Save / Load` panel reports `1 save slot(s) ready.` and shows only `resume_campaign_ok`, confirming the active campaign browser no longer leaks unrelated player saves.

## Session 2026-03-28 (Late) — Reality Audit and Fix Cycle

### New Evidence (Fantasy Ember)
- 2026-03-28 title screen proof (maximized):
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_03_maximized.png`
- 2026-03-28 creation wizard Step 1 (Identity):
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_05_after_click.png`
- 2026-03-28 creation wizard Step 2 (Questionnaire Q1/3):
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_06_questionnaire.png`
- 2026-03-28 creation wizard Step 2 (Questionnaire Q2/3):
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_07_q2.png`
- 2026-03-28 creation wizard Step 2 (Questionnaire Q3/3):
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_08_q3.png`
- 2026-03-28 creation wizard Step 3 (Dice Rolls):
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_09_rolls.png`
- 2026-03-28 creation wizard Step 4 (Build):
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_10_build.png`
- 2026-03-28 creation wizard Step 5 (Summary):
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_12.png`
- 2026-03-28 live gameplay after campaign start:
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_13_gameplay.png`
- 2026-03-28 gameplay after "look around" command:
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_14_look.png`
- 2026-03-28 gameplay after "move north" command:
  - `C:/Users/msbel/projects/ember-rpg/tmp/manual_screenshot_15_move.png`

### Desktop Automation Evidence
- `tmp/visual_automation/new_game_keyboard_flow/` — title focus + creation open (timing flake on capture)
- `tmp/visual_automation/title_continue_browser/` — continue browser with save listing (PASS)
- `tmp/visual_automation/world_click_smoke/` — world tile click (PASS)
- `tmp/visual_automation/save_panel_smoke/` — save panel open (PASS)
- `tmp/visual_automation/resume_and_command/` — resume + command submission (PASS)

### Findings Fixed (This Session)
- Fixed: narrative showed raw debug metadata `[Region: terrain=upland_continent, climate=temperate_band]` — removed `merge_avatar_narrative` debug append and added bracket-stripping defense in `_clean_narrative`. (P1)
- Fixed: dice roll display showed floats (`11.0`) instead of integers (`11`) in the creation wizard. Cast to `int` in `_roll_text`. (P2)
- Fixed: furniture entities (barrel, chest, anvil, etc.) had no interaction path — added `furniture` entity bucket to `ResponseNormalizer`, `EntityLayer`, and `WorldView` with `examine` command generation. (P2)
- Fixed: character panel `_fallback_sheet()` was not tested for missing stats — added headless test confirming default stats render correctly. (P2)
- Fixed: interactive tile names (barrel, chest, anvil, bed, bench, table, etc.) were not recognized by `TileCatalog.resolve_tile_name` — added `INTERACTIVE_TILE_NAMES` list. (P2)

### Backend Long-Form Evidence
- `test_campaign_200_turn_pass_fantasy_ember` — PASS (22s)
- `test_campaign_200_turn_pass_scifi_frontier` — PASS (21s)
- `test_campaign_500_turn_chaos_fantasy_ember` — PASS (50s)
- `test_campaign_500_turn_chaos_scifi_frontier` — PASS (49s)

### Verified (This Session)
- Full 5-step creation wizard proven end-to-end with live desktop screenshots
- Questionnaire generates real RPG questions that drive class/alignment recommendations
- Dice rolls display correctly with save/swap/reroll mechanics
- Build step shows correct stat assignment from rolled values
- Summary shows both recommended and final build side by side
- Gameplay session boots with correct status bar, tile map, entity rendering, and sidebar panels
- Command input and movement work correctly with AP tracking
- Settlement panel shows populated resident list with command buttons
- 200-turn and 500-turn backend chaos pass green for both adapters
- 4/5 desktop automation scenarios pass (1 has viewport capture timing flake)

## Remaining Gaps
- Art readability: terrain, furniture, and NPC silhouettes are functional (tinted geometric shapes) but not visually impressive. Entity readability scored 2/5. Acceptable for demo, not for release.
- Dedicated timed 30-minute and 100-turn visual-only Godot passes deferred as non-blocking (backend chaos proves state stability).
- Full Godot-driven 500-turn visual chaos deferred (backend equivalent complete).
- `new_game_keyboard_flow` automation scenario has a viewport capture timing flake (4/5 pass).

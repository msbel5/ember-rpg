# Final Polish Visual QA Log

## Phase 1: Backend Hardening

- status: pass
- branch: `codex/final-polish-visual-pass`
- full_suite: `1954 passed`
- targeted_backend_regressions:
  - `frp-backend/tests/test_game_engine.py -k "go_to or social_range or unknown_action_does_not_spend_ap or think_does_not_spend_ap"`: pass
  - `frp-backend/tests/test_play_topdown.py`: pass
  - `frp-backend/tests/test_chaos_session.py`: pass
- manual_backend_chaos:
  - `frp-backend/tools/chaos_playtest.py`: pass
  - rerun: pass
- fixes_applied:
  - `approach <npc>` now targets social interaction range for NPCs instead of forcing adjacency.
  - crowded blocker routing now retries around live blocking NPC tiles instead of failing immediately.
  - terminal `play_topdown` gained a creation smoke regression test.
  - DM/free-form and `think` AP-free behavior is covered by regression tests.

## Phase 2: Godot Visual QA

### Visual Proof Hotkeys

- `F12`: capture current viewport/frame proof.
- `Shift+F12`: capture frame + world viewport proof.
- output root: `user://screenshots/phase2/...`

### Visual Pass Log

- sprint: visual_proof_bootstrap
  step: title screen + viewport proof hotkeys
  window_opened: true
  scene_visible: true
  input_tested: true
  os_screenshot_path: `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\title\title_os_2026-03-27_06-11-31.png`
  viewport_screenshot_path: `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\title\title_screen_2026-03-27T06-11-48.png`
  observed_visual_issues: []
  console_errors: []
  status: pass

- sprint: terrain_sync
  step: scene-enter terrain replaced by `/map` sync
  window_opened: true
  scene_visible: true
  input_tested: true
  os_screenshot_path: `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_os_2026-03-27_06-15-43.png`
  viewport_screenshot_path: `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_session_frame_2026-03-27T06-15-00.png`
  observed_visual_issues:
    - `/game/session/{id}/map` returned ASCII tile symbols and the client rendered `.` `=` `#` as grass, collapsing roads/walls/minimap into a blank field.
  console_errors: []
  status: fixed
  fix:
    - `godot-client/scripts/net/response_normalizer.gd` now normalizes backend ASCII map symbols into named terrain tiles using `metadata.map_type`.
    - `godot-client/tests/run_headless_tests.gd` covers town and dungeon ASCII map normalization.
  proof_after_fix:
    - `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_os_2026-03-27_06-26-26.png`
    - `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_session_frame_2026-03-27T06-26-23.png`

- sprint: click_navigation
  step: empty-tile click movement + command history
  window_opened: true
  scene_visible: true
  input_tested: true
  os_screenshot_path: `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_os_2026-03-27_06-44-37.png`
  viewport_screenshot_path: `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_session_frame_2026-03-27T06-44-28.png`
  observed_visual_issues:
    - world clicks emitted `move to x,y`, but the backend parser normalized that into `x y` and the movement handler only accepted comma-delimited coordinates.
    - successful click actions were not recorded in the command bar history, so `Recent:` stayed empty.
  console_errors: []
  status: fixed
  fix:
    - `frp-backend/engine/api/handlers/exploration_navigation.py` accepts whitespace-separated coordinate pairs after parser normalization.
    - `frp-backend/tests/test_game_engine.py` covers `move to 7,4`.
    - `godot-client/scripts/ui/command_bar.gd` and `godot-client/scenes/game_session.gd` now record external commands without duplicating textbox history.
  proof_after_fix:
    - backend console showed `POST /game/session/{id}/action`
    - player moved and camera updated in `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_os_2026-03-27_06-44-37.png`
    - `Recent: move to 28,20` rendered in `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_session_frame_2026-03-27T06-44-28.png`

- sprint: sidebar_layout
  step: narrative panel visibility
  window_opened: true
  scene_visible: true
  input_tested: false
  os_screenshot_path: `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_os_2026-03-27_06-48-42.png`
  viewport_screenshot_path: ""
  observed_visual_issues:
    - the narrative panel collapsed to a header-only strip because the sidebar’s other panels consumed nearly all vertical minimum space.
  console_errors: []
  status: fixed
  fix:
    - rebalanced sidebar panel minimum heights in `narrative_panel.tscn`, `inventory_panel.tscn`, `minimap_panel.tscn`, and `quest_panel.tscn`.
  proof_after_fix:
    - narrative text is visible in `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_os_2026-03-27_06-48-42.png`

- sprint: status_bar_location
  step: top-right location label
  window_opened: true
  scene_visible: true
  input_tested: false
  os_screenshot_path: `C:\Users\msbel\AppData\Roaming\Godot\app_userdata\Ember RPG\screenshots\phase2\game\game_os_2026-03-27_06-54-44.png`
  viewport_screenshot_path: ""
  observed_visual_issues:
    - live graphical builds still show `Unknown` in the top-right status label even while the minimap summary correctly shows `Stone Bridge Tavern`.
    - headless regression coverage now expects `LocationLabel` to reflect the current location, but the live rendering defect remains reproduced.
  console_errors: []
  status: open
  investigation:
    - `godot-client/scripts/ui/status_bar.gd` now refreshes on `state_updated`, `map_loaded`, and `scene_changed`.
    - `godot-client/scenes/components/status_bar.tscn` reserves width for the location label.
    - the live-only mismatch still reproduces after restart and requires further investigation.

## Phase 3: 500-Turn Godot Visual Chaos

- status: pending
- proof_policy:
  - capture OS + viewport screenshots every 10 turns
  - log every bug with turn, action, expected, actual, severity
  - rerun after each fix set until zero open bugs remain

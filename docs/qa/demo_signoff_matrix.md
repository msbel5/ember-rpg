# Demo Signoff Matrix

## Scope
- Date: 2026-03-28 (updated)
- Release target: playable Ember RPG demo on the campaign-first stack
- Adapters in scope:
  - `fantasy_ember`
  - `scifi_frontier`
- Evidence sources:
  - `docs/qa/campaign_cutover_visual_log.md`
  - `docs/qa/rimworld_benchmark_report.md`
  - `docs/qa/vqr_scorecard.md`
  - `docs/qa/bug_registry.md`
  - `frp-backend/tests/test_campaign_creation_v2.py`
  - `frp-backend/tests/test_campaign_character_sheet.py`
  - `frp-backend/tests/test_campaign_api_v2.py`
  - `frp-backend/tests/test_campaign_save_load_v2.py`
  - `frp-backend/tests/test_campaign_region_map_adapter.py`
  - `frp-backend/tests/test_campaign_godot_payload_shapes.py`
  - `frp-backend/tests/test_campaign_chaos.py`
  - `frp-backend/tests/test_play.py`
  - `frp-backend/tests/test_play_topdown.py`
  - `godot-client/tests/run_headless_tests.gd`
  - `godot-client/tests/automation/` (scenario fixtures plus harness tests; only targeted fresh green coverage is credited below)
  - `tmp/visual_qa/baseline/`
  - `tmp/visual_automation/` (desktop automation evidence)
  - `tmp/manual_screenshot_*.png` (manual QA screenshots)

## Contract Lock

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Campaign-first route family is the documented player-facing contract | Green | `docs/PRD_save_load.md`, `docs/PRD_godot_client.md` | Docs | Active flow is `/game/campaigns/...`; legacy session routes remain compatibility-only. |
| Character-sheet payload is documented consistently across backend, terminal, and Godot | Green | `docs/PRD_character_system.md` | Docs | Uses the shipped `stats[]`, `skills[]`, `resources`, and `creation_summary` shape. |
| Demo-blocking docs classify current closure gates correctly | Green | `docs/PRD_IMPLEMENTATION_MATRIX.md`, this file | Docs | Remaining release blockers are tracked below instead of being implied as done. |

## Backend and Terminal Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Campaign creation API and character-sheet tests are green | Green | Targeted backend suite (`28 passed`) | Backend | Current targeted slice is stable after mixed-save compatibility filtering. |
| Terminal startup supports `New / Load / Quit` | Green | `frp-backend/tests/test_play.py`, `frp-backend/tests/test_play_topdown.py` | Backend / Terminal | Player-facing start flow is present in both terminal entry points. |
| Terminal load discovery is non-fatal on invalid input | Green | `frp-backend/tests/test_play.py`, `frp-backend/tests/test_play_topdown.py` | Backend / Terminal | Inline recovery is covered in the targeted slice. |
| Terminal long-form pass: `200` turns per adapter | Green | `frp-backend/tests/test_campaign_chaos.py` (2 tests, ~20s each) | QA | Both `fantasy_ember` and `scifi_frontier` pass 200-turn deterministic pass with save/load at turn 100/150, sanity assertions every 20 turns. |
| Backend chaos: `500` turns per adapter on campaign stack | Green | `frp-backend/tests/test_campaign_chaos.py` (2 tests, ~50s each) | QA | Both adapters pass 500-turn randomized chaos with <5% error rate, save at turn 250, load at turn 350. |

## Godot Onboarding and Gameplay Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Campaign creation wizard works visually for both adapters | Partial | `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/new_game_keyboard_flow/20260328T031956Z/os_screens/advance_identity.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/04_dice.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/10_build_retry.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/13_summary_pre_start.png` | Godot / QA | Fantasy onboarding now has maintained desktop proof into questionnaire, but `scifi_frontier` still has not been rerun this cycle. |
| Character build edits survive wizard navigation | Green | `godot-client/tests/run_headless_tests.gd` | Godot | Regression coverage exists. |
| In-session save/load shell works | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/save_panel_smoke/20260328T032538Z/reports/run_report.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/save_panel_smoke/20260328T032538Z/os_screens/open_save_panel.png` | Godot / QA | Fresh maintained desktop proof shows the `Save / Load` overlay inside gameplay with the active campaign slot. |
| Title-screen resume is a real save browser, not only cached `Continue` | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/title_continue_browser/20260328T032021Z/reports/run_report.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/title_continue_browser/20260328T032021Z/os_screens/refresh_player_saves.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/resume_and_command/20260328T035308Z/reports/run_report.md` | Godot | Fresh maintained desktop proof shows the filtered Chaos save list and a successful handoff into gameplay. The first-frame resume copy is still clipped, but the flow itself is real and stable. |
| Status/location/resource labels stay aligned with backend state | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/resume_and_command/20260328T035308Z/os_screens/load_first_save.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/world_click_smoke/20260328T032606Z/os_screens/click_world_target.png` | Godot | Current fantasy gameplay proof shows coherent status, location, and AP changes after load and world click. |
| Inventory, quest, settlement, and character-sheet panels are clickable and non-ambiguous | Partial | `godot-client/tests/run_headless_tests.gd`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/14_after_space_start.png` | Godot | Fresh gameplay proof shows settlement and character-sheet state, but inventory and quest panels were not freshly surfaced yet. |
| Doors, furniture, item, and world-surface click actions feel complete | Partial | `godot-client/tests/run_headless_tests.gd`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/world_click_smoke/20260328T032606Z/reports/run_report.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/world_click_smoke/20260328T032606Z/os_screens/click_world_target.png` | Godot | Fresh maintained proof now covers a live world click from gameplay, but it still lands on a movement tile rather than richer object interaction. |
| Combat actions are disabled when it is not the player's turn | Green | `godot-client/tests/run_headless_tests.gd` | Godot | Turn gating now has regression coverage and no longer leaves attack actions enabled off-turn. |
| Placeholder and no-data states are clearly distinguished from valid gameplay | Partial | `godot-client/tests/run_headless_tests.gd` | Godot | Headless coverage exists, but the current cycle has not produced fresh desktop proof of placeholder and no-data states. |
| Desktop automation proof is fail-closed instead of false-positive | Green | `python -m pytest godot-client/tests/automation -q` (`24 passed`), `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/new_game_keyboard_flow/20260328T031956Z/reports/run_report.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/title_continue_browser/20260328T032021Z/reports/run_report.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/resume_and_command/20260328T032909Z/reports/run_report.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/save_panel_smoke/20260328T032538Z/reports/run_report.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/world_click_smoke/20260328T032606Z/reports/run_report.md` | QA / Automation | The maintained harness now fails closed when scenes or captures are wrong. Runs must stay sequential because the Win32 executor assumes exclusive control of one Godot window. |

## Visual and Benchmark Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Short graphical pass works for `fantasy_ember` | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/new_game_keyboard_flow/20260328T031956Z/os_screens/advance_identity.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/resume_and_command/20260328T035308Z/os_screens/load_first_save.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/save_panel_smoke/20260328T032538Z/os_screens/open_save_panel.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/world_click_smoke/20260328T032606Z/os_screens/click_world_target.png` | QA | Fresh maintained fantasy proof covers wizard progression, resume-to-gameplay, save panel, and world click in one cycle. |
| Short graphical pass works for `scifi_frontier` | Open | `docs/qa/campaign_cutover_visual_log.md` | QA | Earlier graphical proof exists, but this cycle has not rerun a fresh sci-fi graphical path yet. |
| `100`-turn visual pass per adapter | Open | `frp-backend/tests/test_campaign_chaos.py` | QA | Backend chaos is green, but Director Mode requires a real visual 100-turn pass. That has not been run in this cycle. |
| `30`-minute free play per adapter | Open | `frp-backend/tests/test_campaign_chaos.py` | QA | Backend longevity exists, but real timed visual free play has not been completed in this cycle. |
| RimWorld benchmark floor `>= 3/5` on each axis average | Green | `docs/qa/rimworld_benchmark_report.md`, `docs/qa/vqr_scorecard.md` | QA | Current benchmark refresh keeps each axis average at or above `3/5`, even though the build is still far below a compelling aesthetic bar. |
| Final art and silhouette readability are demo-ready | Open | `docs/qa/rimworld_benchmark_report.md`, `docs/qa/vqr_scorecard.md` | Godot / Art / QA | Current baseline is `SD 2`, `TTD 3`, `UP 2`, and `VQS 2.6`. The game still looks like debug art rather than a demo-ready world. |
| Final Godot-assisted `500`-turn visual chaos pass | Open | `frp-backend/tests/test_campaign_chaos.py` | QA | Backend chaos is green, but the Godot-assisted 500-turn visual pass has not been run. |

## Release Decision
- Current release state: `Not ready for demo`
- Backend correctness is ahead of current visual signoff, but Director Mode closure is blocked by:
  - a missing current-cycle `scifi_frontier` graphical rerun
  - real visual long-form passes
  - a post-slice VQS of only `3.1 / 10`, still below the `5.0` demo target
- Fresh audit findings this cycle:
  - fantasy onboarding, resume, save panel, and world click now have fresh maintained desktop proof
  - desktop automation is trustworthy again when run sequentially
  - the first gameplay frame after resume now uses humanized copy, but the line still clips to the tail fragment `back into the campaign.`
  - final art, silhouette, and UI presentation remain far below demo-ready quality
- Previously fixed code remains valid starting context, but the signoff matrix is no longer treating deferred or inherited proof as closure.

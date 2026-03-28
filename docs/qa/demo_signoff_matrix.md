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
  - `godot-client/tests/automation/` (5 TOML scenarios)
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
| Campaign creation wizard works visually for both adapters | Partial | `docs/qa/campaign_cutover_visual_log.md`, `tmp/manual_screenshot_*.png`, `tmp/visual_automation/new_game_keyboard_flow/20260328T024442Z/` | Godot / QA | Legacy 2026-03-28 manual proof exists, but the fresh audit cycle has not revalidated the wizard. The current desktop scenario marked `pass` while still capturing the title shell, so current-cycle proof is not trustworthy yet. |
| Character build edits survive wizard navigation | Green | `godot-client/tests/run_headless_tests.gd` | Godot | Regression coverage exists. |
| In-session save/load shell works | Partial | `docs/qa/campaign_cutover_visual_log.md`, `tmp/visual_automation/save_panel_smoke/20260328T024538Z/` | Godot / QA | Older manual proof exists, but the fresh `save_panel_smoke` run captured the title screen instead of the save/load panel while still reporting success. |
| Title-screen resume is a real save browser, not only cached `Continue` | Partial | `tmp/manual_screenshot_*.png`, `tmp/visual_automation/resume_and_command/20260328T024519Z/` | Godot | Older manual proof exists, but the fresh resume scenario opened a `Fallback` player entry, found no saves, and later surfaced `HTTP 400`. |
| Status/location/resource labels stay aligned with backend state | Partial | `tmp/manual_screenshot_13_gameplay.png` | Godot | Legacy gameplay proof exists, but the current-cycle graphical replay has not revalidated this after the automation failures. |
| Inventory, quest, settlement, and character-sheet panels are clickable and non-ambiguous | Partial | `godot-client/tests/run_headless_tests.gd`, `tmp/manual_screenshot_13_gameplay.png` | Godot | Headless coverage remains green, but fresh current-cycle desktop proof is still missing. |
| Doors, furniture, item, and world-surface click actions feel complete | Partial | `godot-client/tests/run_headless_tests.gd`, `tmp/visual_automation/world_click_smoke/20260328T024553Z/` | Godot | Headless coverage remains green, but the fresh desktop world-click scenario never left the title shell. |
| Combat actions are disabled when it is not the player's turn | Green | `godot-client/tests/run_headless_tests.gd` | Godot | Turn gating now has regression coverage and no longer leaves attack actions enabled off-turn. |
| Placeholder and no-data states are clearly distinguished from valid gameplay | Partial | `godot-client/tests/run_headless_tests.gd` | Godot | Headless coverage exists, but the current cycle has not produced fresh desktop proof of placeholder and no-data states. |

## Visual and Benchmark Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Short graphical pass works for `fantasy_ember` | Partial | `tmp/manual_screenshot_*.png`, `tmp/visual_qa/baseline/baseline_title_os.png` | QA | Legacy gameplay proof exists and the fresh audit confirmed the title shell. A fresh current-cycle gameplay pass is still pending. |
| Short graphical pass works for `scifi_frontier` | Partial | `docs/qa/campaign_cutover_visual_log.md` | QA | Earlier graphical proof exists, but this cycle has not rerun a fresh sci-fi graphical path yet. |
| `100`-turn visual pass per adapter | Open | `frp-backend/tests/test_campaign_chaos.py` | QA | Backend chaos is green, but Director Mode requires a real visual 100-turn pass. That has not been run in this cycle. |
| `30`-minute free play per adapter | Open | `frp-backend/tests/test_campaign_chaos.py` | QA | Backend longevity exists, but real timed visual free play has not been completed in this cycle. |
| RimWorld benchmark floor `>= 3/5` on each axis average | Partial | `docs/qa/rimworld_benchmark_report.md`, `docs/qa/vqr_scorecard.md` | QA | The benchmark file exists, but the new Director Mode baseline is materially harsher and needs a post-fix refresh before this gate can be green. |
| Final art and silhouette readability are demo-ready | Open | `docs/qa/rimworld_benchmark_report.md`, `docs/qa/vqr_scorecard.md` | Godot / Art / QA | Current baseline is `SD 2`, `TTD 3`, `UP 2`, and `VQS 2.6`. The game still looks like debug art rather than a demo-ready world. |
| Final Godot-assisted `500`-turn visual chaos pass | Open | `frp-backend/tests/test_campaign_chaos.py` | QA | Backend chaos is green, but the Godot-assisted 500-turn visual pass has not been run. |

## Release Decision
- Current release state: `Not ready for demo`
- Backend correctness is ahead of current visual signoff, but Director Mode closure is blocked by:
  - fresh current-cycle graphical revalidation of the main onboarding and gameplay flows
  - real visual long-form passes
  - a broken desktop QA harness that is currently generating false-positive evidence
  - a baseline VQS of `2.6 / 10`
- Fresh audit findings this cycle:
  - desktop automation can claim `pass` while still capturing the title screen
  - resume automation currently demonstrates an invalid `Fallback` player path and `HTTP 400`
  - final art, silhouette, and UI presentation remain far below demo-ready quality
- Previously fixed code remains valid starting context, but the signoff matrix is no longer treating deferred or inherited proof as closure.

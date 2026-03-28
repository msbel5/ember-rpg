# Demo Signoff Matrix

## Scope
- Date: 2026-03-28
- Release target: controlled Ember RPG campaign-first demo
- Adapters in scope:
  - `fantasy_ember`
  - `scifi_frontier`
- Canonical evidence:
  - `docs/qa/vqr_scorecard.md`
  - `docs/qa/bug_registry.md`
  - `docs/qa/play_log.md`
  - `docs/qa/campaign_cutover_visual_log.md`
  - `docs/qa/rimworld_benchmark_report.md`
  - targeted backend suite (`28 passed`)
  - backend chaos suite (`4 passed`)
  - Godot headless preflight (green)
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/`

## Contract Lock

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Campaign-first route family is the documented player-facing contract | Green | `docs/PRD_save_load.md`, this file | Docs | Campaign-first flow remains the public contract. |
| Demo docs classify current closure gates honestly | Green | `docs/qa/vqr_scorecard.md`, this file | Docs | The old `3.1` snapshot is retired as the current verdict. |

## Backend and Terminal Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Campaign creation, payload, save/load, and terminal suites are green | Green | targeted backend suite (`28 passed`) | Backend | Current code slice did not regress backend correctness. |
| Backend chaos: `500` turns per adapter on campaign stack | Green | `python -m pytest frp-backend/tests/test_campaign_chaos.py -v --tb=short` (`4 passed`) | QA | Both adapters pass `200`-turn and `500`-turn chaos in the current cycle. |

## Godot Onboarding and Gameplay Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Campaign creation wizard works visually for both adapters | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_new_20260328T091228Z/os_screens/campaign_boot.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_new_20260328T091331Z/os_screens/campaign_boot.png` | Godot / QA | Fresh current-cycle create-flow proof now exists for both adapters. |
| Summary-screen keyboard activation is real, not click-only | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_new_20260328T091228Z/manifest.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_new_20260328T091331Z/manifest.md` | Godot / QA | The visual driver advances through summary via keyboard activation and reaches gameplay. |
| In-session save/load shell works | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/save_panel_smoke/20260328T032538Z/os_screens/open_save_panel.png` | Godot / QA | Fresh maintained in-session save/load proof remains valid. |
| Title-screen resume is a real save browser with real handoff | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/title_continue_browser/20260328T032021Z/os_screens/refresh_player_saves.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/campaign_boot.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/campaign_boot.png` | Godot / QA | Resume browser and handoff are both current-cycle real. |
| Status, location, AP, and shell state stay aligned in live play | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_100.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_100.png` | Godot / QA | Late-turn frames remain coherent. |
| Inventory, quest, settlement, and character-sheet panels are clickable and non-ambiguous | Partial | Godot headless preflight, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_100.png` | Godot / QA | Character, survey, roster, and settlement surfaces are visibly improved; quest/inventory were not freshly surfaced as dedicated desktop steps in this cycle. |
| Doors, furniture, item, and world-surface click actions feel complete | Partial | Godot headless preflight, `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/world_click_smoke/20260328T032606Z/os_screens/click_world_target.png` | Godot / QA | Truthfulness is improved; richness is still below colony-sim/CRPG expectations. |
| Placeholder and no-data states are clearly distinguished from valid gameplay | Partial | Godot headless preflight | Godot / QA | Headless coverage is present, but current-cycle desktop proof is still missing. |
| Desktop automation proof is fail-closed | Green | `python -m pytest godot-client/tests/automation -q` (`24 passed`), maintained scenario reports in `tmp/visual_automation/` | QA / Automation | Existing maintained harness remains trustworthy for smoke-level proof. |

## Visual and Benchmark Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Short graphical pass works for `fantasy_ember` | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_new_20260328T091228Z/os_screens/campaign_boot.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T084318Z/os_screens/command_050.png` | QA | Fresh new-flow and continue-flow proof both exist. |
| Short graphical pass works for `scifi_frontier` | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_new_20260328T091331Z/os_screens/campaign_boot.png`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T084722Z/os_screens/command_050.png` | QA | The previously missing fresh sci-fi rerun is now closed. |
| `50`-turn visual pass per adapter | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T084318Z/manifest.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T084722Z/manifest.md` | QA | Both adapters now have current-cycle `50`-turn desktop evidence. |
| `100`-turn visual pass per adapter | Green | `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/manifest.md`, `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/manifest.md` | QA | Both adapters now have current-cycle `100`-turn desktop evidence. |
| RimWorld benchmark floor `>= 3/5` on each axis average | Green | `docs/qa/rimworld_benchmark_report.md` | QA | The current build remains above the benchmark floor and materially stronger than the old `3.1` snapshot. |
| Current VQS reaches the minimum demo target | Green | `docs/qa/vqr_scorecard.md` | QA | Current official score is `5.0 / 10`. |
| Manual `30`-minute free play per adapter | Open | `docs/qa/play_log.md` | QA | Not completed in this cycle. |
| Placeholder/no-data desktop proof | Open | `docs/qa/play_log.md` | QA | Still missing as dedicated desktop evidence. |
| Final Godot-assisted visual chaos beyond the current `100`-turn pass | Open | `docs/qa/play_log.md`, `frp-backend/tests/test_campaign_chaos.py` | QA | Backend chaos is green; Godot-assisted chaos beyond `100` turns is still open. |

## Release Decision
- Current release state: `Ready for controlled demo at the minimum bar`
- Why this is now `YES`:
  - no reproduced `P0` or `P1` blocker remains in the current cycle
  - the build now has fresh current-cycle wizard, `50`-turn, and `100`-turn desktop proof for both adapters
  - current official `VQS = 5.0 / 10`
- Why this is still only the minimum bar:
  - the world is still sparse and visually far from reference quality
  - object vocabulary is still shallow
  - `AF` remains weak
  - manual `30`-minute free play and placeholder/no-data desktop proof are still open follow-up QA debt

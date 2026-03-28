# VQR Scorecard

## Scope
- Date: 2026-03-28
- Historical baseline: pre-audit desktop build
- Pinned slice: early director-mode shell/readability lift (`VQS = 3.1 / 10`)
- Current pass: existing-assets strike pass plus fresh desktop validation
- Scoring rule: `VQS = (SD + TTD + AD + IA + IF + NP + CD + AF + UP + DH) / 10`

## Evidence Sets
- Historical baseline:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/01_title.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/13_summary_pre_start.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/14_after_space_start.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/15_after_click_start.png`
- Current-cycle wizard proof:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_new_20260328T091228Z/os_screens/campaign_boot.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_new_20260328T091331Z/os_screens/campaign_boot.png`
- Current-cycle long-form desktop proof:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T084318Z/os_screens/command_050.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T084722Z/os_screens/command_050.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/campaign_boot.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_100.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/campaign_boot.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_100.png`
- Supporting verification:
  - targeted backend suite: `28 passed`
  - backend chaos suite: `4 passed`
  - Godot headless preflight: green

| Axis | Historical Baseline | Pinned Slice | Current Pass | Delta vs Baseline | Evidence |
|------|---------------------|--------------|--------------|-------------------|----------|
| SD | 2 | 3 | 5 | +3 | `campaign_boot.png` and `command_100.png` now show a larger staged player, grounded actors, roster icons, and readable major categories instead of pure tokens. |
| TTD | 3 | 3 | 5 | +2 | `campaign_boot.png` and `command_100.png` show stronger built-area staging, clearer roads/plaza/interior separation, and less grass-dominated wallpaper repetition. |
| AD | 1 | 1 | 4 | +3 | Current-cycle boots show adapter-aware atmosphere wash, vignette/depth treatment, and ambient landmark activity instead of flat unlit surfaces. |
| IA | 4 | 4 | 6 | +2 | The status strip, survey panel, focus summary, action chips, and roster strip make the current scene readable in a glance. |
| IF | 3 | 4 | 5 | +2 | World clicks, movement interpolation, hostile/interest highlights, and live focus actions now acknowledge interaction visibly. |
| NP | 2 | 2 | 4 | +2 | Resume copy is humanized, command outcomes read cleaner, and the shell no longer leaks raw backend shorthand, though the prose is still not magnetic. |
| CD | 5 | 5 | 6 | +1 | The game now exposes visible talk/scout actions, roster picks, save/load controls, truthful prop clicks, and persistent focus prompts. |
| AF | 1 | 1 | 2 | +1 | The build now has movement lerp and idle life, but still no real walk-cycle or action animation pipeline. |
| UP | 2 | 4 | 7 | +5 | Title, wizard, and gameplay shell now share an authored bronze-on-charcoal identity with portrait framing, action strips, separators, and stronger hierarchy. |
| DH | 3 | 4 | 6 | +3 | Fresh wizard-to-gameplay proof and the current shell/world readability finally create enough curiosity to sustain a controlled demo. |

## Score Summary
- Historical baseline: `VQS = 2.6 / 10`
- Pinned early-slice score: `VQS = 3.1 / 10`
- Current official score: `VQS = 5.0 / 10`

## Current Honest Read
- This build now clears the minimum demo bar. It no longer reads like Atari ET with a better menu on top.
- The shell, focus/actions layer, actor readability, tile staging, and adapter atmosphere moved the score most.
- The world is still not reference-quality. `AF = 2` is the loudest remaining weakness, and the prose layer still works harder as a cleanup pass than as a source of wonder.
- This is a `5.0`, not a `6.0`. It is a respectable minimum-bar demo, not an impressive one.

## Remaining Follow-Up Debt
- Manual `30`-minute free play per adapter is still not logged in this cycle.
- Placeholder and no-data desktop proof is still incomplete this cycle.
- Final Godot-assisted visual chaos beyond the current `100`-turn passes is still open.

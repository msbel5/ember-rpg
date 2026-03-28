# VQR Scorecard

## Scope
- Date: 2026-03-28
- Phase: Pre-phase reality audit
- Scoring rule: `VQS = (SD + TTD + AD + IA + IF + NP + CD + AF + UP + DH) / 10`
- Baseline evidence set:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/01_title.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/03_questionnaire.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/04_dice.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/10_build_retry.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/13_summary_pre_start.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/14_after_space_start.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/15_after_click_start.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_qa/baseline/16_continue_default.png`

| Axis | Baseline | After Pre-phase | Delta | Evidence |
|------|----------|-----------------|-------|----------|
| SD | 2 | 2 | 0 | `14_after_space_start.png` - the avatar is a tiny token on a loud grass texture; silhouettes are not readable at a glance. |
| TTD | 3 | 3 | 0 | `14_after_space_start.png` - tiles have texture, but the map still reads as repeated wallpaper instead of authored spaces. |
| AD | 1 | 1 | 0 | `01_title.png`, `14_after_space_start.png` - flat brightness, no particles, no lighting, no weather, no mood layer. |
| IA | 4 | 4 | 0 | `14_after_space_start.png` - core state is grouped and mostly parseable, but the sidebar is still text-heavy and cramped. |
| IF | 3 | 3 | 0 | `15_after_click_start.png` - movement and AP change are visible, but feedback is still mostly text and selection outlines. |
| NP | 2 | 2 | 0 | `14_after_space_start.png` - text is functional and thin; it reports state instead of creating curiosity. |
| CD | 5 | 5 | 0 | `04_dice.png`, `10_build_retry.png`, `14_after_space_start.png` - there are meaningful buttons, commands, and world clicks, even if many are shallow. |
| AF | 1 | 1 | 0 | `14_after_space_start.png`, `15_after_click_start.png` - entities still teleport between states. |
| UP | 2 | 2 | 0 | `01_title.png`, `03_questionnaire.png`, `13_summary_pre_start.png` - title, wizard, and shell still read as stock Godot scaffolding. |
| DH | 3 | 3 | 0 | `03_questionnaire.png`, `13_summary_pre_start.png`, `14_after_space_start.png` - the wizard has intent, but the world still looks like debug art. |

## Baseline Summary
- `VQS = 2.6 / 10`
- Current verdict: not shippable as a respected demo
- Honest read: the game still looks like Atari ET wearing a slightly better grass texture. It works, but the presentation does not earn player curiosity yet.

## Phase 2 Slice Rescore
- Fresh maintained evidence:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/new_game_keyboard_flow/20260328T031956Z/os_screens/advance_identity.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/title_continue_browser/20260328T032021Z/os_screens/refresh_player_saves.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/resume_and_command/20260328T032909Z/os_screens/load_first_save.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/resume_and_command/20260328T032909Z/os_screens/submit_command.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/save_panel_smoke/20260328T032538Z/os_screens/open_save_panel.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/world_click_smoke/20260328T032606Z/os_screens/click_world_target.png`

| Axis | Baseline | After Phase 2 Slice | Delta | Evidence |
|------|----------|---------------------|-------|----------|
| SD | 2 | 3 | +1 | `load_first_save.png` - the closer camera, larger player, and shadow finally make the avatar readable, but NPC and furniture silhouettes are still weak. |
| TTD | 3 | 3 | 0 | `load_first_save.png` - terrain variants help a little, but the grass still overpowers the scene and the plaza still reads as repeated texture. |
| AD | 1 | 1 | 0 | `load_first_save.png` - there is still no atmosphere layer: no light, particles, weather, or room mood. |
| IA | 4 | 4 | 0 | `open_save_panel.png`, `load_first_save.png` - shell grouping remains clear, but the right rail is still text-heavy and crowded. |
| IF | 3 | 4 | +1 | `click_world_target.png` - clicks now get visible flash/selection feedback and recent-command acknowledgement before the next action. |
| NP | 2 | 2 | 0 | `load_first_save.png` - the first gameplay frame still leaks `resume_campaign_ok.`, so the prose layer is still function-over-drama. |
| CD | 5 | 5 | 0 | `advance_identity.png`, `open_save_panel.png`, `click_world_target.png` - there are still many clickable surfaces, even if the object vocabulary is shallow. |
| AF | 1 | 1 | 0 | `load_first_save.png`, `click_world_target.png` - entities still teleport and there is still no motion choreography. |
| UP | 2 | 4 | +2 | `advance_identity.png`, `refresh_player_saves.png`, `open_save_panel.png` - the title, wizard, and shell now feel authored instead of default-toolkit plain, but they still lack icons, art framing, and polish depth. |
| DH | 3 | 4 | +1 | `advance_identity.png`, `load_first_save.png` - the hook is stronger because onboarding and resume now feel intentional, but the world still does not generate strong curiosity on sight. |

## Phase 2 Summary
- Official post-slice score: `VQS = 3.1 / 10`
- Honest read: this is no longer embarrassing in the same way the baseline was, but it is still only a technical-demo-plus build. The title and wizard now have intent; the world still looks like debug art with a competent shell wrapped around it.

## Phase 2 Late Resume Follow-Up
- Fresh resume evidence:
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/resume_and_command/20260328T035308Z/os_screens/load_first_save.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_automation/resume_and_command/20260328T035308Z/os_screens/submit_command.png`
- Score impact:
  - no axis changed enough to warrant a rescored VQS
  - the raw resume token leak is fixed, but the first-line clipping keeps `NP` and `UP` from moving
- Official score remains: `VQS = 3.1 / 10`

# VQR Scorecard

## Scope
- Audit date: 2026-03-28
- Phase: Pre-phase reality audit
- Baseline verdict: `Not demo-ready`
- Baseline VQS: `2.6 / 10`
- Evidence sources:
  - `C:\Users\msbel\projects\ember-rpg\tmp\visual_qa\baseline\baseline_title_os.png`
  - `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_03_maximized.png`
  - `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_12.png`
  - `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png`
  - `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\new_game_keyboard_flow\20260328T024442Z\os_screens\advance_identity.png`
  - `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\resume_and_command\20260328T024519Z\os_screens\open_continue.png`
  - `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\resume_and_command\20260328T024519Z\os_screens\submit_command.png`
  - `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\save_panel_smoke\20260328T024538Z\os_screens\open_save_panel.png`
  - `C:\Users\msbel\projects\ember-rpg\tmp\visual_automation\world_click_smoke\20260328T024553Z\os_screens\click_world_target.png`

| Axis | Baseline | After Pre-Phase | Delta | Evidence |
|------|----------|-----------------|-------|----------|
| Silhouette Distinctiveness (SD) | 2 | 2 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png` |
| Tile Texture Depth (TTD) | 3 | 3 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png` |
| Atmospheric Density (AD) | 1 | 1 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_03_maximized.png`, `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png` |
| Information Architecture (IA) | 4 | 4 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png` |
| Interaction Feedback (IF) | 3 | 3 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png`, `C:\Users\msbel\projects\ember-rpg\tmp\visual_probe\continue_loaded_after_world_click.png` |
| Narrative Presentation (NP) | 2 | 2 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png` |
| Click Density (CD) | 5 | 5 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png` |
| Animation Fluidity (AF) | 1 | 1 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png` |
| UI Polish (UP) | 2 | 2 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\visual_qa\baseline\baseline_title_os.png`, `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_12.png` |
| Demo Hook (DH) | 3 | 3 | 0 | `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_12.png`, `C:\Users\msbel\projects\ember-rpg\tmp\manual_screenshot_13_gameplay.png` |

## Baseline Rationale
- `SD 2`: the world still reads as a token board. The player sprite is tiny and the rest of the entities do not read as characters at a glance.
- `TTD 3`: textured tiles exist, but the map still feels like repeated grass wallpaper with a stamped path and square building footprint.
- `AD 1`: there is no lighting, weather, particle work, or mood. The title and gameplay screens are flat.
- `IA 4`: the shell is organized enough to navigate, and the status line plus right rail expose useful state quickly.
- `IF 3`: clicks generate commands and selection, but the feedback is mostly text and AP changes. There is almost no visual response.
- `NP 2`: the text remains functional and low-drama. It reports state instead of creating curiosity.
- `CD 5`: there are meaningful commands, panel actions, and clickable tiles or entities even though the responses remain shallow.
- `AF 1`: movement and actions still teleport. There is no walk cycle, lerp, or action animation in the baseline.
- `UP 2`: the title screen, wizard, and panels still look like default Godot controls on a dark backdrop.
- `DH 3`: the creation wizard has intent, but the world still looks like Atari ET-era debug presentation rather than a compelling place.

## Audit Notes
- The mandatory targeted backend suite, backend chaos suite, automation Python suite, automation bridge, and Godot headless preflight all passed in this audit cycle.
- The visual automation harness is not trustworthy enough to mark visual gates green. Multiple scenarios reported `pass` while their OS screenshots remained on the title screen or showed a broken continue flow.
- Phase 1 PRD writing is documentation-only. No VQR axis moved yet, and the baseline scores remain the active before-state for implementation.

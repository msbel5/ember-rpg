# RimWorld Benchmark Report

## Scope
- Date: 2026-03-28
- Benchmark PRD: `docs/PRD_rimworld_benchmark_v1.md`
- Evidence sources:
  - `docs/qa/campaign_cutover_visual_log.md`
  - `godot-client/tests/manual/campaign_visual_driver.py`
  - `godot-client/tests/run_headless_tests.gd`
  - `frp-backend/tests/test_campaign_godot_payload_shapes.py`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/continue_browser_live.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/continue_loaded_live.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/continue_loaded_after_world_click.png`

## Adapter Scores

### Fantasy Ember

#### Systems Clarity
- Resident autonomy: `3/5`
  - Evidence: residents, jobs, stockpiles, and posture are surfaced in the settlement panel, but resident behavior is still mostly declarative.
- Jobs and room purpose: `3/5`
  - Evidence: jobs list is readable and commander commands exist, but room consequences are still shallow.
- Event causality: `3/5`
  - Evidence: campaign narrative includes explainability tags and settlement alerts, but the live loop still exposes limited consequence variety.
- Axis average: `3.0/5`

#### Visual Readability
- Tile readability: `3/5`
  - Evidence: map, pathing, and player position are readable in `game_session_frame_2026-03-27T22-33-45.png`.
- Entity readability: `2/5`
  - Evidence: adapter-aware tinting now exists, but silhouette variety is still weak for NPCs, residents, and furniture.
- Information hierarchy: `4/5`
  - Evidence: status bar, narrative, settlement panel, and command bar remain legible in the current shell.
- Axis average: `3.0/5`

#### UX Loop Quality
- First 15-minute onboarding: `3/5`
  - Evidence: new campaign creation, movement, and quick save work without headless-only shortcuts.
- Command discoverability: `3/5`
  - Evidence: command bar, recent history, and settlement quick actions are visible; the keyboard submit bug is now fixed.
- Error recovery: `3/5`
  - Evidence: `Continue` now hides incompatible legacy saves instead of advertising a broken load path, but the deeper long-play recovery path is still not benchmarked.
- Axis average: `3.0/5`

### Sci-Fi Frontier

#### Systems Clarity
- Resident autonomy: `3/5`
  - Evidence: `Auran City` exposes the same settlement panel structure and commander shell as fantasy.
- Jobs and room purpose: `3/5`
  - Evidence: the campaign shell preserves colony-lite state across adapter swap, but sci-fi-specific work loops are still mostly label-deep.
- Event causality: `3/5`
  - Evidence: explainability metadata and frontier-specific labels are visible during live boot and command passes.
- Axis average: `3.0/5`

#### Visual Readability
- Tile readability: `3/5`
  - Evidence: `game_session_frame_2026-03-27T22-33-50.png` shows a cooler world tint and clear status/location framing.
- Entity readability: `2/5`
  - Evidence: adapter-aware tinting improves distinction, but placeholder terrain and entity art still dominate the scene.
- Information hierarchy: `4/5`
  - Evidence: the same shell stays readable after adapter switch and continue/load.
- Axis average: `3.0/5`

#### UX Loop Quality
- First 15-minute onboarding: `3/5`
  - Evidence: adapter selection, campaign creation, continue/load, and quick save all work in graphical mode.
- Command discoverability: `3/5`
  - Evidence: the command bar and settlement actions stay visible, and enter-to-submit is fixed for focused input.
- Error recovery: `3/5`
  - Evidence: continue/load visual proof exists, but there is no long-session desync benchmark yet.
- Axis average: `3.0/5`

## Side-by-Side Notes
- Ember now meets the minimum benchmark gate mechanically: no current axis average below `3`.
- Ember does not yet match RimWorld on silhouette density, room-purpose depth, or event-chain readability.
- Ember remains an avatar-commander hybrid, not a pure colony sim clone. The benchmark is used to track clarity and polish, not to force a genre pivot.
- The continue/load flow is finally honest, but the world still looks like debug art stretched into a shipping shell. The grass, road, and building surfaces are readable, yet they do not carry enough identity to feel authored or memorable.
- The post-resume fountain click proves the interaction loop survives restore, but it also exposes how thin the surface language still is: one clear action works, while broader object vocabulary remains too sparse to feel rich.

## Open Gaps
- Visual differentiation is still too dependent on tinting; it needs stronger terrain/furniture/entity art separation.
- The benchmark is based on short live passes, not the full `100-turn` plus `30-minute` matrix.
- Combat readability and long-horizon reward cadence need more live evidence before final sign-off.
- The `500-turn` Godot visual chaos pass is still required for final closure.

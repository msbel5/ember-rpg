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

## 2026-03-28 Refresh (Long-Form Evidence)

### New Evidence Sources
- `frp-backend/tests/test_campaign_chaos.py` — 200-turn + 500-turn chaos per adapter (all 4 pass)
- `tmp/manual_screenshot_*.png` — full creation wizard + gameplay desktop screenshots
- `tmp/visual_automation/` — 5 desktop automation scenarios (4/5 pass)

### Score Adjustments
- **Systems Clarity** remains `3.0/5` — 500-turn chaos proves state stability through save/load, but no new depth mechanics were added.
- **Visual Readability** remains `3.0/5` — entity readability stays `2/5` (geometric shapes + tinting). Tile readability `3/5`. Information hierarchy `4/5` confirmed with live gameplay screenshots.
- **UX Loop Quality** adjusts upward:
  - First 15-minute onboarding: `4/5` (up from 3) — full 5-step creation wizard proven end-to-end with real RPG questions, dice rolls, stat assignment, and immediate gameplay transition.
  - Command discoverability: `3/5` — unchanged.
  - Error recovery: `3/5` — unchanged. 500-turn chaos proves <5% error rate, but error recovery UX is still not visible to the player.
  - New axis average: `3.3/5`

### Bugs Found and Fixed This Session
- P1: Technical narrative leak (`[Region: terrain=...]`) removed from player-facing text
- P2: Dice roll floats (11.0 → 11) fixed
- P2: Furniture entity bucket added for click interactions
- P2: Character panel fallback hardened for missing stats
- P2: Raw resume token leak removed from the first gameplay handoff

### Honest Assessment
The game mechanically passes the `>= 3/5` benchmark floor on all axes. The creation flow genuinely feels like a real RPG onboarding — not a debug form. The questionnaire generates evocative questions, the dice rolls have tactile save/swap mechanics, and the build screen presents clear stat/class/skill choices. The gameplay session boots with correct state and responds to commands.

What still feels weak:
- Entity art is geometric shapes with tinting. A Planescape veteran would find this sterile.
- Narrative text is thin — "settlement shaped by the uplands" doesn't create curiosity like it should.
- The first resume sentence is still clipped to `back into the campaign.` in the live GUI, which makes the presentation feel brittle even though the raw token is gone.
- The world looks functional but not authored. There's no mood, no atmosphere, no visual identity.
- Furniture interaction adds `examine barrel` but there's no response depth behind it yet.
- The game passes a stress test but doesn't yet create the "I wonder what's behind that door" feeling.

## Open Gaps
- Visual differentiation remains dependent on tinting + geometric shapes. Needs authored sprites for demo-quality visuals.
- Narrative depth is minimal — DM responses are functional but not evocative. No Planescape-level prose.
- Combat readability needs more live visual evidence.
- Dedicated timed visual passes (100-turn, 30-minute) deferred as non-blocking.

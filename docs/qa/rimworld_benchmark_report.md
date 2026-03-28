# RimWorld Benchmark Report

## Scope
- Date: 2026-03-28
- Benchmark purpose: compare Ember RPG against RimWorld-style clarity, readability, and interaction density, not to force a genre pivot
- Evidence sources:
  - `docs/qa/vqr_scorecard.md`
  - `docs/qa/play_log.md`
  - `docs/qa/campaign_cutover_visual_log.md`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/campaign_boot.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/fantasy_ember_continue_20260328T090011Z/os_screens/command_100.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/campaign_boot.png`
  - `C:/Users/msbel/projects/ember-rpg/tmp/visual_probe/scifi_frontier_continue_20260328T090528Z/os_screens/command_100.png`
  - backend chaos suite (`4 passed`)

## Adapter Scores

### Fantasy Ember

#### Systems Clarity
- Resident autonomy: `3/5`
  - Evidence: roster/focus actions, settlement quick actions, and long-form command stability now make current local pressure clearer, but residents still do not visually advertise jobs or mood the way RimWorld colonists do.
- Jobs and room purpose: `4/5`
  - Evidence: the plaza, roads, interiors, and obvious props now read more clearly as spaces with purpose instead of undifferentiated wallpaper.
- Event causality: `3/5`
  - Evidence: the shell now communicates recent orders and visible focus targets better, but consequence chains are still shallow.
- Axis average: `3.3/5`

#### Visual Readability
- Tile readability: `4/5`
  - Evidence: staged surfaces now distinguish built areas from grass much better in `campaign_boot.png` and `command_100.png`.
- Entity readability: `3/5`
  - Evidence: the player, local contacts, and pressure targets are now materially easier to read, but the cast is still too close to tinted tokens.
- Information hierarchy: `5/5`
  - Evidence: the current shell communicates player state, locale, recent orders, focus actions, and nearby cast quickly.
- Axis average: `4.0/5`

#### UX Loop Quality
- First 15-minute onboarding: `4/5`
  - Evidence: the full wizard and immediate gameplay handoff now feel intentional and stable.
- Command discoverability: `4/5`
  - Evidence: the command bar, focus-action chips, roster strip, and save/load buttons make the interaction model much clearer.
- Error recovery: `4/5`
  - Evidence: resume/save flows are honest and stable in the current cycle, and long-form visual passes stayed alive through turn `100`.
- Axis average: `4.0/5`

### Sci-Fi Frontier

#### Systems Clarity
- Resident autonomy: `3/5`
  - Evidence: the sci-fi shell exposes the same focus and settlement structure as fantasy, but still lacks rich visual task-state language.
- Jobs and room purpose: `4/5`
  - Evidence: cooler staging and clearer surfaces now make Auran City feel more intentional than the old debug-map read.
- Event causality: `3/5`
  - Evidence: late-turn orders and world state stay coherent, but deeper consequence vocabulary is still thin.
- Axis average: `3.3/5`

#### Visual Readability
- Tile readability: `4/5`
  - Evidence: current-cycle boot and turn-100 frames show better built-space contrast and less noisy terrain dominance.
- Entity readability: `3/5`
  - Evidence: category readability is materially better, but NPCs and props still need more authored identity.
- Information hierarchy: `5/5`
  - Evidence: the same shell hierarchy remains strong after adapter swap.
- Axis average: `4.0/5`

#### UX Loop Quality
- First 15-minute onboarding: `4/5`
  - Evidence: fresh current-cycle new-game proof exists for sci-fi, not just old cached evidence.
- Command discoverability: `4/5`
  - Evidence: focus actions, roster picks, and recent orders keep the command layer legible.
- Error recovery: `4/5`
  - Evidence: current-cycle continue flow and `100`-turn proof remain stable; save/load honesty holds.
- Axis average: `4.0/5`

## Side-by-Side Notes
- Ember now clears the RimWorld-style clarity floor comfortably instead of barely scraping over it.
- The biggest improvement is not raw simulation depth. It is scene readability: the current shell tells the player what matters now much faster than the old `3.1` build.
- The world still does not match RimWorld on density:
  - entity state is not richly visual
  - room purpose is improved but still limited
  - click-anything depth is still far below a true inspector-driven colony sim
- Ember remains an avatar-commander hybrid. It does not need to become RimWorld, but it now borrows enough of RimWorld’s glanceability to support a minimum-bar demo.

## Honest Assessment
- The current benchmark read is materially stronger than the old one because it is backed by fresh `50`-turn and `100`-turn desktop proof for both adapters.
- The build is now demo-ready at the minimum bar, not because it suddenly gained reference-quality art, but because the shell, world staging, and interaction readability finally work together.
- The biggest remaining gap versus RimWorld is still world life:
  - no rich task-state animation
  - no dense object vocabulary
  - no deep environmental storytelling
  - no “click anything, inspect everything” completeness

## Open Gaps
- Entity art is still not authored enough to feel memorable.
- Long-form narrative phrasing is still serviceable rather than sharp.
- Manual `30`-minute free play per adapter is still not logged in this cycle.
- Placeholder/no-data desktop proof is still open.

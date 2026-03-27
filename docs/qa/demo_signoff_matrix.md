# Demo Signoff Matrix

## Scope
- Date: 2026-03-28
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
  - `frp-backend/tests/test_terminal_campaign_loop.py`
  - `frp-backend/tests/test_play.py`
  - `frp-backend/tests/test_play_topdown.py`
  - `godot-client/tests/run_headless_tests.gd`

## Contract Lock

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Campaign-first route family is the documented player-facing contract | Green | `docs/PRD_save_load.md`, `docs/PRD_godot_client.md` | Docs | Active flow is `/game/campaigns/...`; legacy session routes remain compatibility-only. |
| Character-sheet payload is documented consistently across backend, terminal, and Godot | Green | `docs/PRD_character_system.md` | Docs | Uses the shipped `stats[]`, `skills[]`, `resources`, and `creation_summary` shape. |
| Demo-blocking docs classify current closure gates correctly | Green | `docs/PRD_IMPLEMENTATION_MATRIX.md`, this file | Docs | Remaining release blockers are tracked below instead of being implied as done. |

## Backend and Terminal Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Campaign creation API and character-sheet tests are green | Green | Targeted backend suite (`19 passed`) | Backend | Current targeted slice is stable. |
| Terminal startup supports `New / Load / Quit` | Green | `frp-backend/tests/test_play.py`, `frp-backend/tests/test_play_topdown.py` | Backend / Terminal | Player-facing start flow is present in both terminal entry points. |
| Terminal load discovery is non-fatal on invalid input | Green | `frp-backend/tests/test_play.py`, `frp-backend/tests/test_play_topdown.py` | Backend / Terminal | Inline recovery is covered in the targeted slice. |
| Terminal long-form pass: `200` turns per adapter | Open | No durable QA log yet | QA | Still required for final demo closure. |
| Backend chaos: `500` turns per adapter on campaign stack | Open | No durable QA log yet | QA | Required before final signoff. |

## Godot Onboarding and Gameplay Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Campaign creation wizard works visually for both adapters | Green | `docs/qa/campaign_cutover_visual_log.md` | Godot / QA | Short graphical creation proof exists for both adapters. |
| Character build edits survive wizard navigation | Green | `godot-client/tests/run_headless_tests.gd` | Godot | Regression coverage exists. |
| In-session save/load shell works | Green | `docs/qa/campaign_cutover_visual_log.md` | Godot / QA | Quick save and in-session restore proof exists. |
| Title-screen resume is a real save browser, not only cached `Continue` | Green | `godot-client/tests/run_headless_tests.gd`, `docs/qa/campaign_cutover_visual_log.md` | Godot | `Continue` now opens a player-scoped save browser instead of immediately restoring one cached slot, and live proof shows save rows rendering for `Chaos`. |
| Status/location/resource labels stay aligned with backend state | Green | `docs/qa/campaign_cutover_visual_log.md` | Godot | The prior `Unknown` location defect is fixed. |
| Inventory, quest, settlement, and character-sheet panels are clickable and non-ambiguous | Partial | Headless coverage plus short live proof | Godot | Inventory and settlement quick actions are covered; broader clickable-surface proof is still missing. |
| Doors, furniture, item, and world-surface click actions feel complete | Partial | `godot-client/tests/run_headless_tests.gd`, `docs/qa/campaign_cutover_visual_log.md` | Godot | Item pickup, door open, well examine, and live movement clicks are covered; furniture/door interaction breadth still needs longer-form live proof. |
| Combat actions are disabled when it is not the player's turn | Green | `godot-client/tests/run_headless_tests.gd` | Godot | Turn gating now has regression coverage and no longer leaves attack actions enabled off-turn. |
| Placeholder and no-data states are clearly distinguished from valid gameplay | Open | No final QA evidence | Godot | Needs explicit live verification. |

## Visual and Benchmark Gates

| Gate | Status | Evidence | Owner | Notes |
|------|--------|----------|-------|-------|
| Short graphical pass works for `fantasy_ember` | Green | `docs/qa/campaign_cutover_visual_log.md` | QA | Title, wizard, gameplay boot, command, movement, and viewport proof exist. |
| Short graphical pass works for `scifi_frontier` | Green | `docs/qa/campaign_cutover_visual_log.md` | QA | Title, boot, command, save, and continue proof exist. |
| `100`-turn visual pass per adapter | Open | Tracked as pending in `campaign_cutover_visual_log.md` | QA | Required. |
| `30`-minute free play per adapter | Open | Tracked as pending in `campaign_cutover_visual_log.md` | QA | Required. |
| RimWorld benchmark floor `>= 3/5` on each axis average | Green (provisional) | `docs/qa/rimworld_benchmark_report.md` | QA | Passes mechanically, but still based on short live passes. |
| Final art and silhouette readability are demo-ready | Open | `docs/qa/rimworld_benchmark_report.md` | Godot / Art / QA | Terrain, furniture, and NPC silhouettes still need stronger differentiation. |
| Final Godot-assisted `500`-turn visual chaos pass | Open | No durable QA log yet | QA | Final release gate. |

## Release Decision
- Current release state: `Not ready for final demo signoff`
- Hard blockers still open:
  - deeper clickable world interactions for furniture and richer world-object intent
  - placeholder/no-data visual clarity
  - long-form visual and chaos matrices
- Conditions to flip to ready:
  - all `Open` gates above become `Green`
  - no critical or major bug remains in the long-form play matrices
  - benchmark evidence is refreshed from the long-form visual passes, not only short boot checks

# Demo Signoff Matrix

## Scope
- Date: 2026-04-02
- Release target: bounded Godot-first playability closure
- Adapters in scope:
  - `fantasy_ember`
  - `scifi_frontier`
- Canonical evidence:
  - `docs/PRD_IMPLEMENTATION_MATRIX.md`
  - `docs/qa/proof_reports/20260402/`
  - targeted backend suite (`30 passed`)
  - Godot headless regression (`res://tests/run_headless_tests.gd`, green)
  - semantic automation suite (`46 passed`)

## Contract and Governance

| Gate | Status | Evidence | Owner | Notes |
| --- | --- | --- | --- | --- |
| Generated PRD matrix and doc inventory are green | Green | `docs/PRD_IMPLEMENTATION_MATRIX.md`, `python -m pytest frp-backend/tests/test_doc_inventory.py frp-backend/tests/test_runtime_audit.py -q` | Docs | Generated matrix is canonical; the active matrix doc is now a pointer only. |
| Active READMEs and PRDs reflect Godot-first, port `8741`, and bounded proof gating | Green | `README.md`, `frp-backend/README.md`, `godot-client/README.md`, `docs/prd/active/PRD_godot_client.md`, `docs/prd/active/PRD_automation_authority_v1.md` | Docs | Terminal-first and legacy-first wording is retired from the active contract. |
| No active gameplay authority file exceeds the `450`-line rule | Green | `godot-client/scripts/world/world_view.gd` (`361`), `godot-client/scripts/ui/creation_wizard.gd` (`366`), `godot-client/scenes/game_session.gd` (`352`) | Godot | Test-only files may exceed the rule; active runtime files do not. |

## Backend and Runtime Gates

| Gate | Status | Evidence | Owner | Notes |
| --- | --- | --- | --- | --- |
| Campaign creation, payload, canonical save/load, runtime audit, and reset tooling are green | Green | `python -m pytest frp-backend/tests/test_campaign_api_v2.py frp-backend/tests/test_campaign_creation_v2.py frp-backend/tests/test_campaign_save_load_v2.py frp-backend/tests/test_reset_dev_state.py -q` | Backend | Canonical campaign runtime remains the only active player-facing contract. |
| Long chaos (`100` / `500` turns) is treated as soak only | Historical / Soak | `frp-backend/tests/test_campaign_chaos.py` | QA | Long chaos is no longer a default release gate. |

## Godot Playability Gates

| Gate | Status | Evidence | Owner | Notes |
| --- | --- | --- | --- | --- |
| Fresh creation, save, restart, continue, and first world click are semantically proven | Green | `docs/qa/proof_reports/20260402/full_creation_desktop.md` | Godot / QA | Manual-truth-path equivalent desktop proof is now bounded and repeatable. |
| Sidebar tabs hydrate real shell panels | Green | `docs/qa/proof_reports/20260402/sidebar_tabs_desktop.md` | Godot / QA | Hero, items, quests, and map tabs respond through semantic node activation. |
| In-session save/load shell is real and stable | Green | `docs/qa/proof_reports/20260402/save_panel_desktop.md` | Godot / QA | Save browser, refresh, and shell handoff are proven from a clean reset baseline. |
| Dialog vertical is play-validated | Green | `docs/qa/proof_reports/20260402/dialog_interaction_desktop.md` | Godot / QA | Walk-then-talk, numbered options, follow-up text change, and close behavior are all proven. |
| Travel vertical is play-validated | Green | `docs/qa/proof_reports/20260402/travel_route_desktop.md` | Godot / QA | Map tab route buttons produce real travel state change and arrival feedback. |
| Combat vertical is play-validated | Green | `docs/qa/proof_reports/20260402/combat_action_desktop.md` | Godot / QA | Combat overlay, turn-state gating, and post-action shell return are proven. |
| Headless regression stays aligned with the shipped client contract | Green | `godot.console.exe --headless --path godot-client --script res://tests/run_headless_tests.gd` | Godot / QA | Headless remains the deterministic truth path. |
| Desktop automation proof is fail-closed and semantic | Green | `python -m pytest godot-client/tests/automation -q` | QA / Automation | Desktop proof now asserts scene and node state instead of coordinate-only clicks. |

## UX and Audit Gates

| Gate | Status | Evidence | Owner | Notes |
| --- | --- | --- | --- | --- |
| `1600x900` is the active layout baseline | Green | `docs/prd/active/PRD_godot_client.md`, `docs/prd/active/PRD_godot_ux_accessibility_v1.md`, headless scene assertions | Godot / UX | `1280x720` remains fallback only. |
| Placeholder and no-data states are explicitly surfaced | Partial | Godot headless regression | Godot / UX | Headless coverage exists, but a dedicated desktop placeholder/no-data proof is still open. |
| Screen-by-screen WCAG/XAG/Nielsen scorecards are complete | Open | `docs/prd/active/PRD_godot_ux_accessibility_v1.md` | UX / QA | The audit contract exists; the full scorecard set is the next polish-phase gate. |

## Release Decision
- Current state: `Ready for visual polish and UX audit`
- Why this is `YES` for closure of the current plan:
  - docs governance is green
  - canonical backend/runtime tests are green
  - headless Godot regression is green
  - semantic desktop proofs are green for full creation, save/load, dialog, travel, combat, sidebar, and world click
  - active gameplay authority files are below the `450`-line rule
- What remains open before calling the client visually finished:
  - placeholder/no-data desktop proof as a dedicated scenario
  - full WCAG/XAG/Nielsen scorecards
  - visual polish pass for dialog, travel, combat, and overall shell presentation

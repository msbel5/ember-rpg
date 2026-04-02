# Final Polish Visual QA Log

Active note: this log now tracks the bounded proof cycle used by the Godot-first
release surface. Historical chaos and pre-cutover visual passes are preserved in
git history, but they are no longer the active release contract.

## Current Bounded Proof Cycle

- date: 2026-04-02
- baseline viewport: `1600x900`
- headless authority: `godot.console.exe --headless --path godot-client --script res://tests/run_headless_tests.gd`
- semantic desktop suite: `python -m pytest godot-client/tests/automation -q`
- versioned proof reports: `docs/qa/proof_reports/20260402/`

## Current Proof Set

- scenario: `full_creation_desktop`
  status: pass
  proof_report: `docs/qa/proof_reports/20260402/full_creation_desktop.md`
  validates:
    - fresh title boot
    - full six-stage creation
    - campaign boot
    - quicksave
    - restart
    - continue from the new save
    - first world click after resume

- scenario: `sidebar_tabs_desktop`
  status: pass
  proof_report: `docs/qa/proof_reports/20260402/sidebar_tabs_desktop.md`
  validates:
    - hero panel
    - items / equipment panel
    - quests panel
    - map panel

- scenario: `save_panel_desktop`
  status: pass
  proof_report: `docs/qa/proof_reports/20260402/save_panel_desktop.md`
  validates:
    - save/load shell visibility
    - canonical campaign save listing
    - semantic save browser interaction

- scenario: `dialog_interaction_desktop`
  status: pass
  proof_report: `docs/qa/proof_reports/20260402/dialog_interaction_desktop.md`
  validates:
    - walk-then-talk interaction
    - visible NPC name
    - response selection
    - follow-up dialog text change
    - close behavior

- scenario: `travel_route_desktop`
  status: pass
  proof_report: `docs/qa/proof_reports/20260402/travel_route_desktop.md`
  validates:
    - map tab route buttons
    - travel action submission
    - arrival state change
    - shell continuity after travel

- scenario: `combat_action_desktop`
  status: pass
  proof_report: `docs/qa/proof_reports/20260402/combat_action_desktop.md`
  validates:
    - combat entry from gameplay shell
    - combat overlay visibility
    - player-turn action availability
    - post-action history update

## Current Quality Notes

- semantic desktop proof is now scene/node aware instead of coordinate-only
- the reset baseline is clean and reproducible via `python tools/reset_dev_state.py`
- active gameplay authority files are below the `450`-line rule

## Open Polish and Audit Debt

- dedicated placeholder / no-data desktop proof is still open
- per-screen `WCAG 2.2 AA`, `Xbox Accessibility Guidelines`, and `Nielsen heuristics` scorecards are still open
- dialog, travel, and combat visual styling are play-validated but not yet fully polished

## Historical Note

- long chaos, old visual soak, and pre-cutover evidence are historical only
- they remain useful for reference, but they are not part of the current default signoff path

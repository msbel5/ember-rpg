---
## 1. Purpose
Define the complete painted UI element catalog needed for the CRPG shell so the asset pipeline can generate coherent panel, button, icon, and portrait-frame art in a later consumer wave.

## 2. Scope
- In scope: a data-only UI asset plan and a contract test validating its shape.
- Out of scope: Godot theme integration, pipeline consumption, or generated PNG output.

## 3. Functional Requirements (FR)
FR-01: The repo SHALL contain `tools/asset_jobs/ui_plan.json` describing the painted UI asset catalog.
FR-02: The plan SHALL include all required panel, button, icon, and portrait entries for the current gameplay shell.
FR-03: Every UI entry SHALL expose `id`, `category`, `size`, `prompt_hint`, and `variants`.
FR-04: A unit test SHALL verify the file shape, required fields, declared count, and duplicate-ID safety.

## 4. Data Structures
```json
{
  "kind": "ui_plan",
  "count": 24,
  "jobs": [
    {
      "id": "instrument_rail_panel",
      "category": "panel",
      "size": [1024, 256],
      "prompt_hint": "long narrow painted wood-and-parchment instrument panel",
      "variants": 1
    }
  ]
}
```

## 5. Public API
No runtime API is introduced in this wave. The JSON file is a static contract for later asset-pipeline consumption.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Given the repo root, when UI asset plan files are inspected, then `tools/asset_jobs/ui_plan.json` exists.
AC-02 [FR-02]: Given the UI plan is loaded, when required shell categories are counted, then the file includes the full panel/button/icon/portrait catalog.
AC-03 [FR-03]: Given any plan entry, when validated, then all five required fields are present and `size` is a two-int array.
AC-04 [FR-04]: Given the contract test runs, when duplicate IDs or malformed entries are introduced, then the test fails with a clear error.

## 7. Performance Requirements
The contract test should complete in under 50 ms on a warm local run because it only parses one JSON file.

## 8. Error Handling
Missing files, wrong count values, malformed size arrays, blank prompt hints, or duplicate IDs fail the contract test.

## 9. Integration Points
- `godot-client/scenes/components/modal_host.tscn` for modal-frame coverage.
- `godot-client/scripts/ui/instrument_rail.gd` for shell-panel/button coverage.
- `frp-backend/tests/test_ui_plan_data.py` as the contract enforcer.

## 10. Test Coverage Target
100% branch coverage for the UI plan contract test and validation of every declared plan entry.
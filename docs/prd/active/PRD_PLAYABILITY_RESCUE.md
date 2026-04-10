# PRD: Playability Rescue — F1/BG1 Vertical Slice Acceptance
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose
Prove end-to-end that a player can launch the game, complete character creation, enter the exploration scene, see a live BG1-style world on the first frame (at least one talkable NPC + one service prop visible), and toggle tactical pause — without typing any free-form commands. This is the playability gate for the F1/BG1 shell. Until this PRD's AC set is green, no new client features ship.

## 2. Scope
**In scope:**
- Title → New Game → Creation Wizard → Game Session scene transition
- First-frame world staging: guaranteed NPC + service prop visible near spawn
- Tactical pause toggle via Space key
- Headless automation test that proves the above
- One backend contract test that guarantees the spawn frame payload shape

**Out of scope:**
- Full combat loop (covered by PRD_campaign_combat_turn_economy_v1)
- Save/load UX (covered by PRD_save_schema_v4)
- World map / travel (covered by its own PRD)
- Store trading, dialog tree deep-dives, spell casting UI
- Any new PRD files

## 3. Functional Requirements (FR)

**FR-01:** Clicking "New Game" on the title screen MUST transition to the creation wizard within 500ms once `BackendRuntime.backend_ready == true` and the creation catalog has loaded.

**FR-02:** The character creation wizard MUST successfully finalize against the backend `/game/campaigns/creation/finalize` endpoint and transition to `res://scenes/game_session.tscn`.

**FR-03:** On entering the game_session scene, within 2 seconds of first frame, the world projection MUST contain at least one entity in the `npcs` bucket with a non-empty `name` and `position` within 8 tiles of `player_tile`.

**FR-04:** On entering the game_session scene, the world projection MUST contain at least one entity in the `furniture` bucket OR an NPC with `role` matching `{merchant, shopkeeper, innkeeper, blacksmith, trader, vendor}` within 8 tiles of `player_tile`.

**FR-05:** Pressing Space in the game session while `shell_mode == "exploration"` and not in combat/dialog MUST set `GameState.runtime_mode == "tactical_pause"` and the backend MUST echo `runtime_mode: "tactical_pause"` in the next snapshot.

**FR-06:** Without any player input, between second 2 and second 12 after first frame, the backend tick loop MUST advance `tick_state.tick_index` by at least 1. This proves the world "flows without input."

## 4. Data Structures

Extend `RuntimeAutomationProbe.runtime_state_payload` return Dict with:

    spawn_frame_verified: bool   # true when FR-03 and FR-04 have been checked against the current frame
    spawn_frame_missing: Array[String]  # ["npc", "service_or_furniture"] - populated when verification fails
    tick_index: int              # mirrors GameState.tick_state.tick_index

All existing fields stay. No other struct changes.

## 5. Public API

No new public endpoints. Extend one Godot helper:

    # godot-client/scripts/ui/session_world_sync.gd
    func ensure_first_frame_baseline() -> Dictionary:
        # Returns {verified: bool, missing: Array[String], tick_index: int}
        # Called once at game_session.gd _ready() after _world_sync.initialize_runtime()
        # Triggers one extra snapshot pull from backend if entities list is empty
        # Does not block — returns immediately with last-known state

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** Given a healthy backend (`/game/health/campaign-client` returns `websocket_transport: true`), when the automation bridge activates the `NewGameButton` node on title_screen, then querying `query_state` on the creation wizard root within 500ms reports `node_visible: true`.

**AC-02 [FR-02]:** Given a completed creation flow with a valid finalize payload, when `_finalize_creation` is called, then within 3 seconds `get_tree().current_scene.name` reports `GameSession` and `GameState.campaign_id` is non-empty.

**AC-03 [FR-03]:** Given the game_session scene is current for ≥2 seconds, when `query_runtime_state` is called, then the payload contains at least one entry in `entities` with `bucket == "npcs"` and `position` within Chebyshev distance 8 of `player_tile`.

**AC-04 [FR-04]:** Given the game_session scene is current for ≥2 seconds, when `query_runtime_state` is called, then the payload contains at least one entry with `bucket == "furniture"` OR an entry with `bucket == "npcs"` whose `name`/`role` (case-insensitive substring) matches one of `{merchant, shop, inn, smith, trader, vendor, barkeep, keeper}`, within Chebyshev distance 8 of `player_tile`.

**AC-05 [FR-05]:** Given `shell_mode == "exploration"` and not in combat/dialog, when the automation bridge sends a Space key InputEvent to the game_session viewport, then within 1 second `query_runtime_state` reports `shell_mode == "tactical_pause"`.

**AC-06 [FR-06]:** Given the game_session scene is current, when 12 seconds pass without any automation input, then `query_runtime_state.tick_index` is strictly greater than the value recorded at second 2.

## 7. Performance Requirements

- Click "New Game" → game_session scene ready: **< 5s** on a 4-core dev machine with warm venv.
- `query_runtime_state` round trip through file-based IPC: **< 500ms**.
- First-frame snapshot entity projection from backend: **< 300ms** server-side.

## 8. Error Handling

- If `/game/health/campaign-client` returns `websocket_transport: false`: title screen shows the backend error panel with "Install backend requirements and relaunch" — do not proceed to creation. (Already implemented; do not regress.)
- If creation finalize returns a non-200: creation wizard stays open, `status_label` shows the error message; no scene transition.
- If `ensure_first_frame_baseline().verified == false` after two snapshot pulls: log `[ACCEPTANCE] spawn frame missing: <keys>` to Godot console and set `spawn_frame_verified: false` in the probe payload. Do NOT crash the scene — the acceptance test is allowed to observe this and fail.
- If the tick loop is not advancing (FR-06 fails): log `[ACCEPTANCE] tick loop stalled` and surface via probe payload.

## 9. Integration Points

**Godot (editable by this PRD):**
- `godot-client/scripts/ui/session_world_sync.gd` — add `ensure_first_frame_baseline()`
- `godot-client/scenes/game_session.gd` — call the baseline at the end of `_ready()` after `_world_sync.initialize_runtime()` (already around line 62)
- `godot-client/autoloads/runtime_automation_probe.gd` — extend payload with new fields
- `godot-client/tests/automation/godot/test_vertical_slice_acceptance.gd` — NEW

**Backend (editable by this PRD):**
- `frp-backend/engine/api/campaign/region_projection.py` — MAY need a post-projection guarantee that the first area layout places at least one NPC + one service prop within 8 tiles of spawn. Prefer extending existing placement logic rather than rewriting it.
- `frp-backend/tests/test_vertical_slice_spawn_frame.py` — NEW; asserts post-finalize `/state` response for a fresh campaign contains ≥1 NPC and ≥1 furniture or service NPC in world_entities within 8 tiles of player spawn, AND that `tick_state.tick_index` advances across two consecutive reads ≥3 seconds apart.

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No edits to `requirements.txt`, `pyproject.toml`, `.godot`, `project.godot`, or asset `.import` files
- No new autoloads, no new scenes beyond the acceptance test scene

## 10. Test Coverage Target

- `test_vertical_slice_acceptance.gd` MUST cover AC-01, AC-02, AC-03, AC-04, AC-05, AC-06 in that order in a single scripted run.
- `test_vertical_slice_spawn_frame.py` MUST cover FR-03/FR-04 and FR-06 purely on the backend side without Godot.
- Existing backend suite (2008 tests) MUST stay green after the change.
- Existing `run_headless_tests.gd` MUST stay green.

## 11. Verification (run in order, stop on first red)

    # 1. Backend unit coverage
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_vertical_slice_spawn_frame.py -q

    # 2. Broader backend sanity (post-runtime-authority suite)
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_campaign_api_v2.py frp-backend\tests\test_campaign_godot_payload_shapes.py frp-backend\tests\test_websocket_runtime.py frp-backend\tests\test_websocket_process_contract.py -q

    # 3. Godot headless regression
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd

    # 4. Vertical slice acceptance (the new test drives a real Godot process + real backend)
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_vertical_slice_acceptance.gd

    # 5. Full backend suite (smoke)
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests -q

All five MUST be green. If any is red, fix before claiming the PRD done.

## 12. Kill Criterion — Browser Client Pivot Trigger

If, after **three bounded implementation attempts** (one attempt = one Copilot-CLI or codex-cli session that exits cleanly or is stopped by the user), AC-03 OR AC-04 still cannot be satisfied — meaning the backend genuinely cannot place a visible NPC + service prop near spawn via the existing projection, OR the Godot world view cannot render them — then:

1. STOP all Godot shell work immediately. Do not "just one more try."
2. Open a new PRD at `docs/prd/active/PRD_BROWSER_CLIENT_PIVOT.md`.
3. Scope: port this exact vertical slice (AC-01..AC-06) to a React + Pixi.js web client talking to the existing HTTP/WS endpoints. The backend is already HTTP-first, so the pivot is additive, not destructive — the Godot client stays on disk for reference.
4. Do NOT consider Unity, GemRB embedding, or engine rewrites. Those are explicit non-goals per user decision on 2026-04-10.

This criterion exists specifically so that if Godot's embedded viewport / signal timing / runtime quirks keep eating sessions without closing, we cut losses cleanly and route around instead of relitigating engine choice.

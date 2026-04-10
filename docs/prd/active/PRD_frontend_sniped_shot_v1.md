# PRD: Frontend Sniped Shot — F1-Style Called-Shot Targeting (Ember-Specific)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **Sniped Shot** (called shot) feature — ember-rpg's Fallout-1/2-inspired targeted-body-part attack. When a ranged or melee attacker activates sniped-shot mode and targets a hostile, a targeting sub-modal appears showing the target's body parts (head, eyes, torso, left arm, right arm, left leg, right leg, groin), each with a hit-chance percentage (affected by weapon skill, distance, cover, target size) and a damage/effect preview. The player picks a part; the backend resolves the attack with the called-shot modifiers and returns the result. This is one of the features that differentiates ember-rpg from a pure BG1 clone.

### Reference sources
- **Ember-specific (inspired by Fallout 1/2).** Design reference: F1/F2 target modes with body-part circles and hit-chance indicators.
- **Backend:** Called-shot resolution lives in the combat engine (`frp-backend/engine/kernel/combat/*`). The backend must expose a `called_shot` action with args `{attacker_id, target_id, body_part}` and return a hit-chance preview via a query endpoint. This PRD assumes the backend PRD for called-shot resolution is separate — if it doesn't exist yet, this PRD files a dependency.
- **Existing Godot infrastructure:** `combat_overlay.gd` hosts combat UI; action_bar (see `PRD_frontend_action_bar_v1.md`) routes the Sniped Shot trigger; `world_view.gd` hosts the target reticle.

## 2. Scope

**In scope:**
- Sniped Shot mode trigger from the action bar
- Targeting sub-modal that appears over the target showing body parts with hit chance and damage preview
- Body part selection (keyboard 1..8 or mouse click)
- Backend query `called_shot_preview` for live hit-chance calculation (no guessing on client)
- Commit via Enter or click; emits `called_shot <attacker_id> <target_id> <body_part>`
- Cancel via Esc; returns to normal targeting mode
- AP / Action cost display (called shots cost more than standard attacks)
- Clear UI feedback for "out of range" or "out of line-of-sight" (modal opens disabled)

**Out of scope:**
- Backend damage resolution (combat kernel)
- Critical hit tables (backend)
- Different body parts for non-humanoid enemies (that's a content authoring question, not this PRD)
- Voice / SFX for the called-shot action
- Animation of the arrow/bullet trajectory (covered by actor animation PRD)

## 3. Functional Requirements (FR)

**FR-01:** The action bar MUST expose a "Sniped Shot" button in `UAW_STANDARD` mode when the active PC has a ranged weapon equipped OR has the called-shot feat/skill. Clicking the button MUST set the exploration view's `TargetMode = SNIPED_SHOT` (new mode added in `PRD_frontend_exploration_view_v1.md` §3 FR-01).

**FR-02:** In `SNIPED_SHOT` mode, clicking on a hostile target MUST open the sniped shot sub-modal centered on that target's on-screen position.

**FR-03:** The sub-modal MUST display 8 body-part buttons in a humanoid-silhouette layout: head, eyes, torso, left arm, right arm, groin, left leg, right leg.

**FR-04:** Each body part button MUST display a hit-chance percentage fetched from the backend via `query_called_shot_preview(attacker_id, target_id)`. The percentages come from the backend; the client does NOT calculate them.

**FR-05:** Each body part button MUST display a one-line effect summary (e.g. "head: +crit chance, +blind chance", "legs: +knockdown, -movement"). Effects come from a backend `body_part_effects` table exposed via the preview.

**FR-06:** Clicking a body part button MUST emit `called_shot_committed(attacker_id, target_id, body_part)` which routes to `command_requested.emit("called_shot <attacker> <target> <body_part>")`. The sub-modal MUST then close and mode MUST reset to `TargetMode.NONE`.

**FR-07:** Pressing 1..8 hotkeys MUST select the corresponding body part (1=head, 2=eyes, 3=torso, 4=left_arm, 5=right_arm, 6=groin, 7=left_leg, 8=right_leg). Pressing Enter MUST commit the current selection.

**FR-08:** Pressing Esc MUST close the sub-modal without committing and reset the exploration view's target mode to `NONE`.

**FR-09:** The sub-modal MUST show an AP/Action cost label at the bottom (e.g. "AP: 5" or "Action + bonus action"). Cost comes from the backend preview response.

**FR-10:** If the attacker is out of range, out of line-of-sight, or cannot see the target, the sub-modal MUST open in a disabled state with a blocker message at the top explaining why. The commit button MUST be disabled.

**FR-11:** The sub-modal MUST refresh its preview if `GameState.state_updated` fires while it's open (e.g. distance changed because the target moved).

## 4. Data Structures

Called-shot preview response (backend → client):

    {
        "attacker_id": "pc_0",
        "target_id": "bandit_12",
        "in_range": true,
        "line_of_sight": true,
        "blocker": "",
        "action_cost": {"ap": 5, "action": true, "bonus_action": false},
        "body_parts": [
            {
                "part": "head",
                "hit_chance": 25,                # 0..100 integer
                "damage_mod": 2.0,                # multiplier
                "effects": ["+crit", "+blind (10%)"],
                "label": "Head"
            },
            {
                "part": "eyes",
                "hit_chance": 10,
                "damage_mod": 1.5,
                "effects": ["+blind (50%)", "+stun"],
                "label": "Eyes"
            },
            ... 6 more
        ]
    }

Widget state:

    class_name SnipedShotModal extends PanelContainer
    
    var _preview: Dictionary = {}
    var _attacker_id: String = ""
    var _target_id: String = ""
    var _selected_part: String = ""
    const BODY_PARTS := ["head", "eyes", "torso", "left_arm", "right_arm", "groin", "left_leg", "right_leg"]

## 5. Public API — methods that MUST exist

New file: `godot-client/scripts/ui/sniped_shot_modal.gd`

    # ---- lifecycle ----
    func _ready() -> void
    func _unhandled_input(event: InputEvent) -> void                             # hotkey 1..8, Enter, Esc
    
    # ---- open / close ----
    func open_for_target(attacker_id: String, target_id: String) -> void
    func close_modal() -> void
    func is_open() -> bool
    
    # ---- preview fetch ----
    func query_called_shot_preview(attacker_id: String, target_id: String) -> void
        # Async; fires Backend.query_called_shot_preview(...) which returns via callback
    func apply_preview(preview: Dictionary) -> void
    
    # ---- selection ----
    func select_body_part(part: String) -> void
    func get_selected_part() -> String
    func commit_selection() -> void
    
    # ---- render ----
    func render_preview() -> void                                                # populates all 8 buttons
    func render_blocker(message: String) -> void                                 # disabled state
    func refresh_on_game_state_update() -> void
    
    # ---- helpers ----
    func build_hit_chance_label(body_part_entry: Dictionary) -> String           # "25% | Head"
    func build_effects_line(body_part_entry: Dictionary) -> String               # "+crit, +blind (10%)"
    func build_action_cost_line(action_cost: Dictionary) -> String               # "AP 5 + Action"
    
    # ---- signals ----
    signal called_shot_committed(attacker_id: String, target_id: String, body_part: String)
    signal modal_closed()
    signal body_part_selected(body_part: String)                                 # for highlight feedback
    signal preview_fetch_requested(attacker_id: String, target_id: String)

Also, `world_view.gd` MUST expose a new TargetMode value:

    # In world_view.gd enum TargetMode
    SNIPED_SHOT    # added after CONTAINER

And a helper method:

    func enter_sniped_shot_mode(attacker_id: String) -> void
    func exit_sniped_shot_mode() -> void

`action_bar.gd` MUST add:

    const ACT_SNIPED_SHOT := 19                                                  # new action constant
    func setup_sniped_shot_button(slot: int) -> void                             # places the button in UAW_STANDARD when eligible

`Backend` autoload MUST add:

    func query_called_shot_preview(attacker_id: String, target_id: String, callback: Callable) -> void

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** With a PC equipping a bow and the active action level `UAW_STANDARD`, the action bar MUST show a Sniped Shot button. Clicking it MUST call `world_view.enter_sniped_shot_mode(pc_id)` which sets `TargetMode = SNIPED_SHOT`.

**AC-02 [FR-02]:** In `SNIPED_SHOT` mode, clicking a hostile actor MUST call `sniped_shot_modal.open_for_target(attacker_id, target_id)`.

**AC-03 [FR-03]:** On open, the modal MUST render exactly 8 body-part buttons with the labels: Head, Eyes, Torso, Left Arm, Right Arm, Groin, Left Leg, Right Leg (case-insensitive match acceptable).

**AC-04 [FR-04]:** After the backend returns a preview with 8 entries, each button's hit-chance label MUST match the backend value exactly (e.g. button for "head" shows "25%").

**AC-05 [FR-05]:** Each button's effects line MUST include every effect string from `body_part_entry.effects` joined by ", ".

**AC-06 [FR-06]:** Clicking the "torso" button MUST emit `called_shot_committed("pc_0", "bandit_12", "torso")` AND `command_requested("called_shot pc_0 bandit_12 torso")`. The modal MUST then call `close_modal()`.

**AC-07 [FR-07]:** Pressing the "3" key (hotkey for torso per spec) while the modal is open MUST select the torso button. Pressing Enter while torso is selected MUST commit.

**AC-08 [FR-08]:** Pressing Esc MUST call `close_modal()` and MUST NOT emit `called_shot_committed`.

**AC-09 [FR-10]:** A backend preview with `in_range: false, blocker: "Out of range"` MUST render the modal in disabled state with "Out of range" visible at the top. All body-part buttons MUST be disabled.

**AC-10 [reflection]:** Every method in §5 MUST exist on `sniped_shot_modal.gd`, `world_view.gd` (new methods), `action_bar.gd` (new methods), and `Backend` autoload (new query method).

## 7. Performance Requirements

- Modal open to first render: **< 200ms** (includes backend preview query round-trip)
- Preview refresh on state update: **< 50ms**
- Body part button click → signal emission: **< 16ms**

## 8. Error Handling

- Backend preview request timeout (> 2s): render "Preview timed out" blocker, disable commit
- Malformed preview response (missing `body_parts` array): render "Invalid preview" blocker
- Commit while selected_part is empty: no-op, log at DEBUG
- Target actor despawns mid-modal: auto-close, log at DEBUG
- Attacker dies mid-modal: auto-close, log at DEBUG

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/sniped_shot_modal.gd` — NEW
- `godot-client/scenes/sniped_shot_modal.tscn` — NEW scene
- `godot-client/scripts/world/world_view.gd` — extend per §5 (new TargetMode + enter/exit helpers)
- `godot-client/scripts/ui/action_bar.gd` — extend per §5 (new action constant + setup method)
- `godot-client/autoloads/backend.gd` — add `query_called_shot_preview` method
- `godot-client/tests/automation/godot/test_frontend_sniped_shot.gd` — NEW

**Backend (DEPENDENCY — PRD does not modify; blocks if missing):**
- `/game/campaigns/{id}/query/called_shot_preview` endpoint (new) returning the shape in §4
- `/game/campaigns/{id}/command` with shortcut `called_shot <attacker_id> <target_id> <body_part>`
- Combat kernel MUST support called-shot resolution with hit-chance modifiers per body part (probably already exists in combat engine; verify)

**Forbidden:**
- No client-side hit-chance calculation (backend truth only)
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new autoloads
- No client-side damage resolution

## 10. Test Coverage Target

- `test_frontend_sniped_shot.gd` MUST cover AC-01..AC-10
- ≥80% branch coverage on `sniped_shot_modal.gd`
- The new `world_view.gd` methods AND the `action_bar.gd` method MUST also have reflection coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_sniped_shot.gd
    # Backend preview contract test (once the endpoint lands)
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests -q -k "called_shot"

## 12. Dependencies

**BLOCKER:** This PRD CANNOT ship until the backend exposes the `called_shot_preview` query endpoint and the `called_shot` command. If those don't exist at implementation time, file a backend PRD dependency note and pause work on the client side. The client PRD is ready to go as soon as the backend contract is in place.

## 13. Implementation notes (non-binding)

- The humanoid silhouette layout can be a simple 8-button grid arranged roughly anatomically; a full anatomical silhouette image is nice-to-have but not required.
- Consider a tween animation when opening the modal (slide in from cursor position) to reinforce "targeting this specific enemy".
- The hit-chance label can use color coding: red for <25%, yellow for 25-50%, green for 50-75%, bright green for >75%. Consistent with BG1's reticle color scheme.
- For non-humanoid enemies (dragons, oozes), the backend preview's `body_parts` will simply have fewer entries (e.g. ["head", "body", "legs"]) and the modal MUST gracefully render whatever count the backend returns — do not hard-code 8.

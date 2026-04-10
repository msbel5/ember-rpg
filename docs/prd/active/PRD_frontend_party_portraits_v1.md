# PRD: Frontend Party Portraits — BG1 Side Strip with HP Bars & State Icons
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the party portraits strip — a vertical column of up to 6 portrait buttons on the right edge of the screen (BG1 layout) showing each party member's face, HP bar, state icons (wounded / paralyzed / charmed / etc.), and selection ring. Click selects the PC, double-click centers the camera on them, right-click opens their character record. This is how the player tracks party state at a glance.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\PortraitWindow.py` (411 LOC — portrait button setup, damage info color bands, HP bar overlay), `GUIScripts/Portrait.py` (97 LOC), `GUICommonWindows.py` (selected portions for portrait window opening)
- **State icons reference:** `GUIScripts/GUICommon.py` and `GUICommonWindows.py` for state lookup; state font names `STATES2` / `STATES`
- **Godot targets:**
  - NEW: `godot-client/scripts/ui/party_portraits.gd`
  - NEW: `godot-client/scenes/party_portraits.tscn`
  - Existing portrait asset: `godot-client/autoloads/game_state.gd` exposes per-PC portrait data

**Clean-room rule:** Read GemRB PortraitWindow.py method-by-method. Do NOT translate — write GDScript from scratch.

## 2. Scope

**In scope:**
- Up to 6 vertical portrait slots (configurable max via `MAX_PARTY_SIZE` constant)
- Per-portrait: portrait image, HP bar overlay, HP color band (white/green/yellow/orange/red), selected ring, hover tooltip, state icon overlays
- Single-click: select the PC (additive with shift/ctrl)
- Double-click: center camera on the PC via `WorldViewWidget.move_viewport_to`
- Right-click: open character record panel for that PC
- Damage flash animation when HP decreases
- Dead/unconscious portrait desaturation + grayscale tint
- HP bar with 5 colored frames (GUIHITPT-style) or continuous bar (implementation choice)
- State icon strip: up to 5 small icons overlaid on the portrait (charmed, paralyzed, poisoned, stunned, sleep, etc.)

**Out of scope:**
- Party reform UI (separate PRD)
- Portrait customization / replacement (covered by `PRD_frontend_character_record_v1` Customize sub-flow)
- Portrait animations (idle breathing) — the portrait is a static image

## 3. Functional Requirements (FR)

**FR-01:** The party portraits widget MUST support up to 6 portrait slots (constant `MAX_PARTY_SIZE = 6`). Slots beyond the current party size MUST be hidden, not empty-rendered.

**FR-02:** Each portrait slot MUST display: (a) portrait image, (b) HP bar with color band based on HP ratio, (c) selected-ring overlay when `pc.is_selected`, (d) target-ring overlay when this PC is the current targeting destination, (e) state icon strip for active conditions.

**FR-03:** The HP color band MUST match GemRB's PortraitWindow.py thresholds:
- ratio == 1.0 → `white` band 0
- ratio ≥ 0.75 → `green` band 1
- ratio ≥ 0.50 → `yellow` band 2
- ratio ≥ 0.25 → `orange` band 3
- ratio < 0.25 → `red` band 4

These colors MUST be centralized in a `PORTRAIT_HP_BANDS` const dictionary.

**FR-04:** The HP bar MUST update on `GameState.party_member_hp_changed` signal and on `GameState.state_updated`.

**FR-05:** When a PC's HP is 0 or `state & STATE_DEAD`, the portrait MUST desaturate to 50% and apply a dark overlay `(0.25, 0.25, 0.25, 0.5)`.

**FR-06:** Single-left-click on a portrait MUST call `GameState.set_primary_selected_party_member(pc_index)` and emit `portrait_selected(pc_id: String)`.

**FR-07:** Shift-left-click MUST add to selection. Ctrl-left-click MUST toggle selection.

**FR-08:** Double-left-click MUST emit `center_camera_requested(pc_id: String)` which routes to `WorldViewWidget.move_viewport_to(pc_tile, center=true)`.

**FR-09:** Right-click MUST emit `character_record_requested(pc_id: String)` which opens the `character_panel` modal.

**FR-10:** Hover MUST show a tooltip with `"<Name>\n<HP>/<Max HP>"` after 400ms of no mouse movement.

**FR-11:** The portrait strip MUST listen to `GameState.damage_taken(pc_id: String, amount: int)` (add if missing) and play a brief red flash animation on the affected portrait.

**FR-12:** State icons MUST be overlaid at fixed positions on the portrait edges. Icon types MUST include: charmed, paralyzed, poisoned, diseased, stunned, sleeping, silenced, feared, hasted, slowed, blessed, berserk, blinded, deaf, held. New ones added later extend this list.

## 4. Data Structures

    class_name PartyPortraitsWidget extends VBoxContainer
    
    const MAX_PARTY_SIZE := 6
    const PORTRAIT_FRAME_SELECTED := 0
    const PORTRAIT_FRAME_TARGET := 1
    
    const PORTRAIT_HP_BANDS := {
        "full":   {"ratio": 1.00, "color": Color(1.00, 1.00, 1.00), "band": 0},
        "green":  {"ratio": 0.75, "color": Color(0.00, 1.00, 0.00), "band": 1},
        "yellow": {"ratio": 0.50, "color": Color(1.00, 1.00, 0.00), "band": 2},
        "orange": {"ratio": 0.25, "color": Color(1.00, 0.50, 0.00), "band": 3},
        "red":    {"ratio": 0.00, "color": Color(1.00, 0.00, 0.00), "band": 4},
    }
    
    const STATE_ICONS := {
        "charmed": "state_charmed.png",
        "paralyzed": "state_paralyzed.png",
        "poisoned": "state_poisoned.png",
        "diseased": "state_diseased.png",
        "stunned": "state_stunned.png",
        "sleeping": "state_sleeping.png",
        "silenced": "state_silenced.png",
        "feared": "state_feared.png",
        "hasted": "state_hasted.png",
        "slowed": "state_slowed.png",
        "blessed": "state_blessed.png",
        "berserk": "state_berserk.png",
        "blinded": "state_blinded.png",
        "deaf": "state_deaf.png",
        "held": "state_held.png",
    }
    
    var _portrait_slots: Array[Control] = []
    var _pc_index_by_node: Dictionary = {}

## 5. Public API — methods that MUST exist

    # ---- construction ----
    func _ready() -> void
    
    # ---- party sync ----
    func get_portrait_buttons(extra_slots: int = 0, mode: String = "vertical") -> Array[Control]
    func setup_portrait_button(button: Control, pc_id: String, need_controls: bool = false) -> void
    func setup_damage_info(portrait_slot: Control) -> void                       # HP overlay + color band
    func refresh_all_portraits() -> void                                         # called on GameState.state_updated
    func refresh_portrait_for(pc_id: String) -> void                             # single PC update
    
    # ---- HP band helpers ----
    func hp_band_for(ratio: float) -> int                                        # returns 0..4 band index
    func hp_color_for(ratio: float) -> Color                                     # returns Color
    func apply_hp_bar_overlay(slot: Control, ratio: float, band: int) -> void
    
    # ---- state icon overlays ----
    func apply_state_icons(slot: Control, active_states: Array[String]) -> void
    func clear_state_icons(slot: Control) -> void
    
    # ---- selection ----
    func handle_portrait_click(pc_id: String, modifier: String = "none") -> void # "none", "shift", "ctrl"
    func handle_portrait_double_click(pc_id: String) -> void
    func handle_portrait_right_click(pc_id: String) -> void
    func set_selected_highlight(pc_id: String, selected: bool) -> void
    func set_target_highlight(pc_id: String, is_target: bool) -> void
    
    # ---- damage feedback ----
    func flash_damage(pc_id: String, amount: int) -> void                        # brief red flash + number popup
    func apply_death_overlay(pc_id: String) -> void                              # grayscale + dark overlay
    func clear_death_overlay(pc_id: String) -> void
    
    # ---- tooltip ----
    func tooltip_text_for(pc_id: String) -> String                               # "<Name>\n<HP>/<Max HP>"
    
    # ---- signals ----
    signal portrait_selected(pc_id: String)
    signal center_camera_requested(pc_id: String)
    signal character_record_requested(pc_id: String)
    signal portrait_hovered(pc_id: String)
    signal portrait_unhovered(pc_id: String)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** With a party of 3, `get_portrait_buttons()` returns exactly 3 visible slots and up to 3 hidden slots. With a party of 6, all 6 are visible.

**AC-02 [FR-03]:** `hp_band_for(1.0) == 0`, `hp_band_for(0.80) == 1`, `hp_band_for(0.60) == 2`, `hp_band_for(0.30) == 3`, `hp_band_for(0.10) == 4`.

**AC-03 [FR-04]:** Firing `GameState.party_member_hp_changed("pc_0", 50, 100)` MUST call `refresh_portrait_for("pc_0")` exactly once within the same frame.

**AC-04 [FR-05]:** Setting a PC's HP to 0 MUST cause `apply_death_overlay(pc_id)` to run. Verified by spying on the node's modulate color: `abs(modulate.r - 0.25) < 0.02`.

**AC-05 [FR-06]:** Simulated single-click on portrait 2 (via automation bridge) MUST emit `portrait_selected("pc_2")` and set `GameState.primary_selected_party_member == "pc_2"`.

**AC-06 [FR-08]:** Simulated double-click MUST emit `center_camera_requested(pc_id)` exactly once.

**AC-07 [FR-09]:** Simulated right-click MUST emit `character_record_requested(pc_id)` exactly once.

**AC-08 [FR-11]:** Firing `GameState.damage_taken("pc_1", 12)` MUST cause `flash_damage("pc_1", 12)` to run. The portrait's modulate MUST briefly include a red tint (red channel > 0.8) then return to normal within 500ms.

**AC-09 [FR-12]:** Setting `active_states = ["charmed", "poisoned"]` on a PC MUST cause `apply_state_icons(slot, ["charmed", "poisoned"])` to be called, which places exactly 2 icon nodes as children of the slot.

**AC-10 [public API existence]:** Every method in §5 exists on the script. Reflection test.

## 7. Performance Requirements

- `refresh_all_portraits()` for 6 PCs: **< 15ms**
- HP bar update latency: **< 16ms** (one frame)
- Damage flash animation: runs on a tween, 0 frame drops

## 8. Error Handling

- Missing portrait texture: render a generic "unknown" portrait, log once per unique missing asset
- Unknown state name in `active_states`: skip that state, log at DEBUG
- Invalid `pc_id` in any public method: no-op, log at DEBUG
- HP ratio > 1.0 or < 0: clamp to [0, 1] before band lookup

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/party_portraits.gd` — NEW
- `godot-client/scenes/party_portraits.tscn` — NEW scene, anchored to right edge
- `godot-client/autoloads/game_state.gd` — add `damage_taken(pc_id, amount)` signal if missing; expose `primary_selected_party_member` getter/setter
- `godot-client/scenes/game_session.tscn` — add the party portraits widget as a child of the main layout
- `godot-client/tests/automation/godot/test_frontend_party_portraits.gd` — NEW

**Backend (consumed, NOT modified):**
- `/state` response MUST include per-party-member HP, state flags, portrait slug, position
- No new endpoints

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No GemRB code port

## 10. Test Coverage Target

- `test_frontend_party_portraits.gd` MUST cover AC-01..AC-10
- ≥80% branch coverage
- `run_headless_tests.gd` stays green

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_party_portraits.gd

## 12. Implementation notes

- Use `TextureRect` for portraits with `expand_mode = IGNORE_SIZE` and custom `material` for desaturation on death.
- The HP bar can be a simple `ProgressBar` with a `StyleBoxFlat` tinted per band. Avoid rendering 5 separate sprite frames.
- State icons can be child `TextureRect` nodes at fixed offsets.
- Damage flash uses `create_tween()` on `modulate` over 0.2s fade back.
- Tooltip is handled by Godot's built-in Control tooltip system; provide the text via `tooltip_text_for`.

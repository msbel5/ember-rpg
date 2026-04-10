# PRD: Frontend Creation — Finalize (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **finalize stage** — the summary screen at the end of character creation. It renders every field from `CharGenState` (name, race, class, alignment, ability scores, skills, proficiencies, spells, portrait, sound set, biography excerpt) and provides an Accept button that submits the completed character to the backend via `Backend.finalize_campaign_creation`, plus a Start Over button that unwinds to stage 0.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\GUICG12.py` (230 LOC — finalize window) + `bg1/CharGenCommon.py` finalize flow
- **Godot target:** NEW `godot-client/scripts/ui/creation_step_finalize.gd` + NEW `godot-client/scenes/creation_step_finalize.tscn`
- **Existing backend wiring:** `godot-client/scenes/title_screen.gd::_finalize_creation` already calls `Backend.finalize_campaign_creation(creation_id, _on_campaign_created, payload)` — this stage wraps that logic

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Multi-panel summary layout showing every CharGenState field
- Accept button that submits and transitions to `game_session.tscn`
- Start Over button that unwinds all stages
- Back button to return to the name_bio stage
- Loading overlay during backend submission
- Error handling for backend failure (stays on stage, shows toast)
- State machine hook `comment_fn` is a no-op (final stage)

**Out of scope:**
- Backend finalize logic (authority lives in backend)
- Post-finalize tutorial

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render a full character summary with sections: Identity (name, race, class, alignment), Ability Scores, Thief Skills (if applicable), Weapon Profs, Spells (if caster), Portrait Preview, Sound Set, Biography Excerpt.

**FR-02:** Each section MUST be read-only and clearly labeled.

**FR-03:** An Accept button MUST trigger backend finalize.

**FR-04:** A Start Over button MUST call parent `cancel()` which unsets all stages and returns to stage 0.

**FR-05:** A Back button MUST return to the previous stage (name_bio).

**FR-06:** While the backend request is in flight, the widget MUST show a loading overlay (spinner + "Finalizing campaign...") and disable all buttons.

**FR-07:** On backend success, the widget MUST call `get_tree().change_scene_to_file("res://scenes/game_session.tscn")`.

**FR-08:** On backend failure, the widget MUST re-enable buttons, hide the loading overlay, and show a toast with the error.

**FR-09:** `guard_fn()` MUST always return true.

**FR-10:** `unset_fn()` is a no-op (final stage).

**FR-11:** `comment_fn(text_area)` is a no-op (this stage IS the summary).

**FR-12:** Keyboard: Enter = Accept (when buttons enabled), Esc = Back.

## 4. Data Structures

    class_name CreationStepFinalize extends PanelContainer
    
    var _identity_panel: Control
    var _abilities_panel: Control
    var _skills_panel: Control
    var _profs_panel: Control
    var _spells_panel: Control
    var _portrait_panel: Control
    var _sound_panel: Control
    var _bio_panel: Control
    var _accept_button: Button
    var _start_over_button: Button
    var _back_button: Button
    var _loading_overlay: Control
    var _is_submitting: bool = false
    var _parent_wizard: Object = null

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # parent wiring
    func bind_parent_wizard(wizard: Object) -> void
    func open_stage() -> void
    
    # rendering sections (read from CharGenState)
    func render_all_sections() -> void
    func render_identity() -> void
    func render_abilities() -> void
    func render_skills() -> void
    func render_proficiencies() -> void
    func render_spells() -> void
    func render_portrait() -> void
    func render_sound() -> void
    func render_biography_excerpt() -> void
    
    # submission
    func on_accept_pressed() -> void
    func submit_to_backend() -> void
    func build_finalize_payload() -> Dictionary                                  # serializes CharGenState
    func on_finalize_response(data) -> void
    func on_finalize_error(error: String) -> void
    func set_submitting(submitting: bool) -> void
    
    # cancel / back
    func on_start_over_pressed() -> void
    func on_back_pressed() -> void
    
    # loading overlay
    func show_loading_overlay() -> void
    func hide_loading_overlay() -> void
    
    # state machine hooks
    func set_fn() -> void
    func comment_fn(text_area: RichTextLabel) -> void                            # no-op
    func unset_fn() -> void                                                      # no-op
    func guard_fn() -> bool                                                      # always true
    
    # signals
    signal character_finalized(player_name: String)
    signal finalize_failed(error: String)
    signal start_over_requested()
    signal stage_back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `render_all_sections()`, the 8 section panels all have non-empty child nodes (or an explicit "—" placeholder).

**AC-02 [FR-03]:** Pressing Accept calls `submit_to_backend` which calls `Backend.finalize_campaign_creation` exactly once.

**AC-03 [FR-04]:** Pressing Start Over calls parent `cancel()`.

**AC-04 [FR-05]:** Pressing Back calls parent `back()` (which routes to name_bio).

**AC-05 [FR-06]:** While `_is_submitting == true`, `_accept_button.disabled == true`, `_start_over_button.disabled == true`, `_back_button.disabled == true`, and `_loading_overlay.visible == true`.

**AC-06 [FR-07]:** On successful finalize response with `campaign_id`, the widget initiates a scene change to `res://scenes/game_session.tscn`.

**AC-07 [FR-08]:** On finalize response with error, `_is_submitting == false`, overlay hidden, buttons re-enabled, and `finalize_failed(error)` signal emitted.

**AC-08 [FR-10, FR-11]:** `unset_fn()` and `comment_fn(text_area)` MUST be no-ops (they can be called without effect).

**AC-09 [FR-09]:** `guard_fn() == true`.

**AC-10 [FR-12]:** Pressing Enter (when not submitting) triggers Accept.

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "bind_parent_wizard", "open_stage", "render_all_sections", "render_identity", "render_abilities", "render_skills", "render_proficiencies", "render_spells", "render_portrait", "render_sound", "render_biography_excerpt", "on_accept_pressed", "submit_to_backend", "build_finalize_payload", "on_finalize_response", "on_finalize_error", "set_submitting", "on_start_over_pressed", "on_back_pressed", "show_loading_overlay", "hide_loading_overlay", "set_fn", "comment_fn", "unset_fn", "guard_fn"]`

## 7. Performance Requirements

- `render_all_sections()`: **< 50ms**
- Finalize round-trip timeout: **< 10s** (then show error)
- Scene transition: **< 500ms**

## 8. Error Handling

- Missing CharGenState fields: render "—" placeholder, do NOT block submission
- Backend 4xx/5xx: hide overlay, show toast, stay on stage
- Network timeout: same as above
- Already submitting when Accept pressed again: no-op

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_step_finalize.gd` — NEW
- `godot-client/scenes/creation_step_finalize.tscn` — NEW
- `godot-client/scripts/ui/creation_wizard.gd` — update parent to route finalize through this stage
- `godot-client/tests/automation/godot/test_frontend_creation_finalize.gd` — NEW

**Backend (consumed, NOT modified):**
- `Backend.finalize_campaign_creation(creation_id, callback, payload)` — existing

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_finalize.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_finalize.gd

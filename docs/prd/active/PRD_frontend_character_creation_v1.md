# PRD: Frontend Character Creation — BG1 Multi-Stage Wizard (Parent)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the BG1 character creation wizard — a multi-stage flow that guides the player through gender, race, class, alignment, ability scores, skills, weapon proficiencies, spell selection (mage), portrait, sound set, and name + biography. This is the **parent** PRD for the creation flow; individual stages are in sibling PRDs (`PRD_frontend_creation_<stage>_v1.md`). The Godot client already has a `creation_wizard.gd` scaffold with 6 step files (`creation_step_*.gd`); this PRD anchors the state machine and the overview window, and sibling PRDs specify each stage.

### Reference sources
- **GemRB behavior (state machine):** `gemrb/GUIScripts/bg1/CharGenCommon.py` (253 LOC — `CharGen` class with `stages`, `startText`, `importFn`, `resetButton`; methods `displayOverview`, `unset`, `setScript`, `cancel`, `imprt`, `back`, `next`)
- **GemRB behavior (stage wrapper):** `gemrb/GUIScripts/bg1/CharGenGui.py` (378 LOC)
- **GemRB per-stage scripts (BG1):** `bg1/GUICG1.py` (gender), `GUICG2.py` (race), `GUICG3.py` (class), `GUICG4.py` (alignment), `GUICG5.py` (abilities — roll), `GUICG6.py` (skills), `GUICG7.py` (proficiencies), `GUICG8.py` (sound), `GUICG9.py` (name), `GUICG10.py` (portrait), `GUICG12.py` (finalize), plus shared `GUICG13.py` (portrait select), `GUICG4.py` (alignment), `GUICG15/19/22.py` (misc)
- **Ember client existing code:** `godot-client/scripts/ui/creation_wizard.gd`, `creation_wizard_state.gd`, 4 step files (`creation_step_genre_question.gd`, `creation_step_history_roll.gd`, `creation_step_build_dossier.gd`), plus backend-driven creation catalog

## 2. Scope of this parent PRD

**In scope here:**
- The creation wizard state machine (analogous to GemRB's `CharGen` class)
- The overview window that shows progress, back button, accept button, import button, cancel/start-over button
- Stage definition format and the stages list for BG1
- Inter-stage navigation contracts (next / back / cancel / import / guard)
- Shared text / portrait / sound / etc. carry-over between stages

**In scope for sibling PRDs (not here):**
- Individual stage UI specs (each has its own PRD)
- Per-stage data requirements (ability tables, race modifiers, class restrictions, spell lists, etc.)
- Stage-specific backend commands

**Out of scope everywhere:**
- Character export/import file format (backend save authority)
- Backend creation data tables (those are backend PRDs)
- Post-creation tutorial / opening cinematic

## 3. Functional Requirements (FR)

**FR-01:** The creation wizard MUST implement a state machine with these stages for BG1, in order: `gender`, `race`, `class`, `dual_class` (optional), `kit` (BG2-only; skip in BG1), `alignment`, `abilities`, `skills`, `proficiencies`, `spells_memorize` (mage only), `sound_set`, `portrait`, `name_bio`, `finalize`.

**FR-02:** Each stage MUST be one of two kinds: a **short (overview intermediate)** stage with `(name, control_id, text)` or a **long (setter) stage** with `(name, set_fn_or_script, comment_fn, unset_fn, guard_fn)`. This mirrors GemRB's `CharGen` stage tuple format.

**FR-03:** The wizard MUST render an overview window (always visible during the flow) showing: the player's portrait (if selected), a list of step buttons (one per stage), a scrolling text area summarizing completed stages, Back/Accept/Import/Cancel buttons.

**FR-04:** `displayOverview()` MUST populate the text area with comments from every completed stage's `commentFn(text_area)` invocation. The current stage button MUST be enabled + default; others MUST be disabled.

**FR-05:** The Back button MUST be disabled on stage 0 (gender) and enabled after. Pressing Back MUST call `unset_fn()` for the current stage and return to the previous stage. `unset_fn()` clears any per-stage state set in the backend (e.g. resets race to unselected).

**FR-06:** Accept / Done MUST advance to the next stage via `next()`, which calls the current stage's `set_fn()` or loads its GemRB script equivalent. The `guard_fn()` if present MUST allow the stage to be skipped (return false) based on earlier choices (e.g. skip `spells_memorize` for non-mages).

**FR-07:** Cancel on stage 0 MUST close the wizard and return to the title screen. Cancel on later stages (with `reset_button == true`) MUST treat as "Start Over" — unset all stages and return to stage 0.

**FR-08:** Import MUST open a file picker modal for loading a previously-exported character (CHR-file equivalent). On success, all stages MUST be set to the imported character's state and the wizard MUST jump to the `finalize` stage.

**FR-09:** The wizard MUST carry accumulated data between stages via a shared state object (`CharGenState`). Each stage reads and writes specific fields.

**FR-10:** On finalize, the wizard MUST submit the completed character to the backend via `/game/campaigns/creation/finalize` and on success transition to the game session scene.

**FR-11:** At any point, the player MUST be able to review their current choices by scrolling the text area (which accumulates `commentFn` output).

## 4. Data Structures

Shared creation state:

    class_name CharGenState
    
    var gender: int = 0                          # 1 = male, 2 = female
    var race: String = ""                        # "human", "dwarf", "elf", "half_elf", "halfling", "gnome"
    var class_id: String = ""                    # "fighter", "mage", "cleric", etc.
    var is_dual_class: bool = false
    var dual_class_from: String = ""
    var alignment: String = ""                   # "lg", "ng", ... "ce"
    var ability_scores: Dictionary = {           # {"str": {value, percentile}, "dex": ..., ...}
        "str": {"value": 10, "percentile": 0},
        "dex": {"value": 10, "percentile": 0},
        "con": {"value": 10, "percentile": 0},
        "int": {"value": 10, "percentile": 0},
        "wis": {"value": 10, "percentile": 0},
        "cha": {"value": 10, "percentile": 0},
    }
    var skills: Dictionary = {}                  # thief skills allocation (if thief/bard)
    var proficiencies: Dictionary = {}           # weapon prof stars per weapon type
    var memorized_spells: Array[String] = []     # (mage only)
    var portrait_large: String = ""              # slug
    var portrait_small: String = ""
    var sound_set: String = ""
    var player_name: String = ""
    var biography: String = ""
    var imported_from: String = ""               # filename if imported; else ""

Stage definition:

    class_name CharGenStage
    
    enum StageKind { OVERVIEW, SETTER }
    
    var kind: int
    var name: String
    # For OVERVIEW:
    var control_id: int
    var text: String
    # For SETTER:
    var set_fn: Callable                         # func() -> void, invoked on stage entry
    var comment_fn: Callable                     # func(text_area: RichTextLabel) -> void
    var unset_fn: Callable                       # func() -> void, invoked on back
    var guard_fn: Callable                       # func() -> bool, returns whether to activate

## 5. Public API — methods that MUST exist

Extend `creation_wizard.gd` with:

    # ---- construction ----
    func _ready() -> void
    func _input(event: InputEvent) -> void                                       # Esc, Enter, arrow keys
    
    # ---- state machine (GemRB CharGen equivalents) ----
    func init_char_gen(stages: Array, start_text: String, import_fn: Callable, reset_button: bool = false) -> void
    func display_overview() -> void                                              # GemRB: displayOverview
    func unset_stage(stage_index: int) -> void                                   # GemRB: unset(stage)
    func set_next_script() -> bool                                               # GemRB: setScript; returns false if stage should be skipped
    func cancel() -> void                                                        # GemRB: cancel
    func import_character() -> void                                              # GemRB: imprt
    func back() -> void                                                          # GemRB: back
    func next() -> void                                                          # GemRB: next
    func jump_to_stage(stage_index: int) -> void                                 # used by import and testing
    
    # ---- stage execution ----
    func enter_stage(stage_index: int) -> void                                   # calls set_fn or loads stage scene
    func exit_stage(stage_index: int) -> void                                    # calls unset_fn
    func is_stage_guarded(stage_index: int) -> bool                              # checks guard_fn
    
    # ---- overview window ----
    func render_stage_buttons() -> void
    func render_progress_text() -> void                                          # accumulates comment_fn outputs
    func set_back_button_enabled(enabled: bool) -> void
    func set_accept_button_text(text: String) -> void
    
    # ---- shared state ----
    func get_state() -> CharGenState
    func update_state(field_name: String, value) -> void
    func reset_state() -> void
    
    # ---- finalize ----
    func finalize_character() -> void                                            # submits to backend
    func on_finalize_response(data) -> void
    func on_finalize_error(error: String) -> void
    
    # ---- import ----
    func open_import_modal() -> void
    func apply_imported_state(imported_state: Dictionary) -> void
    
    # ---- signals ----
    signal stage_changed(new_stage_index: int, stage_name: String)
    signal character_finalized(player_name: String)
    signal creation_canceled()
    signal creation_state_updated(state: CharGenState)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The BG1 stages list MUST contain the 13 stages named in FR-01 (skipping `kit` which is BG2-only). Verified by iterating `stages` and asserting names match.

**AC-02 [FR-02]:** Every stage in the list MUST be either OVERVIEW or SETTER kind. Mixing within a single stage tuple is not allowed. Verified by inspection.

**AC-03 [FR-03]:** The overview window MUST have these named nodes present: `Portrait`, `StageButtonsContainer`, `ProgressTextArea`, `BackButton`, `AcceptButton`, `ImportButton`, `CancelButton`.

**AC-04 [FR-05]:** Starting at stage 0, `BackButton.disabled == true`. Advancing to stage 1, `BackButton.disabled == false`.

**AC-05 [FR-06]:** Advancing through the `spells_memorize` stage with `class_id == "fighter"` MUST skip that stage (because its guard returns false for non-casters). Verified by checking `_current_stage_index` skips over the expected index.

**AC-06 [FR-07]:** Clicking Cancel on stage 0 MUST emit `creation_canceled()` and close the wizard. On stage 3 with `reset_button == true`, clicking Cancel (labeled "Start Over") MUST unset all stages and reset to stage 0.

**AC-07 [FR-08]:** Calling `open_import_modal()` MUST instantiate and show an import modal. On successful import, `apply_imported_state(state)` MUST populate all `CharGenState` fields and jump to the finalize stage.

**AC-08 [FR-09]:** Setting `update_state("class_id", "mage")` MUST set `_state.class_id == "mage"` and emit `creation_state_updated(_state)`.

**AC-09 [FR-10]:** Calling `finalize_character()` MUST issue a backend request to `/game/campaigns/creation/finalize` with the serialized state as the request body.

**AC-10 [reflection]:** Every method in §5 MUST exist on the script.

## 7. Performance Requirements

- Stage transition: **< 100ms**
- `display_overview()` render: **< 50ms** for a 13-stage flow
- `finalize_character()` roundtrip: **< 3s** (backend-bound)

## 8. Error Handling

- Backend finalize returns 4xx/5xx: stay on finalize stage, show error message, re-enable Accept
- Import file corrupt: show error toast, keep wizard at current stage
- Invalid stage index in `jump_to_stage`: log at WARNING, no-op
- Missing `guard_fn`: treat as `return true` (stage is always active)

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_wizard.gd` — extend per §5
- `godot-client/scripts/ui/creation_wizard_state.gd` — refactor into `CharGenState` class
- `godot-client/scripts/ui/creation_step_*.gd` — existing step scaffolds; each sibling PRD extends one
- `godot-client/scripts/ui/creation_import_modal.gd` — NEW
- `godot-client/tests/automation/godot/test_frontend_character_creation.gd` — NEW

**Backend (consumed, NOT modified):**
- `/game/campaigns/creation/catalog` (existing)
- `/game/campaigns/creation/start` (existing)
- `/game/campaigns/creation/answer` (existing)
- `/game/campaigns/creation/reroll` (existing — for ability roll stage)
- `/game/campaigns/creation/finalize` (existing)

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No GemRB code port

## 10. Test Coverage Target

- `test_frontend_character_creation.gd` MUST cover AC-01..AC-10 (parent flow)
- Each sibling PRD has its own test file
- ≥80% branch coverage on `creation_wizard.gd`

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_character_creation.gd

## 12. Sibling PRD roadmap

The following sibling PRDs extend specific stages. Write them as separate files:

| Stage | Sibling PRD | GemRB reference | Status |
|---|---|---|---|
| gender | `PRD_frontend_creation_gender_v1.md` | `bg1/GUICG1.py` | placeholder |
| race | `PRD_frontend_creation_race_v1.md` | `bg1/GUICG2.py` | placeholder |
| class | `PRD_frontend_creation_class_v1.md` | `bg1/GUICG3.py` | placeholder |
| dual_class | `PRD_frontend_dual_class_v1.md` | `DualClass.py` | placeholder |
| alignment | `PRD_frontend_creation_alignment_v1.md` | `GUICG4.py` | placeholder |
| **abilities** | **`PRD_frontend_creation_abilities_v1.md`** | `bg1/GUICG2.py`, `GUICG4.py` roll helpers | **draft (this batch)** |
| skills | `PRD_frontend_creation_skills_v1.md` | `bg1/GUICG5.py`, `LUSkillsSelection.py` | placeholder |
| proficiencies | `PRD_frontend_creation_proficiencies_v1.md` | `bg1/GUICG7.py`, `LUProfsSelection.py` | placeholder |
| spells_memorize | `PRD_frontend_creation_spells_v1.md` | `LUSpellSelection.py`, `Spellbook.py` | placeholder |
| sound_set | `PRD_frontend_creation_sound_v1.md` | `GUIRECCommon.py` OpenSoundWindow | placeholder |
| portrait | `PRD_frontend_creation_portrait_v1.md` | `GUICG13.py`, `GUIRECCommon.py` portrait select | placeholder |
| name_bio | `PRD_frontend_creation_name_bio_v1.md` | `bg1/GUICG9.py`, `OpenBiographyWindow` | placeholder |
| finalize | `PRD_frontend_creation_finalize_v1.md` | `bg1/GUICG12.py`, `CharGenCommon.finalize` | placeholder |

Each sibling PRD follows the same template and has its own method catalog, AC set, and acceptance test. The parent coordinates them via the state machine.

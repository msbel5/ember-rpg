# PRD: Frontend Creation — Portrait (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft
**Parent:** `PRD_frontend_character_creation_v1.md`

---

## 1. Purpose

Specify the **portrait selection stage**. A gallery of pre-made portraits filtered by gender, navigated via Left/Right arrows, with a large preview in the center. Optional custom portrait import from disk. Writes `CharGenState.portrait_large` + `portrait_small`.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\GUICG13.py` (62 LOC shared portrait picker) + `GUIRECCommon.py` functions `OpenPortraitSelectWindow`, `PortraitLeftPress`, `PortraitRightPress`, `PortraitDonePress`, `OpenCustomPortraitWindow`, `CustomPortraitDonePress`, `LargeCustomPortrait`, `SmallCustomPortrait` (lines 129-296)
- **Godot target:** NEW `godot-client/scripts/ui/creation_step_portrait.gd` + NEW `godot-client/scenes/creation_step_portrait.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Gallery navigation: Prev/Next buttons + Left/Right hotkeys
- Large center preview showing current portrait
- Small preview showing the matching smaller portrait asset
- Gender filter via `CharGenState.gender`
- Custom portrait import file picker (with validation)
- Writes `CharGenState.portrait_large` and `portrait_small`
- State machine hooks

**Out of scope:**
- Portrait generation (AI or otherwise)
- In-game portrait swap (covered by `customize` modal in character_record)
- Animated portraits

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render a large preview image + small preview + Prev/Next buttons + Done + Back + Custom Import.

**FR-02:** `_portrait_list` MUST be loaded from `GameState.creation_catalog.portraits` and filtered by gender.

**FR-03:** `_current_index` starts at 0. Prev decrements (wraps at 0 to end). Next increments (wraps at end to 0).

**FR-04:** Each index change MUST update both preview images via `_load_portrait_textures(slug)`.

**FR-05:** Left/Right arrow keys MUST bind to `portrait_left_press` / `portrait_right_press`.

**FR-06:** Clicking Custom Import opens a file picker (accepts png/jpg). The chosen file MUST be validated (exists, non-zero size, image format). On success, the file is registered as a custom portrait and selected.

**FR-07:** The custom import flow MUST separately set large (210×330) and small (38×60) via two upload prompts or one image with auto-resize.

**FR-08:** Pressing Done writes `CharGenState.portrait_large` and `CharGenState.portrait_small` (slugs), then calls parent `next()`.

**FR-09:** `unset_fn()` clears both portrait fields on back.

**FR-10:** `comment_fn(text_area)` appends "Portrait: <slug>" to overview.

**FR-11:** `guard_fn()` MUST always return true.

## 4. Data Structures

    class_name CreationStepPortrait extends PanelContainer
    
    const LARGE_PORTRAIT_SIZE := Vector2i(210, 330)
    const SMALL_PORTRAIT_SIZE := Vector2i(38, 60)
    
    var _portrait_list: Array = []                 # [{slug, large_path, small_path, gender}]
    var _current_index: int = 0
    var _large_preview: TextureRect
    var _small_preview: TextureRect
    var _prev_button: Button
    var _next_button: Button
    var _done_button: Button
    var _back_button: Button
    var _custom_button: Button
    var _custom_file_dialog: FileDialog
    var _parent_wizard: Object = null

## 5. Public API — methods that MUST exist

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # parent wiring
    func bind_parent_wizard(wizard: Object) -> void
    func open_stage() -> void
    
    # catalog loading
    func load_portrait_catalog() -> void
    func filter_by_gender(gender: int) -> Array
    
    # navigation
    func portrait_left_press() -> void                                           # GemRB: PortraitLeftPress
    func portrait_right_press() -> void                                          # GemRB: PortraitRightPress
    func set_current_index(index: int) -> void
    func get_current_index() -> int
    func get_current_portrait() -> Dictionary
    
    # rendering
    func update_previews_from_index() -> void
    func load_portrait_textures(slug: String) -> Dictionary                      # returns {large: Texture2D, small: Texture2D}
    
    # custom import
    func open_custom_portrait_window() -> void                                   # GemRB: OpenCustomPortraitWindow
    func on_custom_file_selected(path: String) -> void
    func large_custom_portrait(path: String) -> void                             # GemRB: LargeCustomPortrait
    func small_custom_portrait(path: String) -> void                             # GemRB: SmallCustomPortrait
    func custom_portrait_done_press() -> void                                    # GemRB: CustomPortraitDonePress
    func validate_portrait_file(path: String) -> Dictionary                      # {valid: bool, reason: String}
    
    # confirm / back
    func portrait_done_press() -> void                                           # GemRB: PortraitDonePress
    func on_back_pressed() -> void
    
    # state machine hooks
    func set_fn() -> void
    func comment_fn(text_area: RichTextLabel) -> void
    func unset_fn() -> void
    func guard_fn() -> bool
    
    # signals
    signal portrait_changed(slug: String)
    signal custom_portrait_registered(slug: String)
    signal stage_advanced()
    signal stage_back_requested()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `_ready()`, the widget contains at least one `TextureRect` named `LargePreview` and one named `SmallPreview`.

**AC-02 [FR-02]:** With catalog of 10 portraits (5 male, 5 female) and gender=2 (Female), `_portrait_list.size() == 5`.

**AC-03 [FR-03]:** With `_current_index=0`, `portrait_left_press()` wraps to `(_portrait_list.size() - 1)`.

**AC-04 [FR-03]:** With `_current_index == last`, `portrait_right_press()` wraps to 0.

**AC-05 [FR-05]:** Pressing the Left arrow via `_input` calls `portrait_left_press`.

**AC-06 [FR-06]:** `validate_portrait_file("missing.png") == {"valid": false, ...}`.

**AC-07 [FR-07]:** `large_custom_portrait(path)` and `small_custom_portrait(path)` both accept valid image paths and register them in the portrait list.

**AC-08 [FR-08]:** Pressing Done with a selected portrait calls parent `update_state("portrait_large", ...)` and `update_state("portrait_small", ...)`, then `next()`.

**AC-09 [FR-09]:** `unset_fn()` clears both fields.

**AC-10 [FR-10]:** `comment_fn(text_area)` appends "Portrait:" line containing the slug.

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["_ready", "_input", "bind_parent_wizard", "open_stage", "load_portrait_catalog", "filter_by_gender", "portrait_left_press", "portrait_right_press", "set_current_index", "get_current_index", "get_current_portrait", "update_previews_from_index", "load_portrait_textures", "open_custom_portrait_window", "on_custom_file_selected", "large_custom_portrait", "small_custom_portrait", "custom_portrait_done_press", "validate_portrait_file", "portrait_done_press", "on_back_pressed", "set_fn", "comment_fn", "unset_fn", "guard_fn"]`

## 7. Performance Requirements

- `open_stage()` + initial preview load: **< 100ms**
- Navigation (Prev/Next): **< 50ms** per step
- Custom portrait validation: **< 20ms** for a local file

## 8. Error Handling

- Missing portrait texture at slug: render generic placeholder, log once
- Custom file invalid: show toast with reason, keep prior selection
- Empty filtered list: disable Prev/Next, show "No portraits available"
- File dialog cancel: no-op

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/creation_step_portrait.gd` — NEW
- `godot-client/scenes/creation_step_portrait.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_creation_portrait.gd` — NEW

**Backend (consumed, NOT modified):**
- `GameState.creation_catalog.portraits` — read-only

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_creation_portrait.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_creation_portrait.gd

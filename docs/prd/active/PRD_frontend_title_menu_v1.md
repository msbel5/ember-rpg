# PRD: Frontend Title Menu (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Document and complete the title screen — BG1's main menu with New Game, Continue, Load, Options, Quit (and optional Movies, Multi-Player). This is the first surface the player sees. Partially implemented in `godot-client/scenes/title_screen.gd` (~370 LOC). This PRD enumerates the remaining method contract and brings it to the same method-level bar as the rest of the family.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\Start.py` (134 LOC)
- **Godot target:** EXTEND `godot-client/scenes/title_screen.gd` (existing) + `title_screen.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Main menu buttons: New Game, Continue, Load, Options, Quit (BG1 set)
- Backend health panel with Retry button (already wired)
- Creation wizard host + Load browser host (already wired)
- Version label + build info label
- Background art / music
- Keyboard navigation (arrow keys, Enter, Esc)
- Method catalog for the existing implementation

**Out of scope:**
- Movies button (deferred)
- Multi-player (deferred)
- Cinematic intro sequence

## 3. Functional Requirements (FR)

**FR-01:** The title screen MUST render the main menu with the 5 buttons listed above.

**FR-02:** Continue MUST resume the last save OR open the load browser if no last save.

**FR-03:** New Game MUST open the creation wizard AFTER `BackendRuntime.backend_ready == true` AND the creation catalog is loaded.

**FR-04:** Load MUST open the load browser.

**FR-05:** Quit MUST open a quit confirmation modal (see `PRD_frontend_quit_confirm_v1.md`).

**FR-06:** Options MUST open the options panel (see `PRD_frontend_options_menu_v1.md`).

**FR-07:** The backend diagnostics panel MUST display when backend bootstrap fails with a Retry button.

**FR-08:** Version label MUST show the current ember-rpg build version.

**FR-09:** Keyboard: Up/Down arrows move focus between buttons, Enter activates, Esc quits (with confirm).

**FR-10:** F12 captures a screenshot of the title (already implemented — document).

## 4. Data Structures

Existing structure in `title_screen.gd` — this PRD catalogs methods already present plus ones that must be added.

    var _backend_ready: bool = false                # [existing]
    var _backend_blocking_error: bool = false       # [existing]
    var _catalog_loading: bool = false              # [existing]
    var _catalog: Dictionary = {}                   # [existing]
    var _pending_open_creation: bool = false        # [existing]
    
    @onready var title_menu: TitleMenu              # [existing]
    @onready var status_label: Label                # [existing]
    @onready var backend_panel: PanelContainer      # [existing]
    @onready var creation_wizard: CreationWizard    # [existing]
    @onready var load_browser: LoadBrowserWidget    # [existing]

## 5. Public API — methods that MUST exist

Many already exist. New ones marked NEW.

    # ---- lifecycle [existing] ----
    func _ready() -> void
    func _unhandled_input(event: InputEvent) -> void
    
    # ---- menu actions [existing] ----
    func _on_new_game() -> void
    func _on_continue() -> void
    func _on_load_requested() -> void
    func _open_creation() -> void
    func _close_creation() -> void
    func _close_load_browser() -> void
    
    # ---- creation flow callbacks [existing] ----
    func _start_creation_flow(player_name: String, adapter_id: String, profile_id: String, world_seed: int) -> void
    func _on_creation_started(data) -> void
    func _answer_creation_question(question_id: String, answer_id: String) -> void
    func _reroll_creation() -> void
    func _save_creation_roll() -> void
    func _swap_creation_roll() -> void
    func _on_creation_updated(data) -> void
    func _finalize_creation(payload: Dictionary) -> void
    func _on_campaign_created(data) -> void
    
    # ---- load flow callbacks [existing] ----
    func _load_campaign(save_id: String) -> void
    func _on_campaign_loaded(data, save_id: String) -> void
    
    # ---- catalog [existing] ----
    func _request_creation_catalog() -> void
    func _on_creation_catalog_loaded(data) -> void
    
    # ---- backend bootstrap [existing] ----
    func _bind_backend_runtime() -> void
    func _retry_backend_bootstrap() -> void
    func _on_backend_runtime_status(message: String) -> void
    func _on_backend_runtime_finished(success: bool) -> void
    func _on_backend_error(message: String) -> void
    func _requires_backend_bootstrap() -> bool
    
    # ---- menu state [existing] ----
    func _refresh_menu_state() -> void
    
    # ---- NEW methods (must be added) ----
    func open_options_panel() -> void                                            # NEW — route to options
    func open_quit_confirm() -> void                                             # NEW — route to quit modal
    func get_version_text() -> String                                            # NEW — returns build version string
    func set_version_label(text: String) -> void                                 # NEW
    func handle_keyboard_navigation(event: InputEventKey) -> bool                # NEW — up/down/enter
    func focus_first_menu_button() -> void                                       # NEW — called on _ready
    func get_active_dialog() -> Control                                          # NEW — returns creation_wizard, load_browser, or null
    func is_modal_open() -> bool                                                 # NEW — helper for input routing

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The title screen renders 5 named menu buttons (NewGame / Continue / Load / Options / Quit).

**AC-02 [FR-03]:** Clicking New Game while `_backend_ready == false` MUST NOT open the creation wizard. It MUST show a status message.

**AC-03 [FR-03]:** Clicking New Game while `_backend_ready == true` AND catalog is loaded MUST call `_open_creation`.

**AC-04 [FR-02]:** With `ProfileStorage.last_campaign_save_id()` non-empty, Continue calls `_load_campaign(last_id)`.

**AC-05 [FR-02]:** With no last save but a `preferred_resume_player_id`, Continue opens the load browser.

**AC-06 [FR-07]:** On backend bootstrap failure, `backend_panel.visible == true` and the Retry button is enabled.

**AC-07 [FR-08]:** `get_version_text()` returns a non-empty string containing the version.

**AC-08 [FR-09]:** Pressing Down arrow in title menu focus moves focus to the next button. Pressing Enter activates the focused button.

**AC-09 [FR-05]:** Pressing Quit opens a confirm modal (not an immediate quit).

**AC-10 [FR-10]:** Pressing F12 calls `ScreenshotCapture.capture_viewport`.

**AC-11 [reflection]:** Every method listed in §5 MUST exist on the script. The reflection test enumerates all method names and asserts `script.has_method(name) == true`.

## 7. Performance Requirements

- Title screen `_ready` cost: **< 100ms**
- New Game click → creation wizard visible: **< 300ms** (if backend ready + catalog loaded)
- Options modal open: **< 100ms**

## 8. Error Handling

- Backend never becomes ready: show backend diagnostics panel with Retry
- Catalog load fails: show status label "Failed to load creation catalog", keep menu interactive
- Scene change fails: log at ERROR, stay on title

## 9. Integration Points

**Godot (editable):**
- `godot-client/scenes/title_screen.gd` — extend per NEW methods in §5
- `godot-client/scenes/title_screen.tscn` — may add Options button + version label if missing
- `godot-client/tests/automation/godot/test_frontend_title_menu.gd` — NEW

**Backend (consumed, NOT modified):**
- `BackendRuntime` autoload — existing
- `Backend` autoload — existing

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_title_menu.gd` covers AC-01..AC-11
- ≥80% branch coverage on new methods

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_title_menu.gd

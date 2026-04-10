# PRD: Frontend Load UI (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **load game UI** — slot browser with thumbnails, metadata, Load button, Delete, Refresh, player filter. Extends the existing `load_browser_widget.gd`.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\GUILOAD.py` (231 LOC)
- **Godot target:** EXTEND `godot-client/scripts/ui/load_browser_widget.gd` (existing)

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Scrollable slot list with thumbnails + metadata
- Filter by player_id
- Load button with confirmation for current unsaved progress
- Delete with confirmation
- Refresh button
- F9 quickload
- Corrupt save handling (show error, don't crash)

**Out of scope:**
- Save file inspection tools
- Cloud save

## 3. Functional Requirements (FR)

**FR-01:** The widget MUST render a scrollable list of save slots filtered by `_player_filter`.

**FR-02:** Each slot row shows: thumbnail, character name, area, game time, real timestamp, slot name.

**FR-03:** The widget MUST load the slot list via `Backend.list_player_campaign_saves(player_id, callback)`.

**FR-04:** Clicking a slot selects it; Load button becomes enabled.

**FR-05:** Load button issues `Backend.load_campaign(slot_id, callback)`.

**FR-06:** If there is active unsaved progress, Load MUST show a confirmation "Abandon current progress?" Yes/No.

**FR-07:** Delete opens a confirmation; Yes calls `Backend.delete_campaign_save`.

**FR-08:** Refresh re-fetches the slot list.

**FR-09:** F9 in-game triggers `quickload()` loading the "quicksave" slot.

**FR-10:** Corrupted save (backend returns error) MUST show a red "Corrupted save — cannot load" indicator next to the slot, keep the slot visible, and NOT crash.

## 4. Data Structures

    # Extensions to LoadBrowserWidget / load_browser_widget.gd
    
    var _player_filter: String = ""
    var _selected_slot_id: String = ""
    var _slot_rows: Dictionary = {}
    var _load_button: Button
    var _delete_button: Button
    var _refresh_button: Button
    var _player_filter_dropdown: OptionButton
    var _unsaved_progress_modal: AcceptDialog
    var _delete_confirm_modal: AcceptDialog

## 5. Public API — methods that MUST exist

    # ---- lifecycle ----
    func _ready() -> void
    
    # ---- open / close ----
    func open(player_id: String = "") -> void                                    # [existing]
    func close() -> void
    func is_open() -> bool
    
    # ---- slot list ----
    func refresh_slot_list() -> void
    func render_slot_list(slot_list: Array) -> void
    func build_slot_row(slot_data: Dictionary) -> Control
    func format_slot_text(slot_data: Dictionary) -> String
    func load_slot_thumbnail(slot_id: String) -> Texture2D
    func clear_rows() -> void                                                    # [existing: _clear_rows]
    
    # ---- player filter ----
    func set_player_filter(player_id: String) -> void
    func get_player_filter() -> String
    func refresh_player_dropdown() -> void
    
    # ---- selection ----
    func select_slot(slot_id: String) -> void
    func get_selected_slot() -> String
    func clear_selection() -> void
    func refresh_load_button_state() -> void
    
    # ---- load action ----
    func on_load_pressed() -> void
    func check_unsaved_progress() -> bool
    func confirm_abandon_unsaved() -> void
    func on_abandon_confirmed() -> void
    func on_abandon_canceled() -> void
    func execute_load(slot_id: String) -> void
    
    # ---- delete ----
    func on_delete_pressed() -> void
    func confirm_delete_for(slot_id: String) -> void
    func on_delete_confirmed() -> void
    func on_delete_canceled() -> void
    
    # ---- refresh ----
    func on_refresh_pressed() -> void
    
    # ---- quickload ----
    func quickload() -> void
    
    # ---- corrupt save ----
    func mark_slot_corrupted(slot_id: String, reason: String) -> void
    func is_slot_corrupted(slot_id: String) -> bool
    
    # ---- callbacks ----
    func on_slot_list_fetched(data) -> void                                      # [existing: _on_saves_listed]
    func on_load_response(data, slot_id: String) -> void
    func on_delete_response(data, slot_id: String) -> void
    
    # ---- signals ----
    signal save_load_requested(slot_id: String)                                  # [existing]
    signal browser_closed()                                                      # [existing]
    signal delete_save_requested(slot_id: String)
    signal slot_selected(slot_id: String)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `refresh_slot_list()` with 5 cached slots and `_player_filter == ""`, `_slot_rows.size() == 5`.

**AC-02 [FR-03]:** Calling `refresh_slot_list()` calls `Backend.list_player_campaign_saves` exactly once.

**AC-03 [FR-04]:** Clicking a slot via automation bridge calls `select_slot(slot_id)` and sets `_load_button.disabled == false`.

**AC-04 [FR-05]:** Pressing Load with a selected slot and no unsaved progress calls `execute_load(slot_id)` which calls `Backend.load_campaign`.

**AC-05 [FR-06]:** With unsaved progress, pressing Load opens `_unsaved_progress_modal`. Confirming calls `execute_load`. Canceling does NOT load.

**AC-06 [FR-07]:** Delete flow opens `_delete_confirm_modal`; Yes calls `Backend.delete_campaign_save`.

**AC-07 [FR-08]:** Refresh button calls `refresh_slot_list`.

**AC-08 [FR-09]:** `quickload()` calls `execute_load("quicksave")` (or the configured quicksave slot ID).

**AC-09 [FR-10]:** `mark_slot_corrupted("slot_1", "hash mismatch")` sets `is_slot_corrupted("slot_1") == true` and renders a red indicator in the row.

**AC-10 [FR-02]:** `format_slot_text({...})` contains character name, area, and timestamp.

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["_ready", "open", "close", "is_open", "refresh_slot_list", "render_slot_list", "build_slot_row", "format_slot_text", "load_slot_thumbnail", "clear_rows", "set_player_filter", "get_player_filter", "refresh_player_dropdown", "select_slot", "get_selected_slot", "clear_selection", "refresh_load_button_state", "on_load_pressed", "check_unsaved_progress", "confirm_abandon_unsaved", "on_abandon_confirmed", "on_abandon_canceled", "execute_load", "on_delete_pressed", "confirm_delete_for", "on_delete_confirmed", "on_delete_canceled", "on_refresh_pressed", "quickload", "mark_slot_corrupted", "is_slot_corrupted", "on_slot_list_fetched", "on_load_response", "on_delete_response"]`

## 7. Performance Requirements

- `refresh_slot_list()` fetch + render for 20 slots: **< 1s**
- Thumbnail load: **< 30ms** per slot (cached)
- Load round-trip → scene change: **< 3s**

## 8. Error Handling

- Backend fetch failure: show "Failed to load save list" message
- Load response error: show toast, keep browser open, mark slot corrupted if hash error
- Delete of only remaining save: extra confirmation
- Invalid slot_id in selection: clear selection

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/load_browser_widget.gd` — extend per §5
- `godot-client/tests/automation/godot/test_frontend_load_ui.gd` — NEW

**Backend (consumed, NOT modified):**
- `Backend.list_player_campaign_saves`, `Backend.load_campaign`, `Backend.delete_campaign_save`

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_load_ui.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_load_ui.gd

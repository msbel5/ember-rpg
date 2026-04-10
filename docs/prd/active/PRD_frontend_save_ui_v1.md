# PRD: Frontend Save UI (BG1)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **save game UI** — the Save tab of the save/load panel. Lists existing save slots with thumbnails, metadata (character name, area, game time, timestamp), Save button, Overwrite confirmation, New Save slot at top, Delete (with confirm), Rename. Extends the existing `save_load_panel.gd`.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\GUISAVE.py` (320 LOC)
- **Godot target:** EXTEND `godot-client/scripts/ui/save_load_panel.gd` (existing) — add save-specific methods

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Scrollable save slot list
- Per-slot: thumbnail (viewport capture), character name, area name, game time, real timestamp, slot name
- "New Save" pseudo-slot at the top
- Save button (saves to selected slot)
- Overwrite confirmation for non-empty slots
- Rename and Delete buttons (with confirm)
- F5 triggers quicksave to a dedicated quicksave slot

**Out of scope:**
- Cloud save sync
- Save compression / encryption (backend authority)

## 3. Functional Requirements (FR)

**FR-01:** The save tab MUST render a scrollable list of save slots from `GameState.save_slots_cache` (populated via `Backend.list_player_campaign_saves`).

**FR-02:** Each slot row MUST display: thumbnail, character name, area, game time, real timestamp, slot name.

**FR-03:** A "New Save" row MUST appear at the top of the list.

**FR-04:** Clicking "New Save" opens a text input for the slot name, then issues `Backend.save_campaign(campaign_id, callback, slot_name, player_id)`.

**FR-05:** Clicking an existing slot selects it. Save button overwrites it (after confirmation).

**FR-06:** Overwrite confirmation is a Yes/No modal.

**FR-07:** Delete button opens a confirmation; Yes issues `Backend.delete_campaign_save(slot_id, callback)`.

**FR-08:** Rename button opens a text input; saving issues `Backend.rename_campaign_save(slot_id, new_name, callback)` (if endpoint exists; otherwise fallback to save-new + delete-old).

**FR-09:** F5 in-game triggers `quicksave()` which saves to a dedicated "quicksave" slot name.

**FR-10:** Save tab MUST refresh automatically after any save/delete/rename operation via `Backend.list_player_campaign_saves`.

## 4. Data Structures

    # Additions to SaveLoadPanel / save_load_panel.gd
    
    const QUICKSAVE_SLOT_NAME := "quicksave"
    
    var _selected_save_id: String = ""
    var _save_slot_rows: Dictionary = {}
    var _new_save_row: Control
    var _overwrite_confirm_modal: AcceptDialog
    var _delete_confirm_modal: AcceptDialog
    var _rename_input_modal: AcceptDialog

## 5. Public API — methods that MUST exist

Extend `save_load_panel.gd` with:

    # ---- save tab lifecycle ----
    func open_save_tab() -> void
    func refresh_save_slot_list() -> void
    func render_save_slots(slot_list: Array) -> void
    func render_new_save_row() -> void
    
    # ---- save slot rows ----
    func build_save_slot_row(slot_data: Dictionary) -> Control
    func format_save_slot_text(slot_data: Dictionary) -> String
    func load_save_thumbnail(slot_id: String) -> Texture2D
    
    # ---- selection ----
    func select_save_slot(slot_id: String) -> void
    func get_selected_save_slot() -> String
    func clear_save_selection() -> void
    
    # ---- save actions ----
    func on_new_save_pressed() -> void
    func prompt_new_save_name() -> void
    func save_to_slot(slot_name: String) -> void                                 # calls Backend.save_campaign
    func on_save_pressed() -> void                                               # overwrite flow
    func confirm_overwrite_for(slot_id: String) -> void
    func on_overwrite_confirmed() -> void
    func on_overwrite_canceled() -> void
    
    # ---- delete ----
    func on_delete_pressed() -> void
    func confirm_delete_for(slot_id: String) -> void
    func on_delete_confirmed() -> void
    func on_delete_canceled() -> void
    
    # ---- rename ----
    func on_rename_pressed() -> void
    func prompt_rename_for(slot_id: String) -> void
    func apply_rename(slot_id: String, new_name: String) -> void
    
    # ---- quicksave ----
    func quicksave() -> void
    func on_quick_save_requested() -> void                                       # [existing in session_save_sync]
    
    # ---- callbacks ----
    func on_save_completed(data, slot_name: String) -> void
    func on_delete_completed(data, slot_id: String) -> void
    func on_rename_completed(data, slot_id: String) -> void
    func on_save_list_refreshed(data) -> void
    
    # ---- signals ----
    signal save_requested(slot_name: String)
    signal delete_save_requested(slot_id: String)
    signal rename_save_requested(slot_id: String, new_name: String)
    signal save_slot_selected(slot_id: String)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** After `open_save_tab()` with 3 cached slots, `_save_slot_rows.size() == 3` AND the New Save row is present.

**AC-02 [FR-03]:** The New Save row has a distinguishable label like "— New Save —" or a plus icon.

**AC-03 [FR-04]:** Clicking New Save calls `prompt_new_save_name()` which opens a text input modal.

**AC-04 [FR-05]:** Clicking an existing slot sets `_selected_save_id` to its slot ID.

**AC-05 [FR-06]:** Pressing Save with a selected existing slot opens `_overwrite_confirm_modal`.

**AC-06 [FR-07]:** Pressing Delete opens `_delete_confirm_modal`. Confirming calls `Backend.delete_campaign_save`.

**AC-07 [FR-09]:** Calling `quicksave()` issues `Backend.save_campaign(campaign_id, _, "quicksave", player_id)`.

**AC-08 [FR-10]:** After `on_save_completed`, the slot list is refreshed (verified by spying on `refresh_save_slot_list`).

**AC-09 [FR-02]:** `format_save_slot_text({...})` returns a string containing character name, area, and timestamp.

**AC-10 [FR-08]:** `apply_rename("camp_1", "new_name")` issues the rename backend call (or fallback save+delete).

**AC-11 [reflection]:** Every method in §5 MUST exist:
`["open_save_tab", "refresh_save_slot_list", "render_save_slots", "render_new_save_row", "build_save_slot_row", "format_save_slot_text", "load_save_thumbnail", "select_save_slot", "get_selected_save_slot", "clear_save_selection", "on_new_save_pressed", "prompt_new_save_name", "save_to_slot", "on_save_pressed", "confirm_overwrite_for", "on_overwrite_confirmed", "on_overwrite_canceled", "on_delete_pressed", "confirm_delete_for", "on_delete_confirmed", "on_delete_canceled", "on_rename_pressed", "prompt_rename_for", "apply_rename", "quicksave", "on_quick_save_requested", "on_save_completed", "on_delete_completed", "on_rename_completed", "on_save_list_refreshed"]`

## 7. Performance Requirements

- `refresh_save_slot_list()` with 20 slots: **< 100ms**
- Thumbnail load per slot: **< 30ms** (cached)
- Save round-trip → list refresh: **< 2s**

## 8. Error Handling

- Backend save error: show toast, keep panel open
- Thumbnail missing: render placeholder
- Invalid slot name (empty, duplicate): prevent save, show validation message
- Delete of quicksave slot: require extra confirmation

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/save_load_panel.gd` — extend per §5
- `godot-client/scripts/ui/session_save_sync.gd` — existing, already wires `on_quick_save_requested`
- `godot-client/tests/automation/godot/test_frontend_save_ui.gd` — NEW

**Backend (consumed, NOT modified):**
- `Backend.save_campaign`, `Backend.list_player_campaign_saves`, `Backend.delete_campaign_save`, (optional) `Backend.rename_campaign_save`

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints (rename is optional fallback)
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_save_ui.gd` covers AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_save_ui.gd

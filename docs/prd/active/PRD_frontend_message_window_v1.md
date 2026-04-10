# PRD: Frontend Message Window — BG1 Scrolling Log + Dialog Surface
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the BG1 message window — a scrolling text log at the bottom of the screen that shows combat messages, dialog text, system notifications, and (in dialog mode) the current NPC's speech plus player response options. In BG1 it has three size states (small/medium/large) with PGUP / PGDN hotkeys to expand/contract, and it auto-expands to large during dialog.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\MessageWindow.py` (255 LOC — `OnLoad`, `MWinBG`, `ToggleWindowMinimize`, `SetMWSize`, `UpdateControlStatus`, hotkey wiring), `GUIWORLD.py` (dialog open/close helpers), and shared `TextArea` widget in `core/GUI/TextArea.{h,cpp}` for scrolling text behavior
- **Godot targets:**
  - Primary: `godot-client/scripts/ui/narrative_panel.gd` (existing scrolling log — extend)
  - Dialog overlay: `godot-client/scripts/ui/dialog_overlay.gd` (already exists, already refactored — wire to message window size transitions)
  - State helper: `godot-client/scripts/ui/dialog_overlay_state.gd` (recently refactored)

**Clean-room rule:** Read MessageWindow.py function-by-function to understand the size state machine and dialog auto-expand. Do NOT translate code.

## 2. Scope

**In scope:**
- Three size states: `GS_SMALLDIALOG` (compact log), `GS_MEDIUMDIALOG` (default), `GS_LARGEDIALOG` (expanded for dialog / reading)
- PGUP key → expand to next size; PGDN key → contract to previous size
- Auto-expand to LARGE when `DF_IN_DIALOG` flag is set; auto-restore to previous size when dialog ends
- Scrolling text log with color coding (red = combat hit, white = default, yellow = system, blue = dialog, green = loot)
- Dialog mode: NPC speech at top, player response options as numbered clickable list at bottom
- Continue button at bottom-right for dialog progression (hotkey: Enter or Space)
- Keep-alive at max size during dialog even if player presses PGDN (cannot contract during dialog)
- Log history buffer: keep last N=500 entries, scrollable backward

**Out of scope:**
- Dialog tree traversal logic (handled by backend + dialog_overlay_state)
- NPC voice audio (Phase 3 if ever)
- Custom fonts (use ember theme defaults)
- Rich-text inline icons (Phase 3)

## 3. Functional Requirements (FR)

**FR-01:** The message window MUST support three discrete size states with stable numeric constants `GS_SMALLDIALOG`, `GS_MEDIUMDIALOG`, `GS_LARGEDIALOG` (match GemRB values exactly so save-state survives round-trip).

**FR-02:** Pressing `PgUp` MUST call `on_increase_size()` which cycles `small → medium → large`. Pressing `PgDn` MUST call `on_decrease_size()` which cycles `large → medium → small`.

**FR-03:** When the exploration view emits `dialog_state_entered` (via `dialogue_flags & DF_IN_DIALOG`), the message window MUST: (a) store the current size in `_mta_restore_size`, (b) expand to `GS_LARGEDIALOG`, (c) disable the Contract button.

**FR-04:** When dialog ends (`dialog_state_exited`), the message window MUST restore to `_mta_restore_size` and re-enable Contract.

**FR-05:** The message window MUST expose an `append_text(text: String, color: Color = Color.WHITE)` method that adds a line to the scrolling log. Text MUST auto-scroll to the bottom by default.

**FR-06:** The log buffer MUST keep the last 500 entries (configurable via `LOG_HISTORY_SIZE` constant). Entries older than 500 MUST be trimmed.

**FR-07:** In dialog mode, the widget MUST render NPC speech at top and a numbered list of player options at bottom. Clicking an option (or pressing its number key `1..9`) MUST emit `dialog_option_selected(option_index: int)`.

**FR-08:** The Continue button MUST be present at bottom-right. Pressing Enter or Space while dialog is active MUST trigger it. Clicking it MUST emit `dialog_continue_requested()`.

**FR-09:** Scrollback MUST work via mouse wheel over the log area AND PageUp/PageDown when not in dialog.

**FR-10:** The widget MUST emit `size_changed(new_size: int)` whenever the size state transitions, so other UI elements (e.g. action bar, portrait strip) can reflow.

**FR-11:** Log entries MUST be categorizable via a tag parameter: `append_text(text, tag)` where tag is one of `"system"`, `"combat"`, `"dialog"`, `"loot"`, `"quest"`, `"chat"`. Tags determine color and persistence in save.

**FR-12:** On game save, the last 100 log entries MUST be serialized into the save file. On load, they MUST be restored into the buffer and displayed.

## 4. Data Structures

    class_name MessageWindowWidget extends PanelContainer
    
    const GS_SMALLDIALOG := 0
    const GS_MEDIUMDIALOG := 2
    const GS_LARGEDIALOG := 6
    # (values match GemRB's GUIDefines.py; do not change without migration)
    
    const LOG_HISTORY_SIZE := 500
    const LOG_HISTORY_SAVED_SIZE := 100
    
    const TAG_COLORS := {
        "system": Color.YELLOW,
        "combat": Color(1.00, 0.45, 0.45),
        "dialog": Color(0.65, 0.80, 1.00),
        "loot":   Color(0.55, 1.00, 0.55),
        "quest":  Color(1.00, 0.85, 0.55),
        "chat":   Color.WHITE,
    }
    
    var _current_size: int = GS_MEDIUMDIALOG
    var _mta_restore_size: int = GS_MEDIUMDIALOG              # size to restore after dialog
    var _in_dialog: bool = false
    var _log_entries: Array[Dictionary] = []                  # [{text, tag, timestamp}]
    var _dialog_npc_name: String = ""
    var _dialog_text: String = ""
    var _dialog_options: Array = []                           # [{text, id, enabled}]
    var _expand_button: Button
    var _contract_button: Button
    var _continue_button: Button
    var _scroll_container: ScrollContainer
    var _text_area: RichTextLabel

## 5. Public API — methods that MUST exist

    # ---- lifecycle ----
    func _ready() -> void
    func _input(event: InputEvent) -> void                                       # PGUP/PGDN + Enter/Space in dialog
    
    # ---- size state ----
    func set_window_size(new_size: int) -> void                                  # SetMWSize equivalent
    func get_window_size() -> int
    func on_increase_size() -> void                                              # PGUP handler
    func on_decrease_size() -> void                                              # PGDN handler
    func m_win_bg(size: int) -> String                                           # resolves bg resref per size (returns asset slug)
    func update_control_status(init: bool = false) -> void                       # wires expand/contract buttons; called at startup and after size changes
    signal size_changed(new_size: int)
    
    # ---- dialog mode ----
    func enter_dialog_mode(npc_name: String, speech: String, options: Array) -> void
    func exit_dialog_mode() -> void
    func is_in_dialog() -> bool
    func update_dialog_speech(speech: String) -> void                            # mid-dialog text swap
    func update_dialog_options(options: Array) -> void                           # mid-dialog option swap
    signal dialog_option_selected(option_index: int)
    signal dialog_continue_requested()
    
    # ---- log append ----
    func append_text(text: String, tag: String = "chat") -> void
    func append_system_text(text: String) -> void                                # shorthand: tag="system"
    func append_combat_text(text: String) -> void
    func append_loot_text(text: String) -> void
    func append_quest_text(text: String) -> void
    func clear_log() -> void
    
    # ---- log buffer / save ----
    func get_log_entries() -> Array[Dictionary]
    func load_history(entries: Array) -> void                                    # restore from save
    func serialize_for_save() -> Array                                           # last 100 entries
    
    # ---- minimize / restore ----
    func toggle_window_minimize(gs_flag: int = 0) -> void                        # collapses to a 5-pixel strip
    func toggle_actionbar_clock(show: bool) -> void                              # cross-widget helper: the action bar's clock visibility is linked
    
    # ---- scroll ----
    func scroll_to_bottom() -> void
    func scroll_to_top() -> void
    func set_auto_scroll(enabled: bool) -> void
    
    # ---- thinking indicator (when backend is processing a command) ----
    func show_thinking_indicator() -> void
    func hide_thinking_indicator() -> void

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The three size constants exist with values `GS_SMALLDIALOG=0`, `GS_MEDIUMDIALOG=2`, `GS_LARGEDIALOG=6`. Verified by literal assertion.

**AC-02 [FR-02]:** Starting in `GS_MEDIUMDIALOG`, pressing PGUP once transitions to `GS_LARGEDIALOG` and emits `size_changed(6)`. Pressing PGDN twice transitions back through `GS_MEDIUMDIALOG` to `GS_SMALLDIALOG` and emits `size_changed` twice.

**AC-03 [FR-03, FR-04]:** Calling `enter_dialog_mode("Khalid", "Greetings...", [{text: "Hi", id: 1}])` MUST: (a) store current size in `_mta_restore_size`, (b) set `_current_size = GS_LARGEDIALOG`, (c) disable `_contract_button`, (d) show the NPC name + speech + options. Calling `exit_dialog_mode()` MUST restore `_current_size = _mta_restore_size` and re-enable the contract button.

**AC-04 [FR-05, FR-06]:** Calling `append_text("test line")` 600 times MUST result in exactly 500 entries in `_log_entries` (oldest 100 trimmed).

**AC-05 [FR-07]:** In dialog mode with 3 options, clicking option 2 (via automation bridge) MUST emit `dialog_option_selected(1)` (0-indexed).

**AC-06 [FR-08]:** In dialog mode, pressing Enter (via automation bridge) MUST emit `dialog_continue_requested()` exactly once.

**AC-07 [FR-10]:** Any size transition MUST emit `size_changed` exactly once per transition.

**AC-08 [FR-11]:** Calling `append_combat_text("hit for 5")` MUST append an entry with `tag == "combat"` and apply `TAG_COLORS["combat"]` when rendered.

**AC-09 [FR-12]:** Calling `serialize_for_save()` MUST return exactly 100 entries if the log has ≥100 entries, or all entries if fewer. Calling `load_history(entries)` MUST replace `_log_entries` and re-render.

**AC-10 [public API existence]:** Every method in §5 exists on the script. Reflection test.

## 7. Performance Requirements

- `append_text()` call: **< 1ms** (amortized)
- Log trimming when buffer is full: **< 2ms** per trim
- Dialog mode transition (enter / exit): **< 50ms** total including size change + option render
- Scroll-to-bottom on large log: **< 16ms** (one frame)

## 8. Error Handling

- `set_window_size` with invalid value: clamp to nearest valid size, log at WARNING
- `enter_dialog_mode` called while already in dialog: log at WARNING, replace speech/options without changing `_mta_restore_size`
- `exit_dialog_mode` called while not in dialog: no-op, log at DEBUG
- `append_text` with empty string: no-op
- `load_history` with malformed entries: skip bad entries, log at WARNING, continue

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/narrative_panel.gd` — extend with §5 methods, OR create a new `message_window.gd` that narrative_panel delegates to
- `godot-client/scripts/ui/dialog_overlay.gd` — wire `enter_dialog_mode` / `exit_dialog_mode` integration with the existing dialog overlay
- `godot-client/scripts/ui/dialog_overlay_state.gd` — already refactored out; owns dialog state
- `godot-client/scripts/ui/session_shell_sync.gd` — `append_narrative_system_text` already exists; should delegate to `append_system_text`
- `godot-client/tests/automation/godot/test_frontend_message_window.gd` — NEW

**Backend (consumed, NOT modified):**
- `GameState.current_dialog_payload()` — existing helper, provides NPC name + speech + options
- `/game/campaigns/{id}/command` — dialog choices are issued as `dialog <option_id>`
- Save schema v4 — narrative history already has a slot for serialized log; extend if missing

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No GemRB code port

## 10. Test Coverage Target

- `test_frontend_message_window.gd` MUST cover AC-01..AC-10
- ≥80% branch coverage on the extended script
- `run_headless_tests.gd` stays green

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_message_window.gd

## 12. Implementation notes

- Use `RichTextLabel` with BBCode for inline color coding (`[color=...]...[/color]`).
- The size constants `0, 2, 6` come from GemRB's bitfield layout — treat as opaque numbers, not as continuous integers. The transition logic uses `(expand + 1) * 2` and `expand / 2 - 1` which is GemRB's encoding; for Godot, simpler is a direct state machine between {SMALL, MEDIUM, LARGE}.
- For save/load compat, serialize the log entries as JSON in the save's narrative history slot.
- The "thinking indicator" is already implemented in the current `narrative_panel.gd` via `show_thinking_indicator()` — preserve that API.
- Dialog option numeric hotkeys (1..9) should be handled in `_input()` not `_unhandled_input()` to take priority over world input while dialog is active.

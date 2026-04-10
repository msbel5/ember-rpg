# PRD: Frontend Ask About — F1-style Topic Probe Modal (Ember-Specific)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **Ask About** modal — ember-rpg's Fallout-1-inspired topic probe system. Unlike BG1's linear dialog trees, the player can open a modal during conversation, browse all deterministic topics the current NPC knows something about, select one, and receive a grounded response from the backend knowledge system. This is one of the three features that differentiate ember-rpg from a pure BG1 clone (the other two being **Think** and **Ask DM**). The backend already supports this via `conversation_state.ask_about_topic_ids` and the structured action shortcut `dialog_ask_about`. The Godot client already has `topic_probe_modal.gd` as a scaffold.

### Reference sources
- **Ember-specific (no GemRB equivalent):** Fallout 1 / Fallout 2 keyword-based dialog is the design inspiration. In F1 the player picked from a list of "known words" to query the NPC. Ember does this via live backend-provided topic IDs so no LLM invention is possible.
- **Ember backend:** `conversation_state.ask_about_topic_ids` — populated by the backend's knowledge system during active dialog. Each topic is `{topic_id, label, subtitle, category, gating}`.
- **Ember client existing code:**
  - `godot-client/scripts/ui/topic_probe_modal.gd` (existing `TopicProbeModal` class, see methods `set_topics`, `show_modal`, `hide_modal`, `_select_topic`, `_confirm_selection`)
  - `godot-client/scripts/ui/dialog_overlay.gd` (dialog host that embeds ask-about as a sub-action)
- **Backend command:** structured action `dialog_ask_about` with args `{topic_id}`, or flat command string `ask_about <topic_id>`

**No clean-room rule applies** — this is a native ember-rpg feature with no GemRB source to read. Reference-only: Fallout 1 UI screenshots and the existing `topic_probe_modal.gd`.

## 2. Scope

**In scope:**
- Modal overlay that lists all deterministic topics from `GameState.conversation_state.ask_about_topic_ids`
- Topic selection via keyboard (↑↓ + Enter) or mouse click
- Confirm button emits the structured action to the backend
- Close button + ESC key closes the modal without committing
- Auto-populate when dialog starts; clear when dialog ends
- Topic gating: topics marked `gated` or `unknown` are listed but disabled with a reason tooltip
- Integration with the existing `think_panel` — when a topic is selected there, the ask_about modal can be opened with that topic pre-highlighted

**Out of scope:**
- Generating new topics (backend's knowledge system authority; see `knowledge.py`)
- Topic discovery progression (also backend)
- Free-text prompt (that's what `ask_dm` is for)
- Dialog tree branching

## 3. Functional Requirements (FR)

**FR-01:** The Ask About modal MUST open via: (a) the "Ask About" button in `dialog_overlay.gd`, (b) the F4 hotkey when dialog is active, (c) a structured-action hook from `think_panel`.

**FR-02:** On open, the modal MUST populate its topic list from `GameState.conversation_state.ask_about_topic_ids`. If the list is empty, render a single disabled row: "No deterministic ask-about topics are currently available."

**FR-03:** Each topic row MUST display: `label` (primary text), `subtitle` (secondary text), `category` (icon/badge). If a topic has `gating != ""`, the row MUST be disabled and its tooltip MUST show the gating reason.

**FR-04:** Clicking a topic row MUST select it (highlighted). Pressing Enter MUST confirm the selection. Double-clicking MUST confirm in one click.

**FR-05:** Confirming a selection MUST emit `structured_action_requested("dialog_ask_about", {"topic_id": selected_id}, "ask about <label>")`. The modal MUST then close.

**FR-06:** Pressing Escape MUST close the modal without committing. The modal's parent dialog overlay remains active.

**FR-07:** The modal MUST respond to `GameState.conversation_state` changes: when the dialog ends (`ask_about_topic_ids` becomes empty or `has_active_dialog() == false`), the modal MUST auto-close.

**FR-08:** Keyboard navigation: ↑ and ↓ move the selection, Home/End jump to first/last, PageUp/PageDown scroll by 10, Enter confirms, Esc closes.

**FR-09:** The modal MUST NOT block other keyboard shortcuts from the dialog overlay (e.g. number keys 1..9 still select dialog options while the Ask About modal is closed).

**FR-10:** The modal MUST be centered on the viewport with a minimum size of 640×360 and allow the player to resize it via corner drag (optional, nice-to-have).

## 4. Data Structures

Topic entry shape (from backend):

    {
        "topic_id": "barrow_king_rumor",
        "label": "The Barrow King",
        "subtitle": "A rumor you heard from the tavernkeep",
        "category": "rumor",                 # rumor | fact | quest | lore | gossip
        "gating": "",                        # "" if available, else reason e.g. "Requires Lore 40"
        "priority": 50                       # display order
    }

`GameState.conversation_state.ask_about_topic_ids` is the authoritative source. The list arrives pre-sorted by priority from the backend.

Widget state:

    class_name TopicProbeModal extends PanelContainer
    
    var _topic_entries: Array = []           # list of topic dicts
    var _selected_topic_id: String = ""
    var _pre_selected_topic_id: String = ""  # set from think_panel pre-navigation

## 5. Public API — methods that MUST exist

Extend the existing `topic_probe_modal.gd` with these methods (some already exist; mark them [existing]):

    # ---- existing (verified in topic_probe_modal.gd) ----
    func _ready() -> void                                                        # [existing]
    func set_topics(entries: Array, selected_topic_id: String = "") -> void      # [existing]
    func show_modal() -> void                                                    # [existing]
    func hide_modal() -> void                                                    # [existing]
    func _select_topic(topic_id: String) -> void                                 # [existing, private]
    func _refresh() -> void                                                      # [existing, private]
    
    # ---- NEW (must be added) ----
    func open_for_current_dialog() -> void                                       # reads GameState, populates from conversation_state
    func set_pre_selected_topic(topic_id: String) -> void                        # called by think_panel before opening
    func handle_keyboard_navigation(event: InputEventKey) -> bool                # ↑↓/Home/End/PgUp/PgDn/Enter/Esc
    func is_topic_gated(topic_entry: Dictionary) -> bool
    func get_topic_gating_reason(topic_entry: Dictionary) -> String
    func emit_structured_action() -> void                                        # builds and emits the dialog_ask_about action
    func close_and_restore_focus() -> void                                       # closes modal, returns focus to dialog overlay
    
    # ---- signals ----
    signal close_requested()                                                     # [existing]
    signal topic_submitted(topic_id: String)                                     # [existing]
    signal structured_action_requested(shortcut: String, args: Dictionary, history_text: String)  # [existing]
    signal command_requested(command_text: String)                               # [existing]
    signal topic_selected_changed(topic_id: String)                              # NEW — fires when selection changes (not confirms)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-02]:** Given `GameState.conversation_state.ask_about_topic_ids` has 3 entries, calling `open_for_current_dialog()` MUST result in exactly 3 topic rows rendered. Verified by counting `topic_list` children.

**AC-02 [FR-02]:** Given an empty `ask_about_topic_ids`, `open_for_current_dialog()` MUST render exactly one disabled label saying "No deterministic ask-about topics are currently available."

**AC-03 [FR-03]:** Given a topic with `gating = "Requires Lore 40"`, the corresponding row MUST be disabled and `is_topic_gated(entry) == true` and `get_topic_gating_reason(entry) == "Requires Lore 40"`.

**AC-04 [FR-04]:** Clicking a topic row (via automation bridge) MUST emit `topic_selected_changed(topic_id)`. Pressing Enter while a topic is selected MUST emit `structured_action_requested("dialog_ask_about", {"topic_id": ...}, "ask about <label>")` and then `close_requested()`.

**AC-05 [FR-06]:** Pressing Escape MUST hide the modal and NOT emit a `structured_action_requested`. Verified by spying on the signal.

**AC-06 [FR-07]:** Setting `GameState.conversation_state.ask_about_topic_ids = []` and emitting `dialog_state_changed` MUST auto-close the modal within 1 frame.

**AC-07 [FR-08]:** Calling `handle_keyboard_navigation(KEY_DOWN)` with 5 topics and the first selected MUST transition to the second; calling it with the last selected MUST wrap to the first (or stay; implementation chooses, but MUST NOT crash).

**AC-08 [FR-01]:** The F4 hotkey (when dialog is active) MUST trigger `open_for_current_dialog()`. Verified by automation bridge key press.

**AC-09 [pre-selection]:** Calling `set_pre_selected_topic("barrow_king_rumor")` before `show_modal()` MUST result in that topic being the initially selected row.

**AC-10 [reflection]:** Every method in §5 MUST exist on `topic_probe_modal.gd`. Enumerated reflection test.

## 7. Performance Requirements

- `set_topics()` with 50 entries: **< 10ms** rendering
- Keyboard navigation latency: **< 16ms** per key press
- Modal open/close transition: **< 100ms** total

## 8. Error Handling

- Malformed topic entry (missing `topic_id`): skip, log at DEBUG
- Backend returns topic list with duplicates: dedupe by `topic_id`, log at DEBUG if dedup count > 0
- `emit_structured_action` with no selection: no-op, log at DEBUG, keep modal open
- Modal opened while `has_active_dialog() == false`: refuse to open, log at WARNING

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/topic_probe_modal.gd` — extend with new methods (respect the "existing" ones marked in §5)
- `godot-client/scripts/ui/dialog_overlay.gd` — add an "Ask About" button + F4 hotkey that calls `topic_probe_modal.open_for_current_dialog()`
- `godot-client/scripts/ui/think_panel.gd` — when a topic is chosen there, optionally open the ask_about modal with pre-selection
- `godot-client/tests/automation/godot/test_frontend_ask_about.gd` — NEW acceptance test

**Backend (consumed, NOT modified):**
- `GameState.conversation_state.ask_about_topic_ids` — read-only
- `GameState.has_active_dialog()` — gate
- Structured action endpoint with shortcut `dialog_ask_about` — existing

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No free-text input (that's `ask_dm`'s job)
- No offline topic generation — only list what the backend provides

## 10. Test Coverage Target

- `test_frontend_ask_about.gd` MUST cover AC-01..AC-10
- ≥85% branch coverage on `topic_probe_modal.gd`
- Existing headless tests stay green

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_ask_about.gd

## 12. Implementation notes

- The existing `topic_probe_modal.gd` is a solid scaffold. Focus on wiring it properly: open trigger, keyboard nav, pre-selection, auto-close on dialog end.
- F1-style keyword grids (rather than list) are a nice-to-have; start with the list, optimize later.
- The modal should live as a child of the dialog overlay, not the root — ESC handling will work naturally then.
- Keep the "rumor vs fact vs quest" category visible via small badges or icons for UX clarity.

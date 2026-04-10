# PRD: Frontend Ask DM — Fate Consultation Panel (Ember-Specific)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **Ask DM** panel — ember-rpg's "ask the virtual dungeon master" surface. When the player is stuck, wants a hint, or wants to know their options, they open this panel, type a free-form question, and receive a grounded response from the backend's `advisor_view` system. Unlike dialog or knowledge lookups, Ask DM works *outside* conversation — you can ask even when standing in an empty field. The backend response is strictly grounded in the current campaign state (no LLM invention); if the backend cannot answer, it returns blockers explaining what's missing. One of the three ember-specific features. The Godot client already has `ask_dm_panel.gd` as a scaffold (~90 LOC).

### Reference sources
- **Ember-specific (no GemRB equivalent).** Design reference: TTRPG "ask the DM" pattern.
- **Ember backend:** advisor_view system (see `frp-backend/engine/world/advisor.py` ~596 LOC). Ships `advisor_view` in `/state` with shape `{answer_lines, blockers, related_topic_ids, suggested_commands, fate_reading}`.
- **Ember client existing code:** `godot-client/scripts/ui/ask_dm_panel.gd` (existing `AskDmPanelWidget` class, has `set_waiting`, `set_view`, `set_prompt`, `_submit_query`; also emits `structured_action_requested("advisor", {"action_id": "ask_dm", "query": query})`).

## 2. Scope

**In scope:**
- Free-text prompt input where the player types any question
- Submit via button or Enter key
- Rendering of `advisor_view.answer_lines` as multi-line response text
- Rendering of `advisor_view.blockers` as a prominent "Blockers: ..." label
- Rendering of `advisor_view.related_topic_ids` as clickable chips (opens ask_about or think on click)
- Rendering of `advisor_view.suggested_commands` as clickable command buttons that emit to the exploration command line
- Busy/waiting state while the backend is processing
- Clear distinction between "grounded answer" and "no answer available"

**Out of scope:**
- Backend advisor logic (handled by `advisor.py`)
- Free invention of answers (backend responsibility; if backend returns no lines, UI shows "No grounded answer lines returned")
- Chat history / previous answers (Phase 3 feature; this PRD is single-turn)
- Voice input

## 3. Functional Requirements (FR)

**FR-01:** The Ask DM panel MUST render: summary label at top, prompt input with Submit button, blockers label, answer text area, related topics section, suggested commands section.

**FR-02:** The Submit button MUST be labeled "Consult Fate". Pressing Enter in the prompt input or clicking Submit MUST trigger `_submit_query()`.

**FR-03:** `_submit_query()` MUST emit `structured_action_requested("advisor", {"action_id": "ask_dm", "query": <trimmed text>}, "ask dm <query>")` IF any listener is connected. If no listener, it MUST fall back to `command_requested.emit("ask dm <query>")`.

**FR-04:** While waiting for a backend response, the widget MUST show `_waiting = true`: disable the Submit button and the prompt input. The setter `set_waiting(waiting: bool)` exposes this.

**FR-05:** When `set_view(view)` is called with a populated `advisor_view`, the widget MUST render: `answer_lines` joined by newlines, `blockers` as "Blockers: ..." label, `related_topic_ids` as Label chips, `suggested_commands` as Buttons that emit `command_requested` when pressed.

**FR-06:** If `advisor_view` is empty, the answer text MUST display "No fate reading yet. Submit a grounded question."

**FR-07:** If `answer_lines` is empty AND `blockers` is non-empty, the answer text MUST display "No grounded answer lines returned." and the blockers label MUST be visible.

**FR-08:** Clicking a related topic chip MUST emit `related_topic_clicked(topic_id: String)` which other widgets (think panel, ask about modal) can subscribe to.

**FR-09:** Clicking a suggested command button MUST emit `command_requested(command_text: String)` with the exact string from the suggestion.

**FR-10:** The panel MUST sync on `GameState.advisor_view_updated` signal (add if missing) and on `GameState.state_updated`.

## 4. Data Structures

`advisor_view` shape (backend-provided):

    {
        "answer_lines": [
            "Your party is currently short on healing supplies.",
            "Consider visiting the temple in Candlekeep before heading east."
        ],
        "blockers": [],
        "related_topic_ids": ["candlekeep_temple", "healing_potions"],
        "suggested_commands": [
            "travel candlekeep",
            "examine inventory"
        ],
        "fate_reading": {
            "mood": "cautious",
            "dice_hints": []
        }
    }

Widget state:

    class_name AskDmPanelWidget extends PanelContainer
    
    var _view: Dictionary = {}
    var _waiting: bool = false

## 5. Public API — methods that MUST exist

Extend `ask_dm_panel.gd` (several methods already exist; marked [existing]):

    # ---- existing ----
    func _ready() -> void                                                        # [existing]
    func set_waiting(waiting: bool) -> void                                      # [existing]
    func set_view(view: Dictionary) -> void                                      # [existing]
    func set_prompt(prompt: String) -> void                                      # [existing]
    func _render() -> void                                                       # [existing, private]
    func _submit_query() -> void                                                 # [existing, private]
    
    # ---- NEW (must be added) ----
    func refresh_from_game_state() -> void
    func handle_related_topic_click(topic_id: String) -> void
    func handle_suggested_command_click(command_text: String) -> void
    func build_answer_text(answer_lines: Array) -> String
    func build_blockers_text(blockers: Array) -> String
    func is_empty_view() -> bool
    func clear_prompt() -> void
    func get_current_query() -> String
    func is_submitting() -> bool
    
    # ---- signals ----
    signal structured_action_requested(shortcut: String, args: Dictionary, history_text: String)  # [existing]
    signal command_requested(command_text: String)                               # [existing]
    signal related_topic_clicked(topic_id: String)                               # NEW
    signal advisor_query_submitted(query: String)                                # NEW — for telemetry / logging

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The panel has exactly these named nodes present: `SummaryLabel`, `PromptInput`, `SubmitButton`, `BlockersLabel`, `AnswerText`, `TopicSection`, `CommandSection`. Verified by automation bridge.

**AC-02 [FR-02]:** The Submit button's text is exactly "Consult Fate" on `_ready()`.

**AC-03 [FR-03]:** With at least one listener connected to `structured_action_requested`, typing "where to next" and pressing Enter MUST emit `structured_action_requested("advisor", {"action_id": "ask_dm", "query": "where to next"}, "ask dm where to next")` exactly once AND MUST NOT emit `command_requested`.

**AC-04 [FR-03 fallback]:** With NO listener on `structured_action_requested`, submitting MUST emit `command_requested("ask dm where to next")` exactly once.

**AC-05 [FR-04]:** Calling `set_waiting(true)` MUST disable both the Submit button and the prompt input. `set_waiting(false)` MUST re-enable them.

**AC-06 [FR-05]:** Given a view with `answer_lines = ["A"], blockers = ["B"], related_topic_ids = ["t1"], suggested_commands = ["move north"]`, the rendering MUST include: "A" in `answer_text`, "Blockers: B" in `blockers_label`, a chip for "t1" in the topic list, and a button for "move north" in the command list.

**AC-07 [FR-06]:** With `_view = {}`, `answer_text.text == "No fate reading yet. Submit a grounded question."`.

**AC-08 [FR-08]:** Clicking a related-topic chip MUST emit `related_topic_clicked(topic_id)`.

**AC-09 [FR-09]:** Clicking a suggested command button MUST emit `command_requested(command_text)` with the exact string (no prefix, no modification).

**AC-10 [reflection]:** Every method in §5 MUST exist on the script.

## 7. Performance Requirements

- `_render()` end-to-end: **< 10ms** for a typical response (5 answer lines + 3 topics + 3 commands)
- Submit button → `structured_action_requested` emission: **< 5ms**
- Waiting-state toggle: **< 2ms**

## 8. Error Handling

- Empty query on submit: no-op, keep panel open, log at DEBUG
- `_view` with non-Array `answer_lines`: treat as empty, log at DEBUG
- Backend response with malformed shape: render a fallback "No response format" message
- Submit while `_waiting == true`: no-op
- `set_view` called with non-Dictionary: keep previous view, log at WARNING

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/ask_dm_panel.gd` — extend per §5
- `godot-client/autoloads/game_state.gd` — add `advisor_view` Dictionary (if missing) + `advisor_view_updated` signal
- `godot-client/tests/automation/godot/test_frontend_ask_dm.gd` — NEW

**Backend (consumed, NOT modified):**
- `/state` response MUST include `advisor_view` (existing per the "advisor_view" references in response_normalizer.gd)
- Structured action endpoint: `advisor` with `action_id = "ask_dm"`, `query: str`

**Forbidden:**
- No fact invention
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No chat history (Phase 3)

## 10. Test Coverage Target

- `test_frontend_ask_dm.gd` MUST cover AC-01..AC-10
- ≥85% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_ask_dm.gd

## 12. Implementation notes

- The existing `ask_dm_panel.gd` already has the structured-action emit fallback logic. Preserve that pattern — it ensures the panel still works when the parent scene hasn't connected the structured signal.
- Consider a small "dice rolling" animation while waiting, themed to "Consult Fate" — nice-to-have only, skip if not in the asset set.
- Keep the "grounded only" messaging visible in `summary_label` to reassure the player that nothing is hallucinated.

# PRD: Frontend Think Panel — Knowledge Synthesis Surface (Ember-Specific)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the **Think** panel — ember-rpg's knowledge synthesis surface. When the player selects a topic (from Ask About or from their own discovered knowledge), the Think panel renders the backend's grounded `knowledge_view` response: facts the character knows for certain, rumors they've heard, related topics they could investigate. This is the "I thread together what I know" UI — strictly deterministic, never invents facts, always reflects what the backend knowledge kernel has stored. One of the three ember-specific features. The backend already emits `knowledge_view` in the campaign snapshot. The Godot client already has `think_panel.gd` as a scaffold (~90 LOC).

### Reference sources
- **Ember-specific (no GemRB equivalent).** Design reference: CRPG character notebooks + Fallout-style rumor logs.
- **Ember backend:** `frp-backend/engine/world/knowledge.py` (1111 LOC, NPC knowledge/memory system). Ships `knowledge_view` in the `/state` response with shape `{topic, facts, rumors, topics, blockers, ask_about}`.
- **Ember client existing code:** `godot-client/scripts/ui/think_panel.gd` (existing `ThinkPanelWidget` class with methods `set_view`, `sync_from_game_state`, `_render`, `_submit_query`). Reads `GameState.conversation_state.ask_about_selected_topic_id`.

## 2. Scope

**In scope:**
- Render the active topic's facts, rumors, related topics, blockers
- Free-text query input that emits `think <query>` command to the backend
- Embedded Ask About sub-section showing the ask_about sub-response when the backend includes it
- Topic list with click-to-inspect behavior (switches the primary display to that topic's knowledge_view)
- Surface blockers clearly (missing prerequisite, gated by reputation, needs rest, etc.)
- Sync with `GameState.conversation_state` so the think panel knows which topic the player last selected

**Out of scope:**
- Topic discovery logic (backend authority)
- Free invention of facts (strictly forbidden — if backend returns no facts, the UI says "No confirmed facts returned")
- Editing knowledge (read-only surface)
- Cross-party knowledge aggregation (separate PRD if needed)

## 3. Functional Requirements (FR)

**FR-01:** The Think panel MUST render exactly four regions: topic header, facts column, rumors column, related-topics list.

**FR-02:** The topic header MUST show: `topic.label`, `topic.category`, and any `blockers` joined by ", " below the label. If no topic is set, display "No topic selected".

**FR-03:** The facts column MUST render each entry in `knowledge_view.facts` as a separate line. If the array is empty, display "No confirmed facts returned."

**FR-04:** The rumors column MUST render each entry in `knowledge_view.rumors`. If empty: "No rumor lines returned."

**FR-05:** The related-topics list MUST render each entry in `knowledge_view.topics` as a clickable button. Clicking a button MUST set `query_input.text = topic_id` and trigger a fresh re-render (but not yet emit a command — the player confirms with the Think button).

**FR-06:** The query input (LineEdit) MUST accept free-text input. Pressing Enter or clicking the Think button MUST emit `command_requested("think <query>")` where `<query>` is the trimmed input.

**FR-07:** `sync_from_game_state()` MUST pull the latest `GameState.conversation_state.ask_about_selected_topic_id` and prefill `query_input.text` if it is empty.

**FR-08:** When `knowledge_view.ask_about` is present (indicating the backend attached ask_about results to this think query), the rumors column MUST append an "Ask About" section below the regular rumors, showing the embedded `ask_about.facts` and `ask_about.rumors`.

**FR-09:** The widget MUST refresh on `GameState.state_updated` and `GameState.knowledge_view_updated` (add signal if missing).

**FR-10:** The widget MUST NOT mutate `GameState` — it is strictly read-only.

## 4. Data Structures

`knowledge_view` shape (backend-provided):

    {
        "topic": {
            "topic_id": "barrow_king_rumor",
            "label": "The Barrow King",
            "category": "rumor",
            "priority": 50
        },
        "facts": [
            "He was last seen entering the eastern barrow at dusk.",
            "The barrow door was sealed with a thief's glyph."
        ],
        "rumors": [
            "Locals say strange lights flicker in the barrow at night.",
            "A traveling merchant claims she saw a hooded figure matching his description."
        ],
        "topics": [
            {"topic_id": "eastern_barrow", "label": "The Eastern Barrow"},
            {"topic_id": "thieves_guild_glyph", "label": "Thieves' Guild Glyphs"}
        ],
        "blockers": [],
        "ask_about": {
            "response_type": "rumor_only",
            "facts": [],
            "rumors": ["A shepherd heard voices at midnight."]
        }
    }

Widget state:

    class_name ThinkPanelWidget extends PanelContainer
    
    var _view: Dictionary = {}

## 5. Public API — methods that MUST exist

Extend `think_panel.gd` (some methods already exist; marked [existing]):

    # ---- existing ----
    func _ready() -> void                                                        # [existing]
    func set_view(view: Dictionary) -> void                                      # [existing]
    func sync_from_game_state() -> void                                          # [existing]
    func _render() -> void                                                       # [existing, private]
    func _submit_query() -> void                                                 # [existing, private]
    
    # ---- NEW (must be added) ----
    func set_topic(topic_id: String) -> void                                     # focus the panel on a topic without submitting
    func refresh_from_game_state() -> void                                       # explicit public refresh (called by signals)
    func handle_topic_click(topic_id: String) -> void                            # related-topics click handler
    func build_facts_text(facts: Array) -> String                                # joins facts with newlines + BBCode color
    func build_rumors_text(rumors: Array) -> String                              # same for rumors
    func build_ask_about_section(ask_about: Dictionary) -> String                # renders embedded ask_about
    func is_empty_view() -> bool                                                 # true if _view has no topic, facts, or rumors
    func clear_query() -> void
    func get_current_topic_id() -> String
    
    # ---- signals ----
    signal command_requested(command_text: String)                               # [existing]
    signal topic_navigation_requested(topic_id: String)                          # NEW — emit when player clicks a related topic
    signal knowledge_refresh_requested()                                         # NEW — fires when view becomes stale

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The panel has exactly four regions present as named nodes: `TopicLabel`, `FactsPanel`, `RumorsPanel`, `TopicsSection`. Verified by automation bridge `query_state` on each path.

**AC-02 [FR-03]:** Given a `_view` with `facts = ["A", "B", "C"]`, `facts_text.text` MUST contain all three strings separated by newlines.

**AC-03 [FR-04]:** Given a `_view` with empty `rumors`, `rumors_text.text == "No rumor lines returned."`.

**AC-04 [FR-05]:** Given `_view.topics = [{"topic_id": "t1", "label": "Topic One"}]`, the topics list MUST contain exactly one child Button whose `text == "Topic One"`. Clicking that button (via automation bridge) MUST set `query_input.text == "t1"` but MUST NOT emit `command_requested`.

**AC-05 [FR-06]:** Typing "barrow" into the query input and pressing Enter MUST emit `command_requested("think barrow")` exactly once.

**AC-06 [FR-07]:** Setting `GameState.conversation_state.ask_about_selected_topic_id = "lore_dragons"` and calling `sync_from_game_state()` while `query_input.text` is empty MUST result in `query_input.text == "lore_dragons"`.

**AC-07 [FR-08]:** Given `_view.ask_about = {"response_type": "rumor_only", "rumors": ["R1"]}`, `rumors_text.text` MUST contain the string "R1" AND the header "Ask About".

**AC-08 [FR-09]:** Firing `GameState.state_updated` MUST trigger `_render()` exactly once per frame (debounced).

**AC-09 [FR-10]:** Calling `set_view({})` MUST NOT mutate any property on `GameState`. Verified by snapshotting `GameState` before and after.

**AC-10 [reflection]:** Every method in §5 MUST exist on the script.

## 7. Performance Requirements

- `_render()` end-to-end: **< 15ms** with 10 facts + 10 rumors + 10 related topics
- Signal-triggered refresh coalescing: max 1 render per frame
- Topic button list construction: **< 5ms** for 20 topics

## 8. Error Handling

- Missing `_view.topic`: display "No topic selected"; do not crash
- Non-array `facts` / `rumors` / `topics`: treat as empty, log at DEBUG
- `knowledge_view` absent from GameState: render empty state, log at DEBUG
- Query text with only whitespace: no-op, do not emit command

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/think_panel.gd` — extend per §5
- `godot-client/autoloads/game_state.gd` — add `knowledge_view` Dictionary (if missing) + `knowledge_view_updated` signal
- `godot-client/scripts/ui/topic_probe_modal.gd` — when confirming a topic, optionally notify the think panel via `topic_navigation_requested`
- `godot-client/tests/automation/godot/test_frontend_think_panel.gd` — NEW

**Backend (consumed, NOT modified):**
- `/state` response MUST include `knowledge_view` (backend PRD dependency)
- Command endpoint: `think <query>` shortcut

**Forbidden:**
- No fact invention
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No caching of `knowledge_view` on the client (always re-read from GameState)

## 10. Test Coverage Target

- `test_frontend_think_panel.gd` MUST cover AC-01..AC-10
- ≥85% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_think_panel.gd

## 12. Implementation notes

- The existing `think_panel.gd` has a solid foundation. Focus on wiring per §5 + keeping the "no invention" guarantee visible in the UI (e.g. "grounded only" subtitle).
- Consider a small icon next to each fact/rumor indicating source (merchant, rumor, travel encounter, etc.) — nice-to-have.
- BBCode in `RichTextLabel` can color facts differently from rumors for visual clarity.

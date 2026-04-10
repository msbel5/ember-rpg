# PRD: Frontend Journal — BG1 Chapter-Based Quest Log
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the Journal panel — BG1's quest log. Renders journal entries grouped by chapter, with prev/next chapter navigation (Left/Right hotkeys) and in-game timestamp per entry. The existing Godot scaffold `quest_panel.gd` is a placeholder; this PRD extends it to BG1 fidelity.

### Reference sources
- **GemRB behavior:** `gemrb/GUIScripts/bg1/GUIJRNL.py` (116 LOC — full file read). Key functions: `InitJournalWindow(JournalWindow)`, `UpdateJournalWindow(JournalWindow)`, `JournalPrevSectionPress`, `JournalNextSectionPress`. Uses `GemRB.GetJournalSize(Chapter)` and `GemRB.GetJournalEntry(Chapter, i)` API.
- **Date system:** `YEARS` 2DA table provides `STARTTIME` and `STARTYEAR` constants. Game time is in minutes (`GameTime // 4500` for hours). Entries are sorted by `GameTime`.
- **Godot target:** Extend `godot-client/scripts/ui/quest_panel.gd` (or rename to `journal_panel.gd` if preferred)

## 2. Scope

**In scope:**
- Chapter tabs or prev/next chapter navigation with Left/Right hotkeys
- Chronological list of journal entries within the current chapter
- Per-entry display: in-game date + time, entry text (possibly with highlighted keywords)
- Active quest entries section (entries flagged `active` by backend)
- Completed entries section
- Search/filter by text (nice-to-have)
- Automatic scroll to newest entry on chapter switch

**Out of scope:**
- Quest acceptance/decline UI (that's dialog flow)
- Marking quests on the area map (separate PRD for area map)
- Journal entry editing
- Per-character journals (BG1 has one party-wide journal)

## 3. Functional Requirements (FR)

**FR-01:** The journal panel MUST display a chapter header at the top showing the chapter name (from backend) and chapter number.

**FR-02:** The panel MUST have Prev and Next buttons. Pressing Left arrow OR clicking Prev MUST decrement the displayed chapter (clamp at 0). Pressing Right OR Next MUST increment (clamp at `current_chapter`).

**FR-03:** For each chapter, the panel MUST fetch entries from `GameState.journal.chapters[chapter_index].entries` and render them in chronological order.

**FR-04:** Each entry MUST display: formatted in-game date (Year X, Day Y, Hour Z), optional quest category badge (main/side/rumor/lore), and the entry text.

**FR-05:** The panel MUST categorize entries into "Active Quests" and "Completed Quests" sections within each chapter, based on the `status` field on each entry.

**FR-06:** The entry text MUST support BBCode rendering for bold keywords (NPC names, location names).

**FR-07:** Opening the journal MUST scroll to the newest entry in the current chapter by default. Manual scrolling is preserved while the panel is open.

**FR-08:** A search input at the top MUST filter entries by substring match (case-insensitive) against entry text. Empty search shows all.

**FR-09:** The panel MUST refresh on `GameState.journal_updated` signal (add if missing) and on `GameState.state_updated`.

**FR-10:** The chapter nav MUST not show chapters the player has not yet entered (e.g. at chapter 2, only chapters 0 and 1 and 2 are navigable).

## 4. Data Structures

`GameState.journal` expected shape:

    {
        "current_chapter": 2,
        "chapters": [
            {
                "chapter_index": 0,
                "title": "Prologue",
                "entries": [
                    {
                        "entry_id": "prologue_1",
                        "game_time_minutes": 0,
                        "year": 1368,
                        "day": 1,
                        "hour": 8,
                        "text": "Gorion led me out of Candlekeep for the first time.",
                        "category": "main",          # main | side | rumor | lore
                        "status": "completed"        # active | completed | failed
                    },
                    ...
                ]
            },
            ...
        ]
    }

Widget state:

    class_name JournalPanelWidget extends PanelContainer
    
    const ENTRIES_PER_PAGE := 50
    
    var _displayed_chapter: int = 0
    var _search_filter: String = ""
    var _chapter_header: Label
    var _entries_rich_text: RichTextLabel
    var _active_section: Control
    var _completed_section: Control

## 5. Public API — methods that MUST exist

    # ---- construction ----
    func _ready() -> void
    func _input(event: InputEvent) -> void                                       # Left/Right hotkeys
    
    # ---- chapter navigation ----
    func init_journal_window() -> void                                           # GemRB: InitJournalWindow
    func update_journal_window() -> void                                         # GemRB: UpdateJournalWindow
    func journal_prev_section() -> void                                          # GemRB: JournalPrevSectionPress
    func journal_next_section() -> void                                          # GemRB: JournalNextSectionPress
    func set_displayed_chapter(chapter_index: int) -> void
    func get_displayed_chapter() -> int
    func refresh_chapter_header() -> void
    
    # ---- entry rendering ----
    func render_entries_for_chapter(chapter_index: int) -> void
    func build_entry_text(entry: Dictionary) -> String                           # BBCode-formatted
    func format_entry_date(entry: Dictionary) -> String                          # "Year 1368, Day 12, 14:00"
    func categorize_entry(entry: Dictionary) -> String                           # "active" | "completed" | "failed"
    func get_active_entries(chapter_index: int) -> Array
    func get_completed_entries(chapter_index: int) -> Array
    
    # ---- search ----
    func apply_search_filter(query: String) -> void
    func get_filtered_entries(chapter_index: int) -> Array
    func clear_search() -> void
    
    # ---- scroll ----
    func scroll_to_newest() -> void
    func scroll_to_entry(entry_id: String) -> void
    
    # ---- helpers ----
    func get_chapter_count() -> int
    func get_chapter_title(chapter_index: int) -> String
    func has_entries_in_chapter(chapter_index: int) -> bool
    
    # ---- signals ----
    signal entry_clicked(entry_id: String)
    signal chapter_changed(new_chapter: int)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** Given a chapter with title "Chapter 2: Nashkel Mines", the header label MUST display exactly that string.

**AC-02 [FR-02]:** Pressing Left while `_displayed_chapter == 2` MUST set it to 1. Pressing Left while at 0 MUST stay at 0. Pressing Right while at `current_chapter` MUST stay there.

**AC-03 [FR-03]:** Rendering chapter 1 with 3 entries MUST produce at least 3 child nodes in the entries container (one per entry, possibly with dividers between).

**AC-04 [FR-04]:** `format_entry_date({year: 1368, day: 12, hour: 14})` MUST return a string containing "1368", "12", and "14".

**AC-05 [FR-05]:** Given entries with statuses [active, active, completed], the active section MUST contain 2 entries and the completed section MUST contain 1.

**AC-06 [FR-06]:** BBCode tags in entry text (e.g. `[b]Gorion[/b]`) MUST render as bold in the RichTextLabel.

**AC-07 [FR-08]:** Setting `apply_search_filter("Gorion")` MUST result in only entries containing "Gorion" (case-insensitive) being rendered.

**AC-08 [FR-09]:** Firing `GameState.journal_updated` MUST call `update_journal_window()` once.

**AC-09 [FR-10]:** With `current_chapter == 2`, calling `journal_next_section()` while at chapter 2 MUST NOT advance beyond 2.

**AC-10 [reflection]:** Every method in §5 MUST exist on the script.

## 7. Performance Requirements

- `render_entries_for_chapter()` with 100 entries: **< 30ms**
- Search filter on 200 entries: **< 20ms**
- Chapter switch: **< 50ms**

## 8. Error Handling

- Missing `chapters[index]`: render empty state "No entries in this chapter"
- Malformed entry (missing required fields): skip, log at DEBUG
- Search query with only whitespace: show all entries

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/quest_panel.gd` — rewrite or extend per §5 (rename to `journal_panel.gd` if preferred — update scene references accordingly)
- `godot-client/autoloads/game_state.gd` — add `journal` Dictionary + `journal_updated` signal if missing
- `godot-client/tests/automation/godot/test_frontend_journal.gd` — NEW

**Backend (consumed, NOT modified):**
- `/state` response MUST include `journal` per §4 shape
- No new endpoints

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No GemRB code port
- No entry mutation from client

## 10. Test Coverage Target

- `test_frontend_journal.gd` MUST cover AC-01..AC-10
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_journal.gd

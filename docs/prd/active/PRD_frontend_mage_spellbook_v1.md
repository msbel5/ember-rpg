# PRD: Frontend Mage Spellbook — BG1 9-Level Memorization Grid
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the mage spellbook panel — BG1's arcane spell memorization UI. Shows the selected mage's known spells (scrollable grid) and memorized spells (12-slot 4×3 grid) for the currently selected spell level (1..9), with prev/next level buttons, left/right hotkeys, spell icons, spell info on right-click, memorize/unmemorize on left-click.

### Reference sources
- **GemRB behavior:** `gemrb/GUIScripts/GUIMG.py` (844 LOC — mage spellbook), `gemrb/GUIScripts/Spellbook.py` (830 LOC — shared spellbook helpers), `gemrb/GUIScripts/ie_spells.py` (23 LOC constants)
- **GemRB key functions:** `InitMageWindow(window)`, `UpdateMageWindow`, `RefreshMageLevel`, `MagePrevLevelPress`, `MageNextLevelPress`, `OnMageMemorizeSpell`, `OnMageUnmemorizeSpell`, `OpenMageSpellInfoWindow`, `OpenContingenciesWindow`, `Spellbook.HasSorcererBook(pc)`
- **Godot target:** NEW `godot-client/scripts/ui/spellbook_mage_panel.gd` + NEW `godot-client/scenes/spellbook_mage_panel.tscn`

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- 9 spell-level tabs (levels 1..9) with prev/next buttons and Left/Right hotkeys
- Known spells grid (scrollable) for the selected level
- Memorized spells grid (12 slots, 4×3) for the selected level
- Left-click on known spell → memorize (if free memorized slot available)
- Right-click on memorized or known spell → open info modal (description, casting time, school, range, damage, saves)
- Left-click on memorized spell → unmemorize
- Sorcerer variant: no memorization, show known spells with uses-per-day instead
- Rest prompt when memorized slots are empty (or show "Need rest to memorize" status)

**Out of scope:**
- Rest mechanics (backend)
- Spell learning / scribing from scrolls (separate flow)
- Contingencies (BG2-only feature, not relevant to BG1 phase)
- Spell sequencer UI (BG2-only)

## 3. Functional Requirements (FR)

**FR-01:** The panel MUST render a row of 9 spell-level tab buttons labeled `1 2 3 4 5 6 7 8 9`. The currently selected level MUST be visually highlighted.

**FR-02:** Pressing Left arrow or clicking the Prev button MUST decrement the selected level (clamp at 1). Pressing Right arrow or clicking Next MUST increment (clamp at 9).

**FR-03:** The panel MUST render up to `GUI_SPELL_BUTTON_COUNT` (default 24) known-spell buttons for the selected level, each showing the spell icon and tooltip with spell name.

**FR-04:** The panel MUST render exactly 12 memorized-slot buttons in a 4×3 grid. Empty slots MUST show a generic placeholder; filled slots show the spell icon with a small "faded" overlay if the spell has been cast already (not yet reset by rest).

**FR-05:** Left-click on a known spell MUST call `memorize_spell(pc_id, spell_ref, level)` which issues backend command `memorize <spell_ref>`. If no free slot at that level, show a "No free slots" toast.

**FR-06:** Left-click on a memorized slot MUST call `unmemorize_spell(pc_id, slot_index, level)` which issues backend command `unmemorize <spell_ref> <slot_index>`.

**FR-07:** Right-click on either grid MUST open an info modal showing: name, school, level, casting time, range, duration, saving throw, damage, description. Data comes from the backend spell definition.

**FR-08:** The panel MUST detect sorcerer classes via `GameState.character_sheet.is_sorcerer_caster` (or equivalent) and switch to sorcerer mode: no memorize/unmemorize actions, each spell shows "Uses: X/Y per day".

**FR-09:** The panel MUST refresh on `GameState.state_updated` and `GameState.spell_memorized_changed`. Refresh MUST be idempotent.

**FR-10:** The panel MUST display a status label at top showing the PC's name + class + level count at the current spell level (e.g. "Imoen — Mage 4 — Level 2 spells: 3 memorized / 5 max").

## 4. Data Structures

`GameState.character_sheet.spellbook` expected shape:

    {
        "is_sorcerer_caster": false,
        "mage_book": {
            "1": {
                "known": [{spell_ref, name, school, icon_slug}],
                "memorized": [{spell_ref, name, cast: bool, icon_slug}],
                "max_memorized": 5
            },
            "2": {...},
            ...
            "9": {...}
        }
    }

Widget state:

    class_name MageSpellbookPanel extends PanelContainer
    
    const MAX_SPELL_LEVEL := 9
    const MEMORIZED_SLOTS_PER_LEVEL := 12
    const DEFAULT_KNOWN_GRID_COUNT := 24
    
    var _current_level: int = 1
    var _active_pc_id: String = ""
    var _is_sorcerer: bool = false
    var _known_buttons: Array[Button] = []
    var _memorized_buttons: Array[Button] = []

## 5. Public API — methods that MUST exist

    # ---- construction ----
    func _ready() -> void
    func _input(event: InputEvent) -> void                                       # Left/Right hotkeys
    
    # ---- level navigation ----
    func set_spell_level(level: int) -> void                                     # clamped 1..9
    func get_spell_level() -> int
    func prev_level() -> void
    func next_level() -> void
    func refresh_level_buttons() -> void
    
    # ---- window refresh ----
    func init_mage_window() -> void                                              # GemRB: InitMageWindow
    func update_mage_window() -> void                                            # GemRB: UpdateMageWindow
    func refresh_mage_level() -> void                                            # GemRB: RefreshMageLevel
    
    # ---- spell interaction ----
    func memorize_spell(pc_id: String, spell_ref: String, level: int) -> bool
    func unmemorize_spell(pc_id: String, slot_index: int, level: int) -> bool
    func open_spell_info_modal(spell_ref: String) -> void                        # GemRB: OpenMageSpellInfoWindow
    
    # ---- known spell grid ----
    func render_known_spells(pc_id: String, level: int) -> void
    func setup_known_spell_button(button_index: int, spell_entry: Dictionary) -> void
    
    # ---- memorized spell grid ----
    func render_memorized_spells(pc_id: String, level: int) -> void
    func setup_memorized_slot_button(slot_index: int, spell_entry: Dictionary) -> void
    
    # ---- sorcerer mode ----
    func is_sorcerer_mode() -> bool
    func render_sorcerer_view(pc_id: String, level: int) -> void
    func setup_sorcerer_spell_button(button_index: int, spell_entry: Dictionary, uses_current: int, uses_max: int) -> void
    
    # ---- helpers ----
    func count_memorized(pc_id: String, level: int) -> int
    func max_memorizable(pc_id: String, level: int) -> int
    func has_free_memorized_slot(pc_id: String, level: int) -> bool
    func get_status_text() -> String                                             # "Imoen — Mage 4 — Level 2 spells: 3/5"
    
    # ---- signals ----
    signal command_requested(command_text: String)
    signal spell_info_requested(spell_ref: String)
    signal memorize_failed(reason: String)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The panel has exactly 9 level tab buttons. Verified by counting children of the level-tab container.

**AC-02 [FR-02]:** Pressing Left while `_current_level == 3` MUST set `_current_level == 2` and trigger `refresh_mage_level()`. Pressing Right while at level 9 MUST stay at 9.

**AC-03 [FR-04]:** `render_memorized_spells(pc_id, 1)` with 3 memorized spells MUST populate 3 buttons with icons and leave 9 as empty placeholders.

**AC-04 [FR-05]:** Simulating a left-click on a known spell button with a free slot MUST emit `command_requested` with a string matching `^memorize [\w_-]+$`.

**AC-05 [FR-05 failure]:** Simulating a left-click when `has_free_memorized_slot() == false` MUST emit `memorize_failed("No free slots")` and NOT emit `command_requested`.

**AC-06 [FR-07]:** Simulating a right-click on any spell button MUST emit `spell_info_requested(spell_ref)`.

**AC-07 [FR-08]:** With `character_sheet.is_sorcerer_caster = true`, calling `update_mage_window()` MUST call `render_sorcerer_view()` instead of `render_known_spells() + render_memorized_spells()`.

**AC-08 [FR-09]:** Firing `GameState.spell_memorized_changed` MUST trigger `refresh_mage_level()` exactly once per frame.

**AC-09 [FR-10]:** The status label text MUST match the format described in FR-10 and include all 4 fields.

**AC-10 [reflection]:** Every method in §5 MUST exist on the script.

## 7. Performance Requirements

- `refresh_mage_level()`: **< 15ms** for 9 known + 12 memorized slots
- Level switch: **< 30ms** total
- Spell info modal open: **< 100ms**

## 8. Error Handling

- `spellbook.mage_book[level]` missing: render empty state, log at DEBUG
- Backend spell def missing for `spell_ref`: render placeholder icon, log once per unique missing ref
- Memorize command backend error: show toast with error message, keep panel state
- Level out of range: clamp to [1, 9]

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/spellbook_mage_panel.gd` — NEW
- `godot-client/scenes/spellbook_mage_panel.tscn` — NEW
- `godot-client/autoloads/game_state.gd` — add `spellbook` projection + `spell_memorized_changed` signal if missing
- `godot-client/tests/automation/godot/test_frontend_mage_spellbook.gd` — NEW

**Backend (consumed, NOT modified):**
- `/state` response includes `character_sheet.spellbook.mage_book` (dependency; file note if missing)
- Commands: `memorize <spell_ref>`, `unmemorize <spell_ref> <slot>`

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port

## 10. Test Coverage Target

- `test_frontend_mage_spellbook.gd` MUST cover AC-01..AC-10
- ≥80% branch coverage
- `run_headless_tests.gd` stays green

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_mage_spellbook.gd

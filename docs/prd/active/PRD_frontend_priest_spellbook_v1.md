# PRD: Frontend Priest Spellbook — BG1 7-Level Divine Memorization
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the priest spellbook panel — BG1's divine caster (Cleric, Druid, Ranger, Paladin) spell memorization UI. Structurally identical to the mage spellbook but with 7 spell levels instead of 9 and uses `IE_SPELL_TYPE_PRIEST`. Shares most of its behavior with `PRD_frontend_mage_spellbook_v1.md`; implementers SHOULD factor out shared helpers (e.g. a base `spellbook_panel.gd` or a mixin).

### Reference sources
- **GemRB behavior:** `gemrb/GUIScripts/GUIPR.py` (329 LOC), `gemrb/GUIScripts/Spellbook.py` (shared)
- **GemRB key functions:** `InitPriestWindow(Window)`, `UpdatePriestWindow`, `RefreshPriestLevel`, `PriestPrevLevelPress`, `PriestNextLevelPress`, `OnPriestMemorizeSpell`, `OnPriestUnmemorizeSpell`, `OpenPriestSpellInfoWindow`, `OpenPriestSpellUnmemorizeWindow`
- **Godot target:** NEW `godot-client/scripts/ui/spellbook_priest_panel.gd` + NEW `godot-client/scenes/spellbook_priest_panel.tscn`

## 2. Scope

Same as `PRD_frontend_mage_spellbook_v1.md` §2 with these differences:
- **7 spell levels** (Cleric/Druid max) instead of 9
- `IE_SPELL_TYPE_PRIEST` instead of `IE_SPELL_TYPE_WIZARD`
- Rangers and Paladins use this panel but have restricted access (rangers: druid spells from level 8, paladins: cleric spells from level 9)
- Druid spells pull from a separate spell list; the backend must distinguish (out of scope for this PRD — frontend just renders what backend provides)

## 3. Functional Requirements (FR)

**FR-01..FR-10:** Same as `PRD_frontend_mage_spellbook_v1.md` FR-01..FR-10 with the following replacements:
- "9 spell-level tab buttons" → "7 spell-level tab buttons"
- "levels 1..9" → "levels 1..7"
- "mage_book" → "priest_book"
- "Mage N" → "Cleric/Druid/Ranger/Paladin N" (use `character_sheet.divine_caster_class_title`)

**FR-11:** For Ranger/Paladin: only show spell levels the character has access to at their current level. Below the access threshold, the panel displays "Your class does not grant divine spellcasting until level N" without level tabs.

## 4. Data Structures

`GameState.character_sheet.spellbook.priest_book` expected shape:

    {
        "priest_book": {
            "1": {
                "known": [{spell_ref, name, sphere, icon_slug}],
                "memorized": [{spell_ref, name, cast: bool, icon_slug}],
                "max_memorized": 4,
                "accessible": true
            },
            "2": {...},
            ...
            "7": {...}
        },
        "divine_caster_class_title": "Cleric",
        "divine_access_level": 1                    # for ranger/paladin gating
    }

Widget state:

    class_name PriestSpellbookPanel extends PanelContainer
    
    const MAX_PRIEST_SPELL_LEVEL := 7
    const MEMORIZED_SLOTS_PER_LEVEL := 12
    const DEFAULT_KNOWN_GRID_COUNT := 24
    
    var _current_level: int = 1
    var _active_pc_id: String = ""
    var _known_buttons: Array[Button] = []
    var _memorized_buttons: Array[Button] = []

## 5. Public API — methods that MUST exist

Mirrors `PRD_frontend_mage_spellbook_v1.md` §5 with `priest_` / `Priest` prefixes where appropriate:

    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # level nav
    func set_spell_level(level: int) -> void
    func get_spell_level() -> int
    func prev_level() -> void
    func next_level() -> void
    func refresh_level_buttons() -> void
    
    # window refresh
    func init_priest_window() -> void                                            # GemRB: InitPriestWindow
    func update_priest_window() -> void                                          # GemRB: UpdatePriestWindow
    func refresh_priest_level() -> void                                          # GemRB: RefreshPriestLevel
    
    # spell interaction
    func memorize_spell(pc_id: String, spell_ref: String, level: int) -> bool
    func unmemorize_spell(pc_id: String, slot_index: int, level: int) -> bool
    func open_spell_info_modal(spell_ref: String) -> void                        # GemRB: OpenPriestSpellInfoWindow
    func open_unmemorize_confirm_modal(pc_id: String, slot_index: int) -> void   # GemRB: OpenPriestSpellUnmemorizeWindow
    
    # rendering
    func render_known_spells(pc_id: String, level: int) -> void
    func setup_known_spell_button(button_index: int, spell_entry: Dictionary) -> void
    func render_memorized_spells(pc_id: String, level: int) -> void
    func setup_memorized_slot_button(slot_index: int, spell_entry: Dictionary) -> void
    
    # ranger/paladin gating
    func is_level_accessible(level: int) -> bool
    func render_access_gate_message(current_class_level: int) -> void
    
    # helpers
    func count_memorized(pc_id: String, level: int) -> int
    func max_memorizable(pc_id: String, level: int) -> int
    func has_free_memorized_slot(pc_id: String, level: int) -> bool
    func get_status_text() -> String
    
    # signals
    signal command_requested(command_text: String)
    signal spell_info_requested(spell_ref: String)
    signal memorize_failed(reason: String)

## 6. Acceptance Criteria (AC)

Same as `PRD_frontend_mage_spellbook_v1.md` AC-01..AC-10 with:
- AC-01: 7 level tab buttons (not 9)
- AC-02: clamp upper bound at 7
- AC-11: For a level-4 Ranger (no divine spells below class level 8), `is_level_accessible(1) == false` AND the panel renders the access gate message. Verified by checking label text.

## 7. Performance Requirements

Same as mage spellbook PRD.

## 8. Error Handling

Same as mage spellbook PRD + ranger/paladin access gating fallback.

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/spellbook_priest_panel.gd` — NEW
- `godot-client/scenes/spellbook_priest_panel.tscn` — NEW
- `godot-client/tests/automation/godot/test_frontend_priest_spellbook.gd` — NEW

**Recommended refactor (post-implementation):** extract a shared `spellbook_panel_base.gd` containing the common level-tab navigation, button grid management, and info modal helpers. Both mage and priest panels inherit/compose. NOT required for this PRD but noted as follow-up.

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No GemRB code port

## 10. Test Coverage Target

- `test_frontend_priest_spellbook.gd` MUST cover AC-01..AC-11
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_priest_spellbook.gd

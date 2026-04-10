# PRD: Frontend Character Record — BG1 Stats Sheet + Actions
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify a BG1-fidelity character record ("character sheet") screen for the Godot client. The panel displays the full stat block of the currently-selected party member — ability scores with modifiers, HP/AC, combat stats (THAC0, APR, damage), saves, resistances, proficiencies, skills — plus action buttons for Level Up, Dual Class, Information, Reform Party, Customize, and Export. This replaces the current stub `character_panel.gd` which shows only a name, class, and a truncated stat string.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\GUIREC.py` (838 LOC — window init, refresh, stat overview, information sub-window)
- **GemRB behavior (shared):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\GUIRECCommon.py` (859 LOC — customize window: portrait/sound/script/biography, export, ability bonus tables)
- **GemRB behavior (stat IDs):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\ie_stats.py` (399 LOC — IE_* stat constants used as lookup keys)
- **Godot target:** `godot-client/scripts/ui/character_panel.gd` (currently ~200 LOC stub; to be rewritten)
- **Godot companion:** `godot-client/scenes/character_panel.tscn` (to be created)

**Clean-room rule:** Read GemRB to understand what information is displayed and in what order. Do not copy or translate code. Implement independently in GDScript.

## 2. Scope

**In scope:**
- Full BG1-style stat block layout: header (name/portrait/class/alignment/level/XP), ability scores, HP/AC/combat stats, saves, resistances, proficiencies, skills, biography
- Action button row: Level Up (if eligible), Dual Class (if eligible), Information (opens sub-panel with derived stats), Reform Party, Customize (portrait/sound/script/biography), Export character
- Refresh on `GameState.character_sheet_updated` and `GameState.state_updated`
- Eligibility state for action buttons (enabled/disabled) reflecting backend truth

**Out of scope:**
- Actual level-up flow (separate PRD: `PRD_frontend_level_up_v1.md`)
- Actual dual-class flow (separate PRD: `PRD_frontend_dual_class_v1.md`)
- Actual party reform UI (separate PRD)
- Customize sub-windows (portrait selector, sound set, script assignment, biography editor) — noted as buttons here but sub-flows are separate sub-PRDs: `PRD_frontend_character_record_customize_v1.md`
- Export to file (serialization lives in backend save system)

## 3. Functional Requirements (FR)

**FR-01:** The character record panel MUST display a header row containing: portrait (64×96 px minimum), character name, class/kit title, race, gender, alignment, level (for multi-class, list each class's level), current XP, XP needed for next level.

**FR-02:** The panel MUST display the six ability scores (STR, DEX, CON, INT, WIS, CHA) each as a label + value. STR MUST show percentile form "18/77" when applicable (STR 18 with percentile roll). A hover tooltip on any ability score MUST show the modifier summary (e.g. "+1 to-hit, +2 damage, 90 weight allowance").

**FR-03:** The panel MUST display vitals: HP current / HP max, AC (base and modified), THAC0, APR (attacks per round), damage bonus (+melee / +missile), movement rate.

**FR-04:** The panel MUST display saving throws: Save vs Death, Save vs Wand, Save vs Polymorph, Save vs Breath, Save vs Spell, each as a single integer (lower is better per AD&D 2e).

**FR-05:** The panel MUST display resistances: Slashing, Piercing, Crushing, Missile, Fire, Cold, Electric, Acid, Magic Damage, Magic Resistance. Each shown as a percentage.

**FR-06:** The panel MUST display weapon proficiencies as a list of (weapon type, star count) pairs. Star count is 0..5; display as filled/empty star icons or "★★★☆☆" unicode.

**FR-07:** The panel MUST display class skills where applicable:
- All classes: Lore
- Thief / Bard: Pickpocket, Open Locks, Find Traps, Move Silently, Hide in Shadows, Set Traps, Detect Illusion
- Mage: current school (if specialist) and opposition school
- Cleric: patron deity (if tracked)
- Bard: also Lore
- Ranger / Paladin: also charm animals / turn undead if applicable

**FR-08:** The panel MUST display a biography text area (multi-line, scrollable, read-only in this PRD; editing lives in the Customize sub-flow). Biography text comes from `GameState.character_sheet.biography`.

**FR-09:** The panel MUST render an action button row with: Level Up, Dual Class, Information, Reform Party, Customize, Export. Each button's `disabled` state MUST reflect `GameState.character_sheet.action_eligibility` keys:
- `level_up_available: bool`
- `dual_class_available: bool`
- `reform_party_allowed: bool`
- `export_allowed: bool`

**FR-10:** Clicking the Level Up button MUST emit `panel_requested.emit("level_up")` (routed by the game_session shell to the level-up panel). Clicking Dual Class → `panel_requested.emit("dual_class")`. Clicking Information → toggles an inline "Information" sub-panel within the character panel showing derived stats (see FR-11). Clicking Reform Party → `panel_requested.emit("reform_party")`. Clicking Customize → `panel_requested.emit("customize_character")`. Clicking Export → emits `command_requested.emit("export_character")`.

**FR-11:** The Information sub-panel MUST display a text-based stat overview including: derived ability bonuses (to-hit bonus, damage bonus, spell bonus per GemRB `GetAbilityBonuses()` structure), bonus spells per spell level (GemRB `GetBonusSpells()`), total kills, favorite spell, favorite weapon, monster kills by type.

**FR-12:** The panel MUST refresh on `GameState.state_updated` and `GameState.character_sheet_updated`. Refresh MUST be idempotent.

## 4. Data Structures

Extend `GameState.character_sheet` to expose the full BG1 stat block. The backend `/state` response's `character_sheet` field MUST supply these keys (if it does not, this PRD is BLOCKED on a sibling backend PRD):

    character_sheet: Dictionary
        name: String
        portrait_slug: String
        class_name: String                # "Fighter", "Mage/Thief", etc.
        kit_name: String                  # may be empty
        race: String
        gender: String
        alignment: String                 # "LG", "NG", ... "CE"
        level: Array[Dictionary]          # Per-class: [{class_name, level, xp, xp_next}]
        ability_scores: Dictionary        # {str, dex, con, int, wis, cha} — each is {value, percentile}
        ability_bonuses: Dictionary       # {to_hit, damage, ac, saves, ...}
        hp_current: int
        hp_max: int
        ac_base: int
        ac_modified: int
        thac0: int
        apr: float                        # attacks per round, can be 1.5 etc
        damage_bonus_melee: int
        damage_bonus_missile: int
        movement_rate: int
        saves: Dictionary                 # {death, wand, polymorph, breath, spell}
        resistances: Dictionary           # {slash, pierce, crush, missile, fire, cold, elec, acid, magic_dmg, magic_res}
        proficiencies: Array[Dictionary]  # [{weapon_type, stars}]
        skills: Dictionary                # {lore, pickpocket, open_locks, ..., set_traps, detect_illusion}
        biography: String
        action_eligibility: Dictionary    # {level_up_available, dual_class_available, reform_party_allowed, export_allowed}
        information: Dictionary           # derived overview shown in Information sub-panel

No new backend endpoints.

## 5. Public API

Extend `character_panel.gd` with:

    class_name CharacterPanelWidget
    
    signal command_requested(command_text: String)
    signal panel_requested(panel_id: String)
    signal information_toggled(visible: bool)
    
    func refresh() -> void
    func set_active_party_member(index: int) -> void  # for future multi-PC support
    func show_information_sub_panel() -> void
    func hide_information_sub_panel() -> void

The widget is self-contained; state comes from `GameState.character_sheet`.

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** When the character panel is opened with a non-empty `character_sheet`, the header displays the character name exactly matching `GameState.character_sheet.name`. Verified via automation bridge `query_state` on a dedicated `HeaderNameLabel` node.

**AC-02 [FR-02]:** All six ability score labels are visible and each shows a numeric value. Verified by querying nodes named `Str`, `Dex`, `Con`, `Int`, `Wis`, `Cha` and asserting their text matches `int(character_sheet.ability_scores[key].value)`.

**AC-03 [FR-03]:** The vitals block renders five distinct values: HP, AC, THAC0, APR, damage bonus. Each MUST be present as a labeled node; values match `GameState.character_sheet` exactly.

**AC-04 [FR-04]:** Five saving-throw labels are rendered with numeric values. Verified by automation bridge.

**AC-05 [FR-05]:** Resistance block renders 10 labels with percent values. Labels with value 0 MUST still be rendered (not hidden); they are informative as "not resistant".

**AC-06 [FR-06]:** Proficiency list renders at least one entry when `proficiencies` is non-empty. Each entry's displayed star count equals `stars` from the data.

**AC-07 [FR-09]:** Each of the six action buttons has its `disabled` state matching `action_eligibility`. For example, if `level_up_available == false`, the Level Up button MUST be disabled. Verified by automation bridge `query_state` on each button node.

**AC-08 [FR-10]:** Clicking the Level Up button (via automation bridge `activate_node`) MUST emit `panel_requested` with `"level_up"`. Verified by a test-mode spy.

**AC-09 [FR-11]:** Clicking the Information button toggles the inline sub-panel's visibility. The sub-panel's text area MUST contain at least one line from `character_sheet.information` when visible.

**AC-10 [FR-12]:** When `GameState.character_sheet_updated` signal fires twice, the panel's child count is stable (no leaked nodes). Verified by a headless test.

## 7. Performance Requirements

- Full `refresh()` with all stat blocks visible: **< 30ms** on dev machine
- Open/close transition: **< 80ms**
- Signal-triggered refresh throttling: no refresh if < 50ms since previous refresh (coalesce to end-of-frame)

## 8. Error Handling

- **Missing `character_sheet.information`:** Render the Information sub-panel with a "No derived stats available" message, keep button enabled.
- **Missing `action_eligibility`:** Treat all action buttons as disabled with tooltip "Eligibility data unavailable".
- **Missing `ability_scores`:** Render score labels as "—" and log once to console.
- **Negative values where positive expected (e.g. HP > max):** Clamp display, log warning, continue rendering.
- **Extremely long biography text (> 10k chars):** Truncate to 5000 chars with "..." suffix in the display area; full text still accessible via Customize flow.

## 9. Integration Points

**Godot (editable by this PRD):**
- `godot-client/scripts/ui/character_panel.gd` — rewrite
- `godot-client/scenes/character_panel.tscn` — NEW scene file defining the layout
- `godot-client/autoloads/game_state.gd` — verify `character_sheet` keys exist; extend only if missing backend projection
- `godot-client/tests/automation/godot/test_frontend_character_record.gd` — NEW headless acceptance test covering AC-01..AC-10

**Backend (consumed, NOT modified by this PRD):**
- `/state` response — MUST expose `character_sheet` with the shape in §4. If any key is missing, file a dependency note and BLOCK until the sibling backend PRD lands
- `/game/campaigns/{id}/command` — used for `export_character` shortcut

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No direct backend projection computation on the client — read from `GameState` only
- No GemRB code reuse (clean-room rule — see PRD_frontend_extraction_index_v1.md §1)

## 10. Test Coverage Target

- `test_frontend_character_record.gd` MUST exercise AC-01 through AC-10 in order.
- Existing `run_headless_tests.gd` MUST stay green.
- Coverage goal: ≥80% of branches in `character_panel.gd`.

## 11. Verification

    # 1. Headless regression
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    
    # 2. New character record acceptance
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_character_record.gd
    
    # 3. Backend sanity (character sheet projection)
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_campaign_godot_payload_shapes.py -q -k "character_sheet"

All three MUST be green.

## 12. Method catalog — GemRB GUIREC.py + GUIRECCommon.py → Godot mapping

The implementation MUST provide Godot equivalents for every GemRB function listed below. Source: `gemrb/GUIScripts/GUIREC.py` (838 LOC) and `gemrb/GUIScripts/GUIRECCommon.py` (859 LOC). Method names may adapt to idiomatic GDScript; responsibilities MUST be covered one-to-one.

### Main record window (must_have)

    # GemRB: InitRecordsWindow(Window), UpdateRecordsWindow(Window)
    func init_record_panel() -> void
    func update_record_panel() -> void
    
    # GemRB: UpdateActorDescription(Window) — updates the biography / stat overview text
    func update_actor_description() -> void
    
    # GemRB: GetStatOverview(pc) — produces the multi-line text block at the bottom
    func get_stat_overview(pc_id: String) -> String

### Ability bonus display (must_have)

    # GemRB: GetAbilityBonuses(pc, expand=True)
    func get_ability_bonuses(pc_id: String, expand: bool = true) -> Dictionary
        # returns {to_hit_bonus, damage_bonus, ac_bonus, save_bonus, spell_bonus, weight_allowance, ...}
    
    # GemRB: GetBonusSpells(pc, expand=True)
    func get_bonus_spells(pc_id: String, expand: bool = true) -> Dictionary
        # returns {level_1: int, level_2: int, ..., level_7: int} — wisdom bonus spells per day for clerics/druids
    
    # GemRB: TypeSetStats(stats, pc, recolor=False)
    func type_set_stats(stats_dict: Dictionary, pc_id: String, recolor: bool = false) -> Array[String]
        # formats a list of rich-text lines for the overview panel

### Exportability / dual-class / level up (must_have queries)

    # GemRB: Exportable(pc)
    func is_exportable(pc_id: String) -> bool
    
    # GemRB: CanDualClass(pc) — from GUICommon
    func can_dual_class(pc_id: String) -> bool
    
    # GemRB: LUCommon.CanLevelUp(pc)
    func can_level_up(pc_id: String) -> bool

### Customize sub-window (must_have — separate modal)

    # GemRB: OpenCustomizeWindow()
    func open_customize_modal() -> void
    
    # GemRB: OpenPortraitSelectWindow, PortraitLeftPress, PortraitRightPress, PortraitDonePress
    func open_portrait_select() -> void
    func portrait_select_left() -> void
    func portrait_select_right() -> void
    func portrait_select_done() -> void
    
    # GemRB: OpenCustomPortraitWindow, CustomPortraitDonePress, LargeCustomPortrait, SmallCustomPortrait
    func open_custom_portrait_file_picker() -> void
    func apply_custom_portrait(large_slug: String, small_slug: String) -> void

### Sound set sub-window

    # GemRB: OpenSoundWindow, CloseSoundWindow, DoneSoundWindow, PlaySoundPressed, NextSound
    func open_sound_set_modal() -> void
    func close_sound_set_modal() -> void
    func apply_sound_set(sound_set_id: String) -> void
    func play_sound_sample(sample_index: int) -> void
    func next_sound_sample() -> void

### Script sub-window

    # GemRB: OpenScriptWindow, DoneScriptWindow, FindScriptFile(selected)
    func open_script_modal() -> void
    func apply_script_selection(script_resref: String) -> void
    func find_script_file(script_name: String) -> String

### Biography sub-window

    # GemRB: OpenBiographyWindow, OpenBiographyEditWindow, RevertBiography, ClearBiography, DoneBiographyWindow, GetProtagonistBiography
    func open_biography_modal() -> void
    func open_biography_editor() -> void
    func revert_biography() -> void
    func clear_biography() -> void
    func save_biography(text: String) -> void
    func get_biography_text(pc_id: String) -> String

### Export

    # GemRB: OpenExportWindow, ExportDonePress, ExportCancelPress, ExportEditChanged
    func open_export_modal() -> void
    func export_character(filename: String) -> bool
    func validate_export_filename(filename: String) -> Dictionary  # {valid: bool, error: String}

### Reform party

    # GemRB: OpenRecReformPartyWindow
    func open_reform_party_modal() -> void

### Skills helpers (thief / bard / ranger)

    # GemRB: GetValidSkill(pc, stat)
    func get_valid_skill_value(pc_id: String, skill_stat: String) -> int
    
    # GemRB: GS(pc, stat), GA(pc, stat, col) — low-level stat getters
    func get_player_stat_direct(pc_id: String, stat_id: String) -> int
    func get_player_stat_array(pc_id: String, stat_id: String, col: int) -> int

### Information window (the inline "details" sub-panel)

    # GemRB: OpenInformationWindow
    func open_information_sub_panel() -> void
    func close_information_sub_panel() -> void
    func build_information_text(pc_id: String) -> String             # derived stats text

### Kit information (BG2-style; stubbed for BG1 scope)

    # GemRB: OpenKitInfoWindow (BG2+ only)
    func open_kit_info_modal(kit_id: String) -> void                 # no-op in BG1 mode

### Reflection acceptance criterion

**AC-11 [method catalog completeness]:** A headless test MUST enumerate every method listed in §5 and §12 and assert `script.has_method(name) == true` for each. Any missing method fails the test with the specific name.

## 13. Implementation notes (non-binding)

- The header HP/AC/THAC0/APR labels should share a common "stat label" widget. Extract a small helper `scripts/ui/stat_label.gd` if repetition exceeds three instances.
- Consider a read-only "compact" view for the sidebar rail separately — NOT part of this PRD.
- The portrait rendering already has a `portrait_rect` node in the current stub; keep that node and extend around it.
- Use Godot's `Tween` for any transitions. Do not use `AnimationPlayer` for simple fades.

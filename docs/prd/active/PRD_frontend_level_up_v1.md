# PRD: Frontend Level Up — BG1 Multi-Page Level Advancement Flow
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify a BG1-fidelity level-up flow for the Godot client. The feature renders a multi-page wizard launched from the character record panel whenever the backend reports `LUCommon.CanLevelUp(pc) == true`. The wizard walks the player through HP roll (with reroll), skill allocation (thief / bard only), proficiency allocation (on milestone levels), and spell selection (caster classes on milestone levels), ending with a summary confirmation. Today's client has no level-up flow at all — level eligibility is exposed in `character_panel.gd`'s action row, but pressing the button only emits a placeholder signal. This PRD delivers the full widget and every method required to drive it.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\LevelUp.py` (715 LOC — main wizard shell, HP rolling, info toggle, done / save)
- **GemRB behavior (shared):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\LUCommon.py` (479 LOC — `CanLevelUp`, next-level XP lookup, SetupHP/Thaco/Lore/SavingThrows helpers)
- **GemRB behavior (profs):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\LUProfsSelection.py` (475 LOC — proficiency allocation buttons, save callback)
- **GemRB behavior (spells):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\LUSpellSelection.py` (713 LOC — spellbook window, memorisation step, bonus learn/memorise tracking)
- **GemRB behavior (skills):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\LUSkillsSelection.py` (449 LOC — thief skill allocation with arrow buttons and scrollbar proxy)
- **GemRB behavior (HLA):** `LUHLASelection.py` — **flagged as not present in BG1 scope** (file absent, BG2/ToB only). HLA step is stubbed out in this PRD.
- **Godot target:** `godot-client/scripts/ui/level_up_panel.gd` — NEW file
- **Godot companion scene:** `godot-client/scenes/level_up_panel.tscn` — NEW scene defining the sub-page stack
- **Integration PRD:** `docs/prd/active/PRD_frontend_character_record_v1.md` (the character record wizard consumer)

**Clean-room rule:** Read all five GemRB files to understand page order, button semantics, and callback chains. Do NOT copy or translate source code. Every GDScript snippet in this PRD is newly written and complies with the ≤15 consecutive word rule against GemRB source.

## 2. Scope

**In scope:**
- Modal wizard with five ordered sub-pages: HP Roll → Skills → Proficiencies → Spells → Summary
- Per-page conditional presence: Skills only if class gets skill points; Proficiencies only if milestone level grants a point; Spells only if caster with new spell slots
- HP roll + reroll on the HP page (single reroll allowed per open, matching BG1 behaviour)
- Proficiency point allocation with per-weapon-type star increments and +/- buttons
- Skill point allocation with per-skill +/- buttons, total-remaining label
- Spell learn + memorise sub-stages (wizard memorisation requires choosing which spells to prepare)
- Summary page showing before/after deltas for HP, THAC0, saves, HLA (stub "not in BG1"), and spell counts
- Confirm step issues a backend command (`level_up` or structured action) that atomically applies all allocations
- Cancel / back step reverts all in-page allocations without touching backend state
- Keyboard navigation: Enter advances, Escape cancels, PageUp/PageDown cycle pages when all inputs valid
- Refresh on `GameState.state_updated` after backend confirm (panel closes itself)

**Out of scope:**
- HLA selection (not present in BG1 scope — stubbed no-op)
- Kit-specific bonus spells beyond existing class bonuses (future PRD)
- Dual-class starting flow (separate PRD `PRD_frontend_dual_class_v1.md`)
- Character creation spell selection (a different consumer of the same spell picker widget — future refactor)
- Animated HP roll dice widget (plain text + reroll button is sufficient for this PRD)
- Sound effects on level up (audio pipeline pending)

## 3. Functional Requirements (FR)

**FR-01:** The level-up panel MUST open only when `GameState.character_sheet.action_eligibility.level_up_available == true`. Opening while ineligible MUST log a warning and return without mutating scene state.

**FR-02:** The panel MUST present a numbered stepper header showing the current sub-page index, total sub-page count (dynamically sized based on which pages apply), and sub-page title. The stepper MUST update whenever the wizard advances or retreats.

**FR-03:** The HP Roll sub-page MUST display: the class name + level being gained, the die size (d6 / d8 / d10 / d12 per class), the Constitution HP bonus, the rolled base value, the effective HP gained (roll + CON bonus, floor 1), a "Reroll" button (enabled exactly once per open), and a "Confirm HP" button that advances to the next relevant sub-page.

**FR-04:** The Skills sub-page MUST render only if `GameState.character_sheet.level_up.skill_points_available > 0`. When rendered, it MUST list every skill key in `GameState.character_sheet.level_up.skill_rows` with a current-value label, a `[-]` button, a `[+]` button, and a remaining-points counter. Buttons MUST respect per-skill caps from the same payload and MUST NOT allow the remaining counter to go negative.

**FR-05:** The Proficiencies sub-page MUST render only if `GameState.character_sheet.level_up.proficiency_points_available > 0`. When rendered, it MUST list each weapon category with its current star count, allow incrementing up to the class cap (single class: 5 stars, multi-class: 2 stars, matching BG1 limits), and track remaining points.

**FR-06:** The Spells sub-page MUST render only if `GameState.character_sheet.level_up.spell_picks` is non-empty. It MUST support two sub-stages: (a) learn — pick spells to add to the spellbook, and (b) memorise — pick which of the known spells to prepare in today's slots. Each stage tracks a "picks remaining" counter per spell level; the advance button is disabled until all counters reach zero.

**FR-07:** The Summary sub-page MUST show a before/after block with: HP (old → new), THAC0 (old → new), each save category (old → new), each spell level's known + memorised count (old → new), and any allocated skill / proficiency changes. An explicit "Confirm Level Up" button MUST issue the backend command.

**FR-08:** Confirming MUST emit `command_requested.emit(command_text)` where `command_text` is `"level_up <pc_id>"`, AND emit `structured_action_requested.emit("level_up", args)` where `args` contains `hp_roll`, `skill_allocations`, `proficiency_allocations`, `spells_learned`, `spells_memorised`, and `accept: true`. The receiving shell routes this to `Backend.runtime_submit_command`.

**FR-09:** Cancel or Escape MUST close the panel without emitting any backend command AND MUST clear in-panel allocation state.

**FR-10:** Back / Previous MUST retreat one sub-page without clearing allocations on the retreated page (allocations persist across back-and-forth navigation within a single open).

**FR-11:** When `GameState.state_updated` fires after a successful confirm, the panel MUST close itself, emit `level_up_completed`, and reset internal state.

**FR-12:** The panel MUST reject attempts to advance past a sub-page while that sub-page has unspent required points (skills, profs, or spells). The Next button MUST be disabled in that case, and the stepper MUST show a "X points remaining" hint.

## 4. Data Structures

Extend `GameState.character_sheet` to expose a nested `level_up` dictionary describing the current pending advancement. The backend `/state` response already populates `character_sheet` per `PRD_frontend_character_record_v1.md §4`; this PRD adds the `level_up` sub-shape. If the backend projection does not yet include `level_up`, the panel MUST show a "Level-up projection pending" error and block confirm until the sibling backend PRD lands.

    character_sheet.level_up: Dictionary
        class_name: String                          # "Fighter", "Mage/Thief", etc.
        from_level: int
        to_level: int
        hit_die: int                                # 6, 8, 10, or 12
        hp_rolled: int                              # server-precomputed initial roll
        hp_reroll_allowed: bool                     # true on first open
        hp_con_bonus: int
        hp_old_max: int
        hp_new_max: int
        thaco_old: int
        thaco_new: int
        saves_old: Dictionary                       # {death, wand, polymorph, breath, spell}
        saves_new: Dictionary
        skill_points_available: int
        skill_rows: Array[Dictionary]               # [{key, label, current, min, max}]
        proficiency_points_available: int
        proficiency_rows: Array[Dictionary]         # [{key, label, current, class_cap}]
        spell_picks: Dictionary                     # {"wizard": {1: {learn: 2, memo: 3, catalog: [...]}}, ...}
        spells_old_known: Dictionary                # {level: count}
        spells_new_known: Dictionary
        hla_available: bool                         # ALWAYS false in BG1 scope (stub)
        hla_picks_remaining: int                    # ALWAYS 0 in BG1 scope

`LevelUpPanelWidget` MUST declare the following constants and enums:

    class_name LevelUpPanelWidget extends PanelContainer

    enum Step { HP_ROLL, SKILLS, PROFICIENCIES, SPELLS, SUMMARY }
    enum SpellStage { LEARN, MEMORISE }

    const HIT_DIE_D6 := 6
    const HIT_DIE_D8 := 8
    const HIT_DIE_D10 := 10
    const HIT_DIE_D12 := 12

    const SINGLE_CLASS_PROF_CAP := 5
    const MULTI_CLASS_PROF_CAP := 2

    const SIGNAL_REFRESH_THROTTLE_MS := 50

    var _active_step: int = Step.HP_ROLL
    var _step_order: Array[int] = []                # computed per open, may skip steps
    var _hp_committed: int = 0
    var _hp_reroll_used: bool = false
    var _skill_allocations: Dictionary = {}
    var _proficiency_allocations: Dictionary = {}
    var _spells_learned: Dictionary = {}
    var _spells_memorised: Dictionary = {}
    var _spell_stage: int = SpellStage.LEARN
    var _pending_pc_id: String = ""

## 5. Public API — methods that MUST exist

The Godot implementation MUST provide every method below. An acceptance test MUST enumerate each name via reflection and fail if any is missing.

    class_name LevelUpPanelWidget extends PanelContainer

    signal command_requested(command_text: String)
    signal structured_action_requested(shortcut: String, args: Dictionary)
    signal level_up_completed(pc_id: String)
    signal level_up_canceled(pc_id: String)
    signal step_changed(step: int, total: int)
    signal hp_roll_updated(rolled: int, reroll_allowed: bool)

    # ---- lifecycle ----
    func _ready() -> void
    func _unhandled_input(event: InputEvent) -> void
    func open_for_pc(pc_id: String) -> bool                              # returns false if ineligible
    func close_panel(reason: String = "") -> void
    func reset_wizard_state() -> void

    # ---- eligibility & computed step list ----
    func can_level_up(pc_id: String) -> bool                              # mirrors LUCommon.CanLevelUp
    func compute_step_order(level_up: Dictionary) -> Array[int]           # returns subset of Step values
    func current_step() -> int
    func current_step_label() -> String
    func current_step_index() -> int
    func total_visible_steps() -> int

    # ---- wizard navigation ----
    func advance_step() -> bool                                           # returns true if advanced
    func go_back() -> bool                                                # returns true if retreated
    func jump_to_step(step: int) -> bool                                  # debugging / automation only
    func is_current_step_valid() -> bool                                  # used to gate Next button
    func validation_hint() -> String                                      # text shown when blocked

    # ---- HP Roll page ----
    func render_hp_page(level_up: Dictionary) -> void
    func roll_hp() -> int                                                 # called once on open
    func reroll_hp() -> int                                               # disabled after first use
    func compute_effective_hp(raw_roll: int, con_bonus: int) -> int
    func hit_die_for_class(class_name: String) -> int

    # ---- Skills page ----
    func render_skills_page(level_up: Dictionary) -> void
    func increase_skill(skill_key: String) -> bool
    func decrease_skill(skill_key: String) -> bool
    func skill_points_remaining() -> int
    func skill_allocation(skill_key: String) -> int

    # ---- Proficiencies page ----
    func render_proficiencies_page(level_up: Dictionary) -> void
    func increase_proficiency(prof_key: String) -> bool
    func decrease_proficiency(prof_key: String) -> bool
    func proficiency_points_remaining() -> int
    func proficiency_allocation(prof_key: String) -> int
    func proficiency_cap_for(prof_key: String) -> int

    # ---- Spells page ----
    func render_spells_page(level_up: Dictionary) -> void
    func set_spell_stage(stage: int) -> void
    func current_spell_stage() -> int
    func toggle_spell_learn(spell_level: int, spell_id: String) -> bool
    func toggle_spell_memorise(spell_level: int, spell_id: String) -> bool
    func spell_learn_picks_remaining(spell_level: int) -> int
    func spell_memorise_picks_remaining(spell_level: int) -> int
    func all_spell_picks_satisfied() -> bool

    # ---- HLA page (BG1 stub) ----
    func render_hla_page(level_up: Dictionary) -> void                    # no-op, always skipped in BG1

    # ---- Summary page ----
    func render_summary_page(level_up: Dictionary) -> void
    func compute_summary_deltas(level_up: Dictionary) -> Dictionary

    # ---- Confirm / commit ----
    func confirm_level_up() -> bool                                       # emits command_requested + structured_action_requested
    func build_structured_payload() -> Dictionary
    func on_command_acknowledged(response: Variant) -> void

    # ---- GameState integration ----
    func sync_from_game_state() -> void
    func _on_state_updated() -> void

The widget is self-contained; all per-wizard mutation lives in the private vars listed in §4. Outputs flow through signals only.

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** Calling `open_for_pc("pc_main")` when `character_sheet.action_eligibility.level_up_available == false` MUST return `false`, the panel MUST remain invisible, and `level_up_panel` MUST NOT emit any signal. Verified by setting eligibility false in a synthetic state and spying on signal emissions.

**AC-02 [FR-02]:** When the panel opens with a level_up payload that includes HP, Skills, Profs, Spells and Summary, `total_visible_steps()` MUST return 5. When the payload omits skill_points and proficiency_points, `total_visible_steps()` MUST return 3 (HP, Spells, Summary). Verified via reflection on `_step_order`.

**AC-03 [FR-03]:** After `open_for_pc` with a Fighter payload (d10 hit die), `roll_hp()` MUST return a value in `[1, 10]` inclusive. Calling `reroll_hp()` once MUST return a new value and flip `_hp_reroll_used` to `true`. A second `reroll_hp()` call MUST return the cached value and log a warning.

**AC-04 [FR-04]:** For a thief payload with `skill_points_available == 20`, calling `increase_skill("pickpocket")` twenty times MUST succeed. The twenty-first MUST return `false`. `skill_points_remaining()` MUST return 0 after the twentieth call.

**AC-05 [FR-05]:** For a single-class fighter with 1 proficiency point, calling `increase_proficiency("long_sword")` MUST succeed. Calling it five more times (total six) MUST fail on the sixth (hitting the `SINGLE_CLASS_PROF_CAP`). Multi-class payload (multi=true in the level_up dict) MUST cap at 2 stars instead.

**AC-06 [FR-06, FR-12]:** On the Spells sub-page of a mage payload with `spell_picks[1].learn == 2`, attempting `advance_step()` before selecting two level-1 spells MUST return `false` and `validation_hint()` MUST contain "1 points remaining" or similar. After selecting exactly 2 spells, `advance_step()` MUST return `true` and move to the memorise stage or next page.

**AC-07 [FR-07]:** `compute_summary_deltas(level_up)` MUST return a dictionary containing keys `hp_delta`, `thaco_delta`, `saves_delta`, `spells_known_delta`, and `skills_delta`. Verified by asserting dictionary keys against a synthetic payload.

**AC-08 [FR-08]:** Calling `confirm_level_up()` after all steps validate MUST emit `command_requested` with text matching `^level_up [\w_-]+$` AND emit `structured_action_requested` with shortcut `"level_up"` and `args.accept == true`. Spied via test mode.

**AC-09 [FR-09]:** Calling `close_panel("cancel")` MUST emit `level_up_canceled` with the active pc_id AND MUST NOT emit any `command_requested`. Internal allocations MUST reset to empty dictionaries.

**AC-10 [FR-10]:** After allocating on the Skills page then calling `go_back()` to HP and `advance_step()` back to Skills, the previously allocated skill values MUST still be present in `_skill_allocations`.

**AC-11 [FR-11]:** After `confirm_level_up()` emits, simulating a `GameState.state_updated` signal with a reduced-XP-to-next payload MUST cause `close_panel` to be called automatically and `level_up_completed` to emit once.

**AC-12 [method catalog completeness]:** A headless test MUST enumerate every method listed in §5 and every signal (`command_requested`, `structured_action_requested`, `level_up_completed`, `level_up_canceled`, `step_changed`, `hp_roll_updated`) and assert `script.has_method(name) == true` / `script.has_signal(name) == true` for each. Any missing name MUST fail the test with the specific identifier.

**AC-13 [Reflection sanity]:** `script.get_script_constant_map().has("SINGLE_CLASS_PROF_CAP")` MUST return true, and every entry in the `Step` enum MUST appear in `script.get_property_list()` under the enum entry.

## 7. Performance Requirements

- `open_for_pc()` → first paint: **< 80ms** on dev machine (measured via `Time.get_ticks_msec`)
- `render_*_page()` full repaint on step transition: **< 30ms** each
- `advance_step()` / `go_back()` latency: **< 16ms** (one frame)
- `confirm_level_up()` synchronous path (not counting backend round-trip): **< 40ms**
- `sync_from_game_state()` throttled to `SIGNAL_REFRESH_THROTTLE_MS` (50ms) between successive fires to avoid jitter on rapid `state_updated` spam

## 8. Error Handling

- **`level_up` projection missing from `character_sheet`:** Do not crash. Render the HP page with an error banner "Level-up projection pending — backend update required". Disable Confirm. Log once to console: `[level_up_panel] GameState.character_sheet.level_up missing — backend projection required`.
- **Invalid step in `jump_to_step`:** Clamp to `[0, total_visible_steps() - 1]`, log WARNING, return `false`.
- **Backend command failure (response indicates error):** Re-open the panel at the Summary step with the allocations preserved, surface the error via `SessionShellSync.append_narrative_system_text` in red, and do not auto-close.
- **Class with unknown hit die:** Fall back to `HIT_DIE_D8`, log WARNING with the class name.
- **Spell picks counter goes negative due to desync:** Clamp to zero, log WARNING, invalidate the current spell-level row, and disable Next until `sync_from_game_state()` is called again.
- **Proficiency cap lookup unknown:** Treat as `SINGLE_CLASS_PROF_CAP`, log once per unique key.
- **Second reroll attempt:** Return cached HP value, flash a "One reroll per level" hint label, log at DEBUG level.
- **`_unhandled_input` called while not visible:** Early-return to avoid stealing input from other modals.

## 9. Integration Points

**Godot (editable by this PRD):**
- `godot-client/scripts/ui/level_up_panel.gd` — NEW; full widget
- `godot-client/scenes/level_up_panel.tscn` — NEW; sub-page stack with header stepper + footer button row
- `godot-client/tests/automation/godot/test_frontend_level_up.gd` — NEW; acceptance test covering AC-01..AC-13

**Godot (consumed, NOT modified by this PRD):**
- `godot-client/scripts/ui/character_panel.gd` — already has the Level Up button emitting `panel_requested("level_up")`; the session shell routes that to `level_up_panel.open_for_pc(pc_id)`
- `godot-client/autoloads/game_state.gd` — read-only consumer of `character_sheet.level_up`
- `godot-client/autoloads/backend_runtime.gd` — the session shell calls `Backend.runtime_submit_command` after receiving `command_requested`
- `godot-client/scripts/ui/session_shell_sync.gd` — routes `level_up_completed` back to session state reset

**Backend (consumed, NOT modified by this PRD):**
- `/game/campaigns/{id}/command` — existing POST endpoint; this PRD issues `level_up <pc_id>` as both a command string and a structured action
- `/state` response — MUST include `character_sheet.level_up` per §4; if absent, error banner shown per §8

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_frontend_level_up.gd` MUST exercise AC-01 through AC-13 in the same headless run
- Existing `run_headless_tests.gd` MUST remain green
- Coverage goal: **≥80% branch coverage** of `level_up_panel.gd`, including every step of `compute_step_order`, both branches of `reroll_hp`, and all five `render_*_page` entries
- The test MUST use a synthetic `GameState.character_sheet.level_up` payload seeded by the test helper (no live backend call)

## 11. Verification

    # 1. Headless regression
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd

    # 2. New level-up acceptance
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_level_up.gd

    # 3. Method catalog reflection
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_level_up.gd --test-filter="method_catalog"

All three MUST be green. If the backend `level_up` command handler does not yet exist, this PRD is BLOCKED on a sibling backend PRD — raise a dependency note and stop.

## 12. Method catalog — GemRB LevelUp.py + LU* → Godot mapping

The implementation MUST provide Godot equivalents for every GemRB function below. Names may adapt to idiomatic GDScript; responsibilities MUST be covered one-to-one.

### Main shell (must_have)

    # GemRB: LevelUp.OpenLevelUpWindow
    func open_for_pc(pc_id: String) -> bool

    # GemRB: LevelUp.LevelUpDonePress
    func confirm_level_up() -> bool

    # GemRB: LevelUp.LevelUpInfoPress
    func toggle_info_sub_panel() -> void

    # GemRB: LevelUp.GetLevelUpNews (summary text for the info area)
    func build_level_up_news(level_up: Dictionary) -> String

    # GemRB: LevelUp.ReactivateBaseClass (dual-class handling; stubbed in BG1 scope)
    func reactivate_base_class_stub() -> void

### HP helpers (must_have)

    # GemRB: LUCommon.SetupHP
    func compute_hp_delta(level_up: Dictionary) -> int

    # GemRB: dice roll derived from class hit die
    func roll_hit_die(die: int) -> int

    # GemRB: LevelUp.OpenLevelUpWindow → HP redraw branch
    func refresh_hp_labels() -> void

### THAC0 / Saves / Lore (must_have — read-only projection mirrors)

    # GemRB: LUCommon.SetupThaco
    func preview_thaco(level_up: Dictionary) -> int

    # GemRB: LUCommon.SetupSavingThrows
    func preview_saves(level_up: Dictionary) -> Dictionary

    # GemRB: LUCommon.SetupLore
    func preview_lore(level_up: Dictionary) -> int

### Proficiencies (must_have — maps to LUProfsSelection.py)

    # GemRB: LUProfsSelection.SetupProfsWindow
    func setup_proficiencies_sub_page(level_up: Dictionary) -> void

    # GemRB: LUProfsSelection.ProfsRedraw
    func redraw_proficiencies_sub_page() -> void

    # GemRB: LUProfsSelection.ProfsLeftPress / ProfsRightPress
    func on_proficiency_decrement(prof_key: String) -> void
    func on_proficiency_increment(prof_key: String) -> void

    # GemRB: LUProfsSelection.ProfsSave
    func commit_proficiency_allocations() -> Dictionary

    # GemRB: LUProfsSelection.ProfsNullify
    func reset_proficiency_allocations() -> void

### Skills (must_have — maps to LUSkillsSelection.py)

    # GemRB: LUSkillsSelection.SetupSkillsWindow
    func setup_skills_sub_page(level_up: Dictionary) -> void

    # GemRB: LUSkillsSelection.SkillsRedraw
    func redraw_skills_sub_page() -> void

    # GemRB: LUSkillsSelection.SkillIncreasePress / SkillDecreasePress
    func on_skill_increment(skill_key: String) -> void
    func on_skill_decrement(skill_key: String) -> void

    # GemRB: LUSkillsSelection.SkillsSave
    func commit_skill_allocations() -> Dictionary

    # GemRB: LUSkillsSelection.SkillsNullify
    func reset_skill_allocations() -> void

### Spells (must_have — maps to LUSpellSelection.py)

    # GemRB: LUSpellSelection.OpenSpellsWindow
    func setup_spells_sub_page(level_up: Dictionary) -> void

    # GemRB: LUSpellSelection.ShowSpells
    func render_spell_learn_grid(spell_level: int) -> void

    # GemRB: LUSpellSelection.ShowKnownSpells
    func render_spell_memorise_grid(spell_level: int) -> void

    # GemRB: LUSpellSelection.SpellsSelectPress
    func on_spell_learn_pressed(spell_level: int, spell_id: String) -> void

    # GemRB: LUSpellSelection.MemorizePress
    func on_spell_memorise_pressed(spell_level: int, spell_id: String) -> void

    # GemRB: LUSpellSelection.SpellsDonePress
    func commit_spell_selections() -> Dictionary

    # GemRB: LUSpellSelection.SpellsCancelPress
    func cancel_spell_selections() -> void

    # GemRB: LUSpellSelection.MarkButton (visual highlight helper)
    func mark_spell_button(spell_level: int, spell_id: String, selected: bool) -> void

    # GemRB: LUSpellSelection.HasSpecialistSpell
    func has_specialist_spell_for(school: String, spell_level: int) -> bool

    # GemRB: LUSpellSelection.ExtraSpellButtons
    func count_extra_spell_slots(level_up: Dictionary, spell_level: int) -> int

### Eligibility (must_have)

    # GemRB: LUCommon.CanLevelUp
    func can_level_up(pc_id: String) -> bool

    # GemRB: LUCommon.GetNextLevelExp
    func get_next_level_exp(pc_id: String, class_name: String) -> int

    # GemRB: LUCommon.GetLevelDiff
    func get_level_diff(pc_id: String) -> Dictionary

## 13. Implementation notes (non-binding)

- Use a `PanelContainer` root with a `VBoxContainer` child holding the stepper header, a `Control` sub-page host, and a footer `HBoxContainer` with Back / Next / Cancel buttons. Swap sub-page scenes into the host via `add_child` + `queue_free`.
- Keep every allocation dictionary keyed by the same string keys as the backend payload — this lets `build_structured_payload` be a shallow copy.
- HP roll uses Godot's `randi_range(1, die)`. Seed with `RandomNumberGenerator` scoped to the panel so headless tests can fix the seed.
- The spell memorise sub-stage MUST reuse `render_spells_page` with `_spell_stage = SpellStage.MEMORISE`, not a separate page.
- Do not wire `Backend` calls directly from this widget — emit signals and let `game_session.gd` route them.
- Throttle `_on_state_updated` using `Time.get_ticks_msec()` deltas to honour the 50ms requirement.

## 14. Forbidden (restated for reviewers)

- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

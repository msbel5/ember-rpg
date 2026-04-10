# PRD: Frontend Action Bar — BG1 12-Button Action Bar + Modes
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the BG1 action bar — a horizontal strip of 12 context-sensitive buttons whose contents depend on who is selected and what "action level" is active (standard, quick weapon, quick spell, quick item, innate, song, modal, formation). This is the player's primary verb input during exploration and combat. GemRB's `ActionsWindow.py` (700+ LOC in the shared module alone) implements this via an action-level state machine with icon lookup tables and button configuration helpers.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\ActionsWindow.py`, plus `GUICommonWindows.py` for common button wiring, and `ie_action.py` for action constants (ACT_TALK, ACT_ATTACK, ACT_STOP, ACT_DEFEND, ACT_CAST, etc.)
- **GemRB modal state:** `ie_modal.py`
- **Godot targets:**
  - Primary: `godot-client/scripts/ui/instrument_rail.gd` (extend to host action bar slots)
  - New helper: `godot-client/scripts/ui/action_bar.gd` (NEW, owned by the widget)
  - Combat variant: `godot-client/scripts/ui/combat_overlay.gd` (already exists; action bar integrates)

**Clean-room rule:** Read `ActionsWindow.py` method-by-method to extract the action-level state machine. Do NOT port Python — reimplement in GDScript independently.

## 2. Scope

**In scope:**
- 12-button action bar with icon + tooltip + hotkey per slot
- Action level state machine: `UAW_STANDARD`, `UAW_QWEAPONS`, `UAW_QSPELLS`, `UAW_QITEMS`, `UAW_INNATE`, `UAW_SONGS`, `UAW_MODAL`, `UAW_FORMATION`, `UAW_EQUIPMENT`
- Button population based on selected PC's class, equipped items, memorized spells, known abilities
- Formation selection sub-mode (5 preset formation buttons)
- Ammo/ability sub-mode for ranged weapons
- Quick-slot item bindings (F1..F12 or 1..9 keys)
- Group-control mode when multiple PCs are selected (attack, defend, stop, talk)

**Out of scope:**
- Combat turn resolution (backend kernel)
- Spell selection UI (separate `PRD_frontend_mage_spellbook_v1`)
- Item management (inventory PRD)
- The clock button itself (separate `PRD_frontend_clock_widget_v1`)

## 3. Functional Requirements (FR)

**FR-01:** The action bar MUST render exactly 12 button slots. Each slot MUST support: icon texture, tooltip text, disabled state, hotkey binding (F1..F12 by default), press handler, right-press handler.

**FR-02:** The widget MUST expose an `ActionLevel` enum with all 9 values listed in §2. A state transition MUST emit `action_level_changed(level: int)`.

**FR-03:** When `action_level == UAW_STANDARD` and a single PC is selected, the 12 buttons MUST show the PC's standard actions: attack, cast, talk, inventory, character, map, journal, pickpocket (if thief), stealth (if thief), search, modal toggle, formation.

**FR-04:** When `action_level == UAW_STANDARD` and multiple PCs are selected (group select), the bar MUST show group actions via `group_controls()`: talk (BG2-style) or defend (BG1-style) on button 0, attack on 1, stop on 2, and formation presets on 7..11.

**FR-05:** Clicking an ammo-firing weapon's quick slot MUST transition to `UAW_QWEAPONS` mode showing up to 4 ammo types from the PC's quiver. Clicking an ammo button selects it as current ammo and transitions back to `UAW_STANDARD`.

**FR-06:** Clicking the Cast button MUST transition to `UAW_QSPELLS` showing memorized spells. Clicking a spell MUST set the current `TargetMode = CAST` on the exploration view (see `PRD_frontend_exploration_view_v1`), then return to `UAW_STANDARD`.

**FR-07:** Clicking the Formation button MUST transition to `UAW_FORMATION` showing 5 formation preset buttons. Selecting one calls backend `set_formation <formation_index>`.

**FR-08:** Each button MUST have a hotkey. The action bar MUST reserve F1..F12 by default for the 12 slots in `UAW_STANDARD`. Hotkeys MUST be reconfigurable via a keybindings map.

**FR-09:** When the currently selected PC is dead, unconscious, or in a helpless state, the widget MUST disable all buttons except those allowed by class (e.g. thief can still use stealth if sleeping? no — hard disable).

**FR-10:** The widget MUST refresh on `GameState.selected_party_ids_changed` and `GameState.state_updated`.

## 4. Data Structures

    class_name ActionBarWidget extends Control
    
    enum ActionLevel {
        UAW_STANDARD,
        UAW_QWEAPONS,
        UAW_QSPELLS,
        UAW_QITEMS,
        UAW_INNATE,
        UAW_SONGS,
        UAW_MODAL,
        UAW_FORMATION,
        UAW_EQUIPMENT,
    }
    
    const GUIBT_COUNT := 12                  # buttons per bar (matches GemRB)
    const FORMATION_PRESETS := 5             # number of formation preset slots
    
    var _action_level: int = ActionLevel.UAW_STANDARD
    var _buttons: Array[Button] = []         # 12 button nodes
    var _hotkey_map: Dictionary = {}         # slot_index → KEY_F1 etc
    var _active_pc_id: String = ""           # currently primary-selected PC
    var _group_selected: bool = false        # true if multiple PCs selected
    var _return_to_level: int = ActionLevel.UAW_STANDARD  # used by sub-mode exit

## 5. Public API — methods that MUST exist

    # ---- construction ----
    func _ready() -> void
    func _input(event: InputEvent) -> void                                       # hotkey handling
    
    # ---- action level state ----
    func set_action_level(level: int) -> void
    func get_action_level() -> int
    func push_action_level(new_level: int) -> void                               # stores _return_to_level
    func pop_action_level() -> void                                              # returns to _return_to_level
    signal action_level_changed(level: int)
    
    # ---- population / refresh ----
    func update_actions_window() -> void                                         # main refresh — called by GameState signals
    func empty_controls() -> void                                                # hide all 12 buttons
    func group_controls() -> void                                                # populate for multi-PC group selection
    func standard_controls_for(pc_id: String) -> void                            # populate for a single PC
    
    # ---- button helpers ----
    func set_button_icon(slot: int, action_id: int, button_index: int) -> void
    func set_button_action(slot: int, action_id: int, press_handler: Callable, right_press_handler: Callable = Callable()) -> void
    func set_button_disabled(slot: int, disabled: bool) -> void
    func set_button_tooltip(slot: int, tooltip: String) -> void
    func set_button_hotkey(slot: int, key_scancode: int) -> void
    
    # ---- formation ----
    func setup_formation(origin_slot: int) -> void                               # enters UAW_FORMATION
    func select_formation(formation_index: int) -> void                          # slot click
    func select_formation_preset(orig_slot_index: int) -> void                   # right-click to set preset
    
    # ---- quick weapons / ammo ----
    func select_quiver_slot() -> void                                            # equip chosen ammo
    func select_item_ability() -> void                                           # pick a specific ability on an item
    func setup_item_abilities(pc_id: String, slot: int, only_ammo: bool = false) -> void
    
    # ---- quick slots (global hotkeys F1..F12 per PC) ----
    func setup_quick_items_for(pc_id: String) -> void
    func setup_quick_spells_for(pc_id: String) -> void
    func setup_quick_weapons_for(pc_id: String) -> void
    func setup_quick_abilities_for(pc_id: String) -> void
    func setup_songs_for(pc_id: String) -> void                                  # bards
    
    # ---- modal state (stealth, bard song, turn undead, etc) ----
    func toggle_modal(pc_id: String, modal_type: int) -> void
    func is_in_modal(pc_id: String, modal_type: int) -> bool
    
    # ---- routing ----
    signal command_requested(command_text: String)
    signal structured_action_requested(shortcut: String, args: Dictionary)
    signal target_mode_request(mode: int, source_pc_id: String)                  # routes to WorldViewWidget.set_target_mode
    
    # ---- utilities ----
    func get_action_icon_atlas() -> Texture2D                                    # cached icon atlas
    func action_id_to_icon_name(action_id: int) -> String                        # ACT_TALK → "act_talk.png"
    func action_id_to_tooltip(action_id: int) -> String

Action constants (port the numeric values from GemRB's `ie_action.py` without copying code):

    const ACT_TALK := 0
    const ACT_ATTACK := 1
    const ACT_DEFEND := 2
    const ACT_CAST := 3
    const ACT_USE := 4
    const ACT_STOP := 5
    const ACT_QWEAPON := 6
    const ACT_QSPELL := 7
    const ACT_QITEM := 8
    const ACT_INNATE := 9
    const ACT_SONG := 10
    const ACT_FORMATION := 11
    const ACT_INVENTORY := 12
    const ACT_CHARACTER := 13
    const ACT_MAP := 14
    const ACT_JOURNAL := 15
    const ACT_SEARCH := 16
    const ACT_STEALTH := 17
    const ACT_THIEVING := 18
    # (verify full list from ie_action.py; extend as needed)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** The action bar renders exactly 12 buttons. Verified by `_buttons.size() == 12` after `_ready()`.

**AC-02 [FR-02]:** The `ActionLevel` enum has exactly 9 values. Calling `set_action_level(ActionLevel.UAW_QSPELLS)` then `get_action_level()` returns `ActionLevel.UAW_QSPELLS` and `action_level_changed` was emitted once.

**AC-03 [FR-03]:** Given a single PC selected, calling `update_actions_window()` populates slots 0..N with non-empty icons. Verified by checking each button's `icon != null`.

**AC-04 [FR-04]:** With 2+ PCs selected, `update_actions_window()` routes through `group_controls()` which places the defend/talk/stop/formation icons on the expected slots.

**AC-05 [FR-07]:** Calling `setup_formation(11)` (slot 11) transitions to `UAW_FORMATION`. Clicking slot 2 (formation preset index 2) MUST emit `command_requested("set_formation 2")` and return to `UAW_STANDARD`.

**AC-06 [FR-08]:** Pressing F3 (via automation bridge) when `UAW_STANDARD` is active MUST activate button slot 2's press handler. Verified by spying on the press signal.

**AC-07 [FR-09]:** When the selected PC's HP is 0, all 12 buttons MUST be disabled. Verified by iterating `_buttons[*].disabled == true`.

**AC-08 [public API existence]:** Every method listed in §5 MUST exist on the `action_bar.gd` script. Verified by reflection test.

**AC-09 [FR-10]:** When `GameState.state_updated` emits, `update_actions_window()` MUST be called at most once per tick (debounce). Verified by a test that fires the signal 3 times in the same frame and counts invocations.

**AC-10 [structured action routing]:** Clicking the Cast button (ACT_CAST) emits `target_mode_request(TargetMode.CAST, active_pc_id)`. The exploration view picks this up and sets its target mode. Verified by a mock connected to the signal.

## 7. Performance Requirements

- `update_actions_window()` end-to-end: **< 10ms** for a full repopulation
- Hotkey response latency: **< 50ms** from key press to signal emission
- Icon atlas load: one-time on `_ready()`, cached after first load

## 8. Error Handling

- Unknown `action_id` in `set_button_icon`: render a placeholder "?" icon, log once at WARNING
- Missing icon asset: fallback to a generic action icon, log once
- Invalid `action_level` in `set_action_level`: clamp to `UAW_STANDARD`, log at WARNING
- PC not found for `active_pc_id`: call `empty_controls()`, log at DEBUG

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/action_bar.gd` — NEW
- `godot-client/scenes/action_bar.tscn` — NEW scene
- `godot-client/scripts/ui/instrument_rail.gd` — host the action bar as a child widget; wire its signals
- `godot-client/scripts/ui/combat_overlay.gd` — show the combat-mode variant of the action bar during combat turns
- `godot-client/tests/automation/godot/test_frontend_action_bar.gd` — NEW

**Backend (consumed, NOT modified):**
- `/game/campaigns/{id}/command` — issues `attack`, `cast <spell_ref>`, `talk`, `stealth`, `search`, `set_formation <n>`, `use_quick_slot <n>`, `stop`
- `GameState.party_members` — source for selected PC detection
- `GameState.character_sheet` — for class-based action filtering

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No GemRB code port

## 10. Test Coverage Target

- `test_frontend_action_bar.gd` MUST cover AC-01..AC-10
- ≥80% branch coverage on `action_bar.gd`
- `run_headless_tests.gd` stays green

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_action_bar.gd

## 12. Implementation notes

- Icon atlas: generate a single texture with all action icons; use `atlas_region` per button for perf.
- Hotkeys route through `_input()` not `_unhandled_input()` so the action bar takes priority over world scroll.
- The `push_action_level` / `pop_action_level` stack should be depth-1 only in Phase 2 — full nesting is not needed yet.

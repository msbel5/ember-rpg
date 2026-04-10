# PRD: Frontend Inventory — BG1 Paper Doll + Backpack + Ground
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify a BG1-fidelity inventory screen for the Godot client. The feature shall render a paper-doll with equipment slots, a scrollable backpack grid, a ground-items row, drag-drop between all regions, right-click item info, and a live HUD (name, class, HP, AC, encumbrance, gold, clothing color pickers). This replaces the current stub `inventory_panel.gd` which shows items as flat text buttons and does not support equipping, dropping, or examining by right-click.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\bg1\GUIINV.py` (243 LOC — window init, refresh, ground-item scrollbar, paper doll color pickers, slot iteration)
- **GemRB behavior (shared):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\InventoryCommon.py` (1165 LOC — drag-drop handlers, slot update, item info windows, amount windows)
- **GemRB behavior (paper doll):** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\GUIScripts\PaperDoll.py` (400 LOC — paper-doll rendering, color stats, equipment setup)
- **Godot target:** `godot-client/scripts/ui/inventory_panel.gd` (currently ~80 LOC stub; to be rewritten)
- **Godot companion:** `godot-client/scripts/ui/inventory_panel.tscn` scene (to be created with the layout described in §4)

**Clean-room rule:** Read the GemRB files to understand behavior. Do not copy or translate their code. All GDScript in this PRD's implementation is newly written.

## 2. Scope

**In scope:**
- Inventory panel layout: left paper doll + equipment slots, center backpack grid, bottom ground row, top HUD header
- Drag-drop between equipment slots, backpack, and ground
- Right-click → item info modal; double-click → use/consume; shift-click → stack-split modal
- Ground-items scrollbar (5 visible, scroll for more)
- Live refresh on `GameState.state_updated` and `GameState.inventory_updated` signals
- Tooltip-on-hover showing name + short description + encumbrance weight
- Major/minor color pickers (cosmetic; map to a future avatar color system — OK to no-op for now but wire the signal)

**Out of scope:**
- Drag-drop between multiple party members simultaneously (requires party portraits wiring — separate PRD)
- Paper-doll rendering of actual equipment sprites (art pipeline work — PRD_frontend_paper_doll_art_v1 later)
- Item comparison tooltips (hover over equipped item vs unequipped — Phase 3)
- Item enchanting, crafting, or identification UI

## 3. Functional Requirements (FR)

**FR-01:** The inventory panel MUST render a layout that visually divides the screen into four regions — (a) header HUD, (b) paper-doll + equipment slots, (c) backpack grid, (d) ground items row — matching the BG1 spatial arrangement (HUD top, paper-doll left, backpack right, ground bottom).

**FR-02:** The header HUD MUST display: character name, class/kit title, current HP, max HP, AC, party gold, encumbrance (current/max weight), and two clothing-color swatches (major/minor).

**FR-03:** The paper-doll region MUST show at least the following equipment slot categories, each as a distinct drop target with a slot-type icon when empty:
- Head / Helmet
- Neck / Amulet
- Body / Armor
- Cloak
- Rings (×2)
- Belt
- Gauntlets / Bracers
- Boots
- Weapon main hand
- Weapon off-hand (or shield)
- Quiver (×3 for ammo stacks)
- Quick weapons (×2..4 visible as hotbar)

**FR-04:** The backpack grid MUST render the character's carried items as a grid of uniform slots. Each slot shows icon, stack count (if > 1), and a hover tooltip with name + one-line description.

**FR-05:** The ground row MUST render the top-of-stack 5 items present at the player's current tile, with a horizontal scrollbar exposing the rest. Ground items come from `GameState.ground_items`.

**FR-06:** Clicking (left, default mouse button) on an item in the backpack or ground row MUST initiate a drag operation. Releasing over a valid equipment slot MUST attempt to equip (issuing `equip <item_id> <slot_id>` as a campaign command). Releasing over the ground row MUST drop (issuing `drop <item_id> [quantity]`). Releasing over the backpack from a ground slot MUST pick up (`pickup <item_id> [quantity]`). Releasing over an invalid target MUST return the item to its origin without issuing a command.

**FR-07:** Right-click on any item MUST open an item info modal showing: name, full description, damage/armor/speed stats (as relevant), value in gold, weight, enchantment level, usability by current class/alignment.

**FR-08:** Shift-click on a stackable item MUST open a stack-amount modal where the player selects a quantity to split off into a new stack in the first free backpack slot.

**FR-09:** Double-click on a usable item (potion, scroll, wand, consumable) MUST issue `use <item_id>` as a campaign command.

**FR-10:** The panel MUST refresh on any of these signals: `GameState.state_updated`, `GameState.inventory_updated`, `GameState.character_sheet_updated`. Refresh MUST be idempotent and not leak Godot nodes.

**FR-11:** When the backend response indicates a command error (e.g. "cannot equip: class restriction"), the panel MUST surface the error via the existing `narrative_panel` system-text channel. Do not crash.

## 4. Data Structures

Extend `GameState` (if not already present) to expose:

    GameState.equipped_slots: Dictionary
        # Shape: {slot_id: {item_id: String, quantity: int, durability: int}}
        # Keys: "head", "neck", "armor", "cloak", "ring_left", "ring_right",
        #       "belt", "gauntlets", "boots", "weapon_main", "weapon_off",
        #       "quiver_1", "quiver_2", "quiver_3", "quick_1", "quick_2"
    
    GameState.ground_items: Array[Dictionary]
        # Each: {item_id, name, quantity, icon_slug, weight, value}
        # Populated from backend /state response "ground_items" field
        # (already exists per response_normalizer.gd:174)
    
    GameState.inventory_items: Array[Dictionary]
        # Already exists; each entry: {item_id, name, quantity, icon_slug, ...}

No new backend endpoints. If `equipped_slots` is not already projected by the backend, this PRD depends on a sibling backend PRD and must NOT proceed until that lands.

## 5. Public API

Extend `inventory_panel.gd` with:

    class_name InventoryPanelWidget
    
    signal command_requested(command_text: String)
    signal item_info_requested(item_entry: Dictionary)
    signal stack_split_requested(item_entry: Dictionary)
    
    func refresh() -> void                   # Full repaint from GameState
    func focus_slot(slot_id: String) -> bool # Called by automation bridge / hotkey
    func begin_drag(item_entry: Dictionary, source_region: String) -> void
    func handle_drop(source_region: String, target_region: String, target_slot: String) -> bool

Do not introduce autoloads. Keep the widget self-contained; all state comes from `GameState`.

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01, FR-02]:** When the inventory panel is opened in the game session, the automation bridge's `query_state` on the panel root reports `node_visible: true` AND the header label contains the character name from `GameState.player.name`.

**AC-02 [FR-03]:** When the inventory panel is opened, at least 10 distinct slot nodes exist under the paper-doll region, each with a unique `name` corresponding to one of the slot categories in FR-03. This is checked by enumerating children via `query_state` from the automation bridge.

**AC-03 [FR-04]:** When `GameState.inventory_items` contains ≥1 entry, the backpack grid renders at least that many buttons, each with a non-empty `text` or `tooltip_text`.

**AC-04 [FR-05]:** When `GameState.ground_items` contains ≥1 entry, the ground row renders at least one button whose tooltip matches the item name. When `ground_items` has more than 5 entries, a scrollbar node is present under the ground row.

**AC-05 [FR-06]:** When the automation bridge issues a simulated `left_click_drag` from a backpack item to the weapon-main equipment slot, the `command_requested` signal emits a string matching `^equip [\w_-]+ weapon_main$`. Verified via a test-mode spy added to the panel that captures emitted commands.

**AC-06 [FR-07]:** When the automation bridge issues a simulated right-click on a backpack item, the `item_info_requested` signal emits once with a dictionary containing `name`, `description`, and `value` keys.

**AC-07 [FR-10]:** When `GameState.state_updated` fires twice in rapid succession (simulated), the panel's child-node count MUST remain stable (within ±0 of the expected count), proving no leaks. Verified by a headless Godot test.

**AC-08 [FR-11]:** When the backend command response indicates an error string, the narrative panel MUST receive an `append_system_text` call with that error message colored red. Verified by injecting a synthetic error response into GameState and spying on `SessionShellSync.append_narrative_system_text`.

## 7. Performance Requirements

- Full `refresh()` on a 40-item inventory: **< 50ms** on a dev machine (measured via Time.get_ticks_msec delta around the call).
- Drag-drop visual feedback latency from mouse-move to item ghost position: **< 16ms** (one frame at 60Hz).
- Panel open/close transition: **< 100ms** total (including fade-in if present).

## 8. Error Handling

- **Missing `GameState.equipped_slots`:** If the backend hasn't been updated to project equipped slots yet, the paper-doll region MUST render empty slots with a tooltip "Backend projection pending" and NOT crash. Log once to console: `[inventory_panel] equipped_slots missing from GameState — backend projection required`.
- **Invalid drag-drop target:** Return item to origin, play a "nope" UI sound (or no-op if audio is not wired), show a 1-second toast "Can't put that there".
- **Backend command error:** See FR-11. Log to narrative panel with red color. Do not retry automatically.
- **Icon not found for item:** Fall back to a generic "unknown item" icon. Log once per unique missing slug to avoid log spam.
- **Scrollbar position out of range:** Clamp to `[0, max(0, ground_items.size() - 5)]`.

## 9. Integration Points

**Godot (editable by this PRD):**
- `godot-client/scripts/ui/inventory_panel.gd` — rewrite
- `godot-client/scenes/inventory_panel.tscn` — NEW scene file defining the layout described in §4
- `godot-client/autoloads/game_state.gd` — extend with `equipped_slots` Dictionary if not present
- `godot-client/tests/automation/godot/test_frontend_inventory.gd` — NEW headless acceptance test covering AC-01..AC-08
- `godot-client/scripts/ui/inventory_item_info_modal.gd` — NEW; small modal showing item detail on right-click
- `godot-client/scripts/ui/inventory_stack_split_modal.gd` — NEW; amount picker on shift-click

**Backend (consumed, NOT modified by this PRD):**
- `/game/campaigns/{id}/command` — existing POST endpoint; this PRD issues `equip`, `unequip`, `drop`, `pickup`, `use`, `examine_item`, `split_stack`, `combine_stack` shortcuts
- `/state` response — MUST contain `equipped_slots` in the campaign projection. If it does not yet, this PRD is BLOCKED and must file a dependency note on `PRD_item_system_kernel_v1.md` before proceeding

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No edits to any other PRD file
- No new backend endpoints
- No new autoloads
- No direct HTTP calls from `inventory_panel.gd` — go through `Backend` autoload only
- No GemRB code reuse (clean-room rule — see PRD_frontend_extraction_index_v1.md §1)

## 10. Test Coverage Target

- `test_frontend_inventory.gd` MUST exercise AC-01 through AC-08 in order in a single run.
- Existing `run_headless_tests.gd` MUST stay green.
- Coverage goal: ≥80% of branches in `inventory_panel.gd` exercised by the new test. Measured via `godot --headless --coverage` if the coverage harness is available, otherwise via manual inspection.

## 11. Verification

    # 1. Headless regression
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    
    # 2. New inventory acceptance
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_inventory.gd
    
    # 3. Backend sanity (spot check equip/drop/pickup shortcuts exist)
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_campaign_api_v2.py -q -k "equip or drop or pickup"

All three MUST be green. If the backend shortcut spot check is red, escalate to the kernel team before proceeding — this PRD is front-end only.

## 12. Method catalog — GemRB InventoryCommon.py → Godot mapping

The implementation MUST provide Godot equivalents for every GemRB function listed below. These are extracted from `gemrb/GUIScripts/InventoryCommon.py` (1165 LOC) and `gemrb/GUIScripts/bg1/GUIINV.py` (243 LOC). The Godot method names MAY differ slightly for idiomatic GDScript but MUST cover the same responsibilities. The acceptance test MUST enumerate every `must_have` method via reflection.

### Window lifecycle (must_have)

    # GemRB: InitInventoryWindow(Window), UpdateInventoryWindow(Window), RefreshInventoryWindow(Window)
    func init_inventory_panel() -> void                              # one-time wiring on _ready
    func update_inventory_panel() -> void                            # full refresh + scroll reset (on panel open)
    func refresh_inventory_panel() -> void                           # partial refresh without scroll reset (on state change)
    
    # GemRB: InventoryClosed(win)
    func on_inventory_closed() -> void                               # drop currently-held item on close; fallback to ground

### Slot rendering (must_have)

    # GemRB: UpdateSlot(pc, slot)
    func update_slot(pc_id: String, slot_index: int) -> void
    
    # GemRB: UpdateInventorySlot(pc, Button, Slot, slot_type)
    func update_inventory_slot(pc_id: String, button: Control, slot: Dictionary, slot_type: String) -> void

### Drag-drop (must_have)

    # GemRB: OnDragItem(btn)
    func on_drag_item(btn_id: int) -> void                           # pickup OR place OR swap
    
    # GemRB: OnDragItemGround(btn)
    func on_drag_item_ground(btn_id: int) -> void                    # ground-slot specific
    
    # GemRB: OnAutoEquip()
    func on_auto_equip() -> void                                     # drop to -1 (any equipable), failure plays GAM_47
    
    # GemRB: MouseEnterSlot, MouseLeaveSlot (hover tooltip)
    func on_mouse_enter_slot(btn_id: int) -> void
    func on_mouse_leave_slot(btn_id: int) -> void
    func on_mouse_enter_ground(btn_id: int) -> void
    func on_mouse_leave_ground(btn_id: int) -> void

### Item info / amount sub-windows (must_have)

    # GemRB: OpenGroundItemInfoWindow, OpenItemInfoWindow, OpenSlotItemInfoWindow
    func open_item_info_modal(item_entry: Dictionary, source_region: String) -> void
    
    # GemRB: OpenGroundItemAmountWindow, OpenItemAmountWindow
    func open_item_amount_modal(item_entry: Dictionary, source_region: String) -> void
    
    # GemRB: OpenItemIdentifyWindow
    func open_item_identify_modal(item_entry: Dictionary) -> void
    
    # GemRB: OpenItemAbilitiesWindow
    func open_item_abilities_modal(item_entry: Dictionary) -> void

### Paper doll (must_have)

    # GemRB: PaperDoll.SetupEquipment(pc, button, size, stats)
    func setup_paper_doll_equipment(pc_id: String, body_node: Control, size: String, stats: Dictionary) -> void
    
    # GemRB: PaperDoll.GetActorPaperDoll(pc)
    func get_actor_paper_doll_slug(pc_id: String) -> String
    
    # GemRB: PaperDoll.ColorStatsFromPC(pc)
    func color_stats_from_pc(pc_id: String) -> Dictionary             # {major_color, minor_color, skin_color, hair_color}
    
    # GemRB: PaperDoll.SelectPickerColor(stat_id)
    func open_color_picker(stat_id: String) -> void                   # opens major/minor color picker modal

### Stack split (must_have)

    # GemRB: DragItemAmount window handling
    func split_stack(source_slot: int, amount: int) -> void
    func combine_stack(source_slot: int, target_slot: int) -> void

### Identification & usability (must_have)

    # GemRB: CheckItemUsability(pc, item)
    func check_item_usability(pc_id: String, item_entry: Dictionary) -> Dictionary
        # returns {usable: bool, reason: String, class_restricted: bool, alignment_restricted: bool}
    
    # GemRB: IdentifyItem (from the lore skill)
    func try_identify_item(pc_id: String, item_entry: Dictionary) -> bool

### Container interactions (must_have for in-area chests/bodies)

    # GemRB: EnterStore + ChangeStoreItem pattern for containers
    func enter_container(container_id: String) -> void
    func leave_container() -> void
    func transfer_from_container(container_id: String, item_entry: Dictionary, amount: int) -> bool
    func transfer_to_container(container_id: String, item_entry: Dictionary, amount: int) -> bool

### Encumbrance (must_have — read-only projection, no mutation)

    # GemRB: SetEncumbranceLabels(Window, light_label_id, heavy_label_id, pc)
    func update_encumbrance_labels() -> void                         # reads GameState.player.encumbrance

### Class restrictions (BG1-specific)

    # GemRB: BG2-style monk offhand check; class-based armor restrictions
    func is_armor_allowed(pc_class: int, armor_type: String) -> bool
    func is_weapon_allowed(pc_class: int, weapon_type: String) -> bool

### Reflection acceptance criterion

**AC-11 [method catalog completeness]:** A headless test MUST enumerate every method listed in §5 AND §12 and assert `script.has_method(name) == true` for each. If any is missing, the test fails with the specific name. This is the bright-line test that Copilot CLI has implemented the full method surface.

## 13. Out-of-band: the paper-doll art question

BG1's paper-doll renders actual equipment over a body sprite tinted by major/minor colors. The ember-rpg art pipeline does not yet have per-item paper-doll overlays. For this PRD, render the paper-doll as a **body sprite with colored tint** only (no equipment overlays); equipped items appear only in the slot icons around the body, not on the body itself. A later PRD (`PRD_frontend_paper_doll_art_v1`) will add overlay sprites once the art pipeline supports them. This limitation MUST be stated in §8 of the implementation's code comments and the acceptance test MUST NOT require overlay sprites.

# PRD: Gameplay UX V1 — Playable Colony-Commander Interface
**Project:** Ember RPG
**Phase:** 0
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-02
**Status:** Draft

---

## 1. Purpose

Define the complete gameplay interface for the Avatar-Commander hybrid: a player who is both a colony manager (RimWorld-style oversight) and an avatar explorer (Baldur's Gate-style adventurer). The current gameplay shell now has bounded play-validation for click-to-walk, semantic interaction, dialog, travel, combat entry, save/load, and sidebar hydration. The remaining gap is not basic operability; it is consistency, clarity, and visual polish across those already-wired systems.

Reference: Baldur's Gate 2 (bottom action bar, right portraits, left mode buttons, click-to-walk with pathfinding), RimWorld (colony overview, job assignment, resource bars), Fallout 1/2 (dialog with visible options and skill checks).

## 2. Scope

### In scope
- Click-to-walk movement with animated pathfinding
- Right-click context menus for entities and ground
- Dialog overlay (Fallout-style: NPC portrait + text + player options with skill checks)
- Map camera: edge scroll, WASD pan, wheel zoom, middle-mouse drag
- World map travel (sidebar Map tab with clickable destinations)
- Top status bar (location, time, weather, gold, HP)
- Action bar with context-sensitive buttons (explore/combat/dialog modes)
- Inventory/equipment paperdoll (BG2-style)
- Combat overlay with turn order and action buttons
- Settlement management panel improvements
- Entity rendering: name labels, distinction, correct positions

### Out of scope
- Asset creation (sprites, portraits, animations)
- Audio/music system
- Multiplayer
- Mobile/touch input

## 3. Functional Requirements (FR)

### A. Movement & Camera

**FR-01 (Click-to-Walk):** Left-clicking an empty ground tile pathfinds from player position to clicked tile using A* (from `pathfinding_algorithms.py`). The player sprite walks tile-by-tile with 0.24s per tile animation (existing `MOVE_TWEEN_DURATION`). Path shown as dotted gold line on hover before click. Walking can be interrupted by: right-click (stop), combat trigger, reaching destination.

**FR-02 (Walk-Then-Interact):** Left-clicking an entity that is more than 1 tile away: first pathfind to an adjacent tile, then auto-execute the default interaction (talk for NPCs, examine for items, attack for hostiles). If already adjacent: interact immediately.

**FR-03 (Camera Pan):** Mouse at viewport edges (within 20px of edge) pans the camera at 200px/s. WASD keys pan camera at 300px/s. Middle-mouse-button drag pans camera. Camera is NOT locked to player — player can look around freely. Home key re-centers camera on player.

**FR-04 (Camera Zoom):** Mouse wheel up/down zooms camera. Minimum zoom: 0.5x (zoomed out, see more). Maximum zoom: 2.0x (zoomed in, detail). Default: 1.0x. Zoom centered on mouse position.

**FR-05 (World Tick on Move):** Each tile the player moves, the world ticks once. This triggers: NPC movement, need decay, effect ticks, time advancement. The player FEELS the world is alive because NPCs move, day/night changes, events occur during exploration.

### B. Entity Interaction

**FR-06 (Right-Click Context Menu):** Right-clicking an entity shows a popup menu with available actions:
- NPC: [Talk] [Examine] [Pickpocket] [Attack]
- Enemy: [Attack] [Examine] [Flee]
- Item on ground: [Pick Up] [Examine]
- Furniture: [Examine] [Use]
- Empty ground: [Move Here] [Search Area] [Rest]
Each action sends the corresponding command to backend.

**FR-07 (Entity Name Labels):** Each entity sprite has a name label 8px above it: NPC names in gold, enemy names in red, item names in green, player name in white. Labels visible when zoomed in (>= 0.8x), hidden when zoomed out. Font size: 12px, outline: 1px black for readability.

**FR-08 (Entity Hover Tooltip):** Hovering an entity for 0.3s shows a tooltip panel: name (bold), type, HP bar (if combatant), 1-line status. The tooltip follows the mouse.

**FR-09 (Entity Position Fix):** Entity tile positions from backend MUST map correctly to pixel positions. Formula: `pixel_pos = Vector2(tile_x * TILE_SIZE + TILE_SIZE/2, tile_y * TILE_SIZE + TILE_SIZE/2)`. If an entity reports tile (5, 10) but renders at a different location, the mapping is broken.

**FR-10 (Entity Distinction):** Entities must be visually distinct:
- Player: white/gold sprite, 1.2x size, pulsing gold aura
- NPCs: amber sprite, 1.0x size, subtle idle bob
- Enemies: red sprite, 1.0x size, faster idle animation, red aura
- Items: green sprite, 0.8x size, sparkle effect
- Furniture: brown sprite, 0.9x size, no animation
Bucket tints already exist in entity_layer.gd — verify they're working and increase contrast.

### C. Dialog System UI

**FR-11 (Dialog Overlay):** When talking to an NPC, display a dialog overlay covering the bottom 40% of the world viewport:
```
┌────────────────────────────────────────────────────────────┐
│ [NPC Portrait]  NPC Name                                    │
│                 "Welcome, traveler. The road from the       │
│                  north has been dangerous lately. What       │
│                  brings you to our settlement?"              │
├────────────────────────────────────────────────────────────┤
│ > "I'm looking for work." (always available)                │
│ > "What dangers lurk on the northern road?" (always)        │
│ > [CHA 14] "Perhaps you could offer a discount..." (gray)  │
│ > [STR 16] "I'll clear the road myself." (available)        │
│ > "Goodbye." (always, closes dialog)                        │
└────────────────────────────────────────────────────────────┘
```

**FR-12 (Dialog Options):** Each player dialog option is a full-width clickable button showing:
- Skill check tag if applicable: "[CHA 14]" in gold if met, gray if not met
- Full option text
- Grayed out if requirements not met (but VISIBLE — player sees what they're missing)
- Click or press number key (1-5) to select

**FR-13 (Dialog State):** During dialog: world is paused, camera locked, other entities frozen. Player can only interact with the dialog. Escape closes dialog (sends "Goodbye" equivalent). Dialog history scrollable if conversation is long.

**FR-14 (Dialog Integration):** Backend returns dialog options via command response. The narrative_panel already receives text — extend it to detect dialog mode (when response contains `dialog_options` array) and display the overlay instead of plain text.

### D. Map & Travel

**FR-15 (Map Tab):** The sidebar Map tab shows the world graph (existing minimap_panel.gd). Enhancements:
- Settlement nodes: clickable circles with name labels
- Current location: gold filled circle with pulsing ring
- Reachable destinations: white circles with connecting lines showing travel time
- Unreachable destinations: dark gray circles
- Click a reachable destination: "Travel to [Name]?" confirmation → sends travel command

**FR-16 (Travel Sequence):** When traveling between settlements:
- World viewport fades to dark
- Travel text overlay: "Traveling to [destination]... (3 days journey)"
- Random travel events appear as text: "Day 1: Clear weather. Day 2: You encounter a merchant caravan."
- Arrival: viewport fades back in showing new settlement
- Uses existing `hybrid_runtime.py` travel state machine

### E. Top Status Bar

**FR-17 (Status Bar):** Persistent bar at top of game session:
```
[Settlement: Ironhold] | [Day 14, 2:30 PM] | [Weather: Clear] | [Gold: 250] | [HP: 45/60 ████░░]
```
- Location from `GameState.location`
- Time from backend `game_time`
- Weather from backend `weather`
- Gold from player inventory
- HP as bar with numeric overlay
- Additional: AC, Level shown on hover

### F. Action Bar

**FR-18 (Context-Sensitive Actions):** Bottom action bar changes based on game mode:
- **Exploration mode:** [Attack (A)] [Talk (T)] [Examine (E)] [Use (U)] [Rest (R)] [Save (F5)]
- **Combat mode:** [Attack (A)] [Spell (S)] [Item (I)] [Defend (D)] [Flee (F)]
- **Dialog mode:** Action bar hidden (dialog overlay takes over)
- Each button: icon placeholder + text + hotkey hint
- Text command input field on the right (existing functionality, preserved)

### G. Combat UI

**FR-19 (Combat Overlay):** When combat starts, overlay appears:
- Top: Turn order bar showing all combatants as small portraits/icons, current actor highlighted
- World viewport: selected actor has gold ring, targetable enemies have red rings
- Bottom: Combat action buttons replace exploration buttons
- Attack: click enemy → resolve via `resolve_attack()` → show floating damage number (+3, -15 HP)
- Spell: opens spell list panel → select spell → select target → resolve
- Each attack: attacker sprite tweens toward defender (0.2s), flash on impact, tweens back

**FR-20 (Damage Numbers):** When damage is dealt, a floating number appears above the target: red for damage ("-15"), green for healing ("+8"), gold for XP ("+50 XP"). Number floats upward and fades over 1 second.

**FR-21 (Combat Log):** Combat events appear in the narrative panel with color coding: attacks in red, heals in green, status effects in blue, deaths in dark red.

### H. Inventory & Equipment

**FR-22 (Gear Tab — Paperdoll):** The sidebar Gear tab (currently Items) redesigned:
```
┌──────────── Equipment ─────────────┐
│     [Helmet]                        │
│ [Amulet]  [Armor]  [Cloak]         │
│ [Ring L]  [Shield] [Ring R]         │
│ [Gloves]  [Belt]   [Boots]         │
│ [Weapon 1] [Weapon 2]              │
│ [Quiver]                            │
├──────────── Backpack ──────────────┤
│ [Item][Item][Item][Item]            │
│ [Item][Item][Item][Item]            │
│ [Item][Item][Item][Item]            │
│ [Item][Item][Item][Item]            │
├──────────── Details ───────────────┤
│ Selected: Iron Longsword +1         │
│ Damage: 1d8+3 slashing              │
│ Weight: 4 lbs                       │
│ [Equip] [Drop] [Examine]           │
└─────────────────────────────────────┘
```

**FR-23 (Equip Flow):** Click item in backpack → details panel shows stats. Click [Equip] → item moves to appropriate equipment slot. Click equipped item → [Unequip] returns to backpack. Stat changes preview: "AC: 12 → 15 (+3 from chainmail)".

**FR-24 (Item Interaction):** Right-click item in world → [Pick Up] adds to backpack. Backpack full → "Inventory full" message. Drop item: remove from backpack, appears on ground tile.

### I. Settlement Panel Enhancement

**FR-25 (Colony Overview):** The Town tab shows:
- Population count + mood indicator (emoji-style: content/unhappy/miserable)
- Resource bars: Food, Wood, Stone, Metal, Gold
- Active jobs list with assigned workers
- Alerts: "Food shortage!", "Enemy spotted!", "Mood is low!"
- Quick actions: [Harvest] [Build] [Recruit] [Defend]
- Each action sends a colony management command to backend

## 4. Acceptance Criteria (AC)

AC-01 [FR-01]: Left-click empty tile → player walks tile-by-tile with animation, NOT teleport.
AC-02 [FR-02]: Left-click NPC 5 tiles away → player walks to adjacent tile, THEN auto-talks.
AC-03 [FR-03]: Mouse at right edge of viewport → camera pans right. WASD keys pan camera.
AC-04 [FR-04]: Mouse wheel up → camera zooms in. Mouse wheel down → zooms out.
AC-05 [FR-05]: Each tile moved triggers a world tick (NPCs move, time advances).
AC-06 [FR-06]: Right-click NPC → context menu with [Talk] [Examine] [Attack] appears.
AC-07 [FR-07]: NPCs have gold name labels above sprites, enemies have red labels.
AC-08 [FR-11]: Talking to NPC → dialog overlay appears with NPC text and player options as buttons.
AC-09 [FR-12]: Dialog option with [CHA 14] check shown grayed if player CHA < 14.
AC-10 [FR-15]: Map tab shows world graph with clickable settlement nodes and travel times.
AC-11 [FR-16]: Clicking reachable settlement → travel sequence with text events → arrive at new settlement.
AC-12 [FR-17]: Top status bar shows location, time, weather, gold, HP at all times.
AC-13 [FR-18]: Exploration mode: bottom bar shows Attack/Talk/Examine/Use/Rest buttons with hotkeys.
AC-14 [FR-19]: Combat mode: turn order bar visible, attack click shows floating damage number.
AC-15 [FR-22]: Gear tab shows paperdoll equipment slots + backpack grid + item details.
AC-16 [FR-23]: Click backpack item → click Equip → item appears in equipment slot, stats update.

## 5. Performance Requirements
- Click-to-walk path computation: < 5ms for 80x60 map
- Tile-to-tile animation: exactly 0.24s per tile
- Context menu appearance: < 0.1s after right-click
- Dialog overlay transition: < 0.2s
- Camera pan: 60fps smooth at 200-300 px/s
- Floating damage numbers: 60fps fade animation

## 6. Error Handling
- Path not found: show "Can't reach there" text, no movement
- Entity interaction at range: walk first, then interact (never "too far" error to player)
- Combat action on invalid target: show "Invalid target" text
- Inventory full on pickup: show "Backpack is full" text
- Backend error during dialog: show "Connection lost" in dialog overlay, allow retry

## 7. Integration Points
- **Backend.gd**: submit_campaign_command() for all actions
- **GameState.gd**: state_updated signal drives all panel refreshes
- **pathfinding_algorithms.py**: A* for click-to-walk path computation
- **combat_resolution.py**: resolve_attack() for combat actions
- **dialog.py**: DialogDef for dialog structure
- **items.py**: ItemInstance for equipment management
- **entity_layer.gd**: sprite rendering, name labels, movement animation
- **world_view.gd**: click handling, camera control, context menu

## 8. Test Coverage Target
- Click-to-walk: headless test with path verification
- Context menu: each entity type produces correct menu
- Dialog overlay: text display and option selection
- Camera controls: pan, zoom, edge scroll
- Equipment: equip/unequip item flow
- Combat: attack → damage number display
- Travel: map click → travel sequence → arrival
- Status bar: updates on state change
- All interactions keyboard-accessible

## Changelog
- 2026-04-02: Updated the purpose section to reflect that the shell is now bounded-playable and that the remaining work is polish and UX closure rather than basic feature absence.

# PRD: Frontend Extraction Index — BG1 Clean-Room Reimplementation (Master)
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

This is the **master index** for the frontend PRD family. It enumerates every user-visible screen, panel, overlay, or interaction that GemRB implements for Baldur's Gate 1, maps each to its GemRB reference source AND its existing Godot target, and tracks the child PRD that specifies the clean-room reimplementation.

**Clean-room reimplementation rule:** Child PRDs reference GemRB source files as behavioral specifications only. No GemRB Python or C++ code may be copied, translated line-by-line, or embedded. Each PRD describes what the feature does (read from GemRB), then specifies how it shall behave in Godot terms, independently. GemRB is GPLv2; the ember-rpg frontend must stay independent of that license.

## 2. Scope

**In scope (this index):**
- The full catalog of BG1 frontend features and their PRD slots
- Naming convention, authoring rules, integration contract
- Priority ordering and dependency chain
- Kill-criterion tie-in to PRD_PLAYABILITY_RESCUE.md

**Out of scope (this index):**
- Actual feature specifications (those live in the child PRDs)
- Backend endpoint design (child PRDs consume the existing campaign runtime API)
- Art asset sourcing (handled by the asset pipeline separately)

## 3. Feature catalog

Each row is one PRD. `Status` values: `placeholder` (not yet written), `draft` (written, not yet executed), `implemented` (shipped and verified), `skipped` (intentionally deferred). All child PRDs live under `docs/prd/active/PRD_frontend_<screen>_v1.md`.

### Core play loop (highest priority — required for F1 feel)

| # | Feature | GemRB reference | Godot target | PRD | Status |
|---|---|---|---|---|---|
| 1 | Main exploration view | `core/GUI/GameControl.cpp`, `GUIScripts/GUIWORLD.py`, `MessageWindow.py` | `godot-client/scripts/world/world_view.gd` + `scenes/game_session.gd` | `PRD_frontend_exploration_view_v1.md` | placeholder |
| 2 | Action bar (exploration + combat) | `GUIScripts/ActionsWindow.py`, `GUICommonWindows.py`, `ie_action.py` | `godot-client/scripts/ui/instrument_rail.gd` + `combat_overlay.gd` | `PRD_frontend_action_bar_v1.md` | placeholder |
| 3 | Party portraits strip | `GUIScripts/PortraitWindow.py`, `Portrait.py`, `GUICommonWindows.py` | `godot-client/scripts/ui/` (needs new `party_portraits.gd`) | `PRD_frontend_party_portraits_v1.md` | placeholder |
| 4 | Message / dialog window | `GUIScripts/MessageWindow.py`, `GUIWORLD.py` dialog helpers | `godot-client/scripts/ui/dialog_overlay.gd` + `narrative_panel.gd` | `PRD_frontend_message_window_v1.md` | placeholder |
| 5 | Inventory + paper doll | `GUIScripts/bg1/GUIINV.py`, `InventoryCommon.py`, `PaperDoll.py` | `godot-client/scripts/ui/inventory_panel.gd` | **`PRD_frontend_inventory_v1.md`** | **draft** |
| 6 | Character record (sheet) | `GUIScripts/GUIREC.py`, `GUIRECCommon.py`, `ie_stats.py` | `godot-client/scripts/ui/character_panel.gd` | **`PRD_frontend_character_record_v1.md`** | **draft** |

### Spellcasting

| # | Feature | GemRB reference | Godot target | PRD | Status |
|---|---|---|---|---|---|
| 7 | Mage spellbook | `GUIScripts/GUIMG.py`, `Spellbook.py` | NEW: `godot-client/scripts/ui/spellbook_mage_panel.gd` | `PRD_frontend_mage_spellbook_v1.md` | placeholder |
| 8 | Priest spellbook | `GUIScripts/GUIPR.py`, `Spellbook.py` | NEW: `godot-client/scripts/ui/spellbook_priest_panel.gd` | `PRD_frontend_priest_spellbook_v1.md` | placeholder |

### Map and travel

| # | Feature | GemRB reference | Godot target | PRD | Status |
|---|---|---|---|---|---|
| 9 | Area map (current-area automap) | `GUIScripts/GUIMA.py`, `GUIMACommon.py`, `core/GUI/MapControl.cpp` | `godot-client/scripts/ui/minimap_panel.gd` | `PRD_frontend_area_map_ui_v1.md` | placeholder |
| 10 | World map (overland travel) | `GUIScripts/GUIWMAP.py` (if present) or engine fallback | NEW: `godot-client/scripts/ui/world_map_panel.gd` | `PRD_frontend_world_map_v1.md` | placeholder |

### Quests, items, containers, trade

| # | Feature | GemRB reference | Godot target | PRD | Status |
|---|---|---|---|---|---|
| 11 | Journal | `GUIScripts/bg1/GUIJRNL.py` | `godot-client/scripts/ui/quest_panel.gd` | `PRD_frontend_journal_v1.md` | placeholder |
| 12 | Container (chest/body loot) | `GUIScripts/Container.py` | NEW: `godot-client/scripts/ui/container_panel.gd` | `PRD_frontend_container_v1.md` | placeholder |
| 13 | Store / merchant | `GUIScripts/GUISTORE.py` (2024 LOC) | `godot-client/scripts/ui/settlement_panel.gd` + NEW merchant surface | `PRD_frontend_store_v1.md` | placeholder |

### Character creation and progression

| # | Feature | GemRB reference | Godot target | PRD | Status |
|---|---|---|---|---|---|
| 14 | Character creation flow | `GUIScripts/bg1/CharGen*.py`, `CharGenCommon.py`, `GUICG*.py` (1..22) | `godot-client/scripts/ui/creation_wizard.gd` + step files | `PRD_frontend_character_creation_v1.md` | placeholder |
| 15 | Level up / advancement | `GUIScripts/LevelUp.py`, `LUCommon.py`, `LUSpellSelection.py`, `LUProfsSelection.py`, `LUSkillsSelection.py`, `LUHLASelection.py` | NEW: `godot-client/scripts/ui/level_up_panel.gd` | `PRD_frontend_level_up_v1.md` | placeholder |
| 16 | Dual-class UI | `GUIScripts/DualClass.py` | NEW: `godot-client/scripts/ui/dual_class_panel.gd` | `PRD_frontend_dual_class_v1.md` | placeholder |

### System menus

| # | Feature | GemRB reference | Godot target | PRD | Status |
|---|---|---|---|---|---|
| 17 | Title / main menu | `GUIScripts/bg1/Start.py` | `godot-client/scenes/title_screen.gd` | `PRD_frontend_title_menu_v1.md` | placeholder |
| 18 | Quit confirmation | `GUIScripts/bg1/QuitGame.py` | `godot-client/scripts/ui/pause_menu.gd` | `PRD_frontend_quit_confirm_v1.md` | placeholder |
| 19 | Options menu | `GUIScripts/GUIOPT.py`, `GUIOPTControls.py`, `GUIOPTExtra.py` | NEW: `godot-client/scripts/ui/options_panel.gd` | `PRD_frontend_options_menu_v1.md` | placeholder |
| 20 | Save game | `GUIScripts/GUISAVE.py` | `godot-client/scripts/ui/save_load_panel.gd` (save tab) | `PRD_frontend_save_ui_v1.md` | placeholder |
| 21 | Load game | `GUIScripts/GUILOAD.py` | `godot-client/scripts/ui/load_browser_widget.gd` | `PRD_frontend_load_ui_v1.md` | placeholder |

### Presentation / peripherals

| # | Feature | GemRB reference | Godot target | PRD | Status |
|---|---|---|---|---|---|
| 22 | Loading screen | `GUIScripts/bg1/LoadScreen.py` | NEW: `godot-client/scenes/loading_screen.tscn` + `.gd` | `PRD_frontend_loading_screen_v1.md` | placeholder |
| 23 | Death screen | `GUIScripts/GUIWORLD.py` `DeathWindow()` | NEW: integrated into `scenes/game_session.gd` | `PRD_frontend_death_screen_v1.md` | placeholder |
| 24 | Tooltip system | `core/GUI/Tooltip.cpp`, various `Button.SetTooltip` usages | NEW: `godot-client/scripts/ui/tooltip_host.gd` | `PRD_frontend_tooltip_system_v1.md` | placeholder |
| 25 | In-game clock widget | `GUIScripts/Clock.py` | `godot-client/scripts/ui/status_bar_widget.gd` (extend) | `PRD_frontend_clock_widget_v1.md` | placeholder |
| 26 | Console (dev) | `GUIScripts/Console.py`, `core/GUI/Console.cpp` | OPTIONAL — may stay out of scope | `PRD_frontend_dev_console_v1.md` | skipped |
| 27 | Movie player (cutscenes) | `GUIScripts/GUIMOVIE.py` | OPTIONAL — may stay out of scope for Phase 2 | `PRD_frontend_movie_player_v1.md` | skipped |

### Architectural layers — the "alive world" (added 2026-04-10 per user directive)

The UI layer alone doesn't produce BG1's signature "alive" feel. That comes from the below architectural layers. These PRDs cover backend simulation + client rendering **together** as vertical slices, not just UI.

| # | Layer | GemRB reference | ember-rpg existing code | PRD | Status |
|---|---|---|---|---|---|
| A1 | Actor data model + stat block | `core/Scriptable/Actor.{h,cpp}`, `CombatInfo.h`, `PCStatStruct.h` | `frp-backend/engine/world/entity.py`, backend actor records | `PRD_architecture_actor_runtime_v1.md` | placeholder |
| A2 | Actor animation state machine (walk/stand/attack/cast/hit/die + 8 directional sprites) | `core/CharAnimations.{h,cpp}`, `Animation.{h,cpp}`, `AnimationFactory.{h,cpp}` | `godot-client/scripts/world/entity_layer.gd` (tween only), `entity_visuals.gd` (idle bob only), NO state machine yet | `PRD_architecture_actor_animation_v1.md` | placeholder |
| A3 | **NPC wander + schedules + ambient life** (idle behavior that makes the world feel alive) | `core/GameScript/*` (BCS triggers+actions), `core/Scriptable/Scriptable.{h,cpp}` script slots SCR_GENERAL/SCR_DEFAULT, `core/Calendar.{h,cpp}` | `frp-backend/engine/world/behavior_tree.py` (RimWorld-style primitives exist, NPC attachments unclear), `frp-backend/engine/api/campaign/tick_loop.py` (30s tick is too slow for visible walking) | **`PRD_architecture_ambient_life_v1.md`** | **draft** |
| A4 | Actor spawning (spawn points, spawn groups, time triggers) | `plugins/AREImporter/*`, `core/Map.{h,cpp}` spawn handling | `frp-backend/engine/worldgen/npc_generator.py`, `frp-backend/engine/worldgen/npc_authored.py`, `region_projection.py` | `PRD_architecture_actor_spawning_v1.md` | placeholder |
| A5 | Live pathfinding + interruption | `core/PathFinder.{h,cpp}`, `core/Scriptable/Movable.{h,cpp}` | `godot-client/scripts/world/world_walk.gd` (client interpolation), backend pathfinding unclear | `PRD_architecture_pathfinding_v1.md` | placeholder |
| A6 | Multi-layer sprite rendering (body + equipment overlays + color tinting) | `core/CharAnimations.{h,cpp}`, `plugins/PLTImporter/*`, `GUIScripts/PaperDoll.py` | `godot-client/scripts/world/entity_sprite_catalog.gd`, `entity_visuals.gd` color tinting exists — no equipment overlays | `PRD_architecture_sprite_layers_v1.md` | placeholder |
| A7 | Area ambient animations (torches, flags, water, crowds) | `core/AreaAnimation.{h,cpp}` | NOT YET — needs new `godot-client/scripts/world/area_ambient_layer.gd` | `PRD_architecture_area_ambient_v1.md` | placeholder |
| A8 | Effect queue + status conditions (buffs, poisons, charm, sleep, paralysis) | `core/Effect.{h,cpp}`, `EffectQueue.{h,cpp}` | `frp-backend/engine/kernel/effects/*` (backend has effects — client visualization unclear) | `PRD_architecture_effect_visualization_v1.md` | placeholder |
| A9 | Fast visual tick (sub-second NPC position updates for smooth walking) | GemRB runs at native framerate; its equivalent is the game engine's own render loop | `tick_loop.py` runs at 30s interval, too slow — needs a separate fast lane | `PRD_architecture_fast_visual_tick_v1.md` | placeholder |

**Why A3 is the exemplar drafted first:** it cross-cuts the alive-world problem (behavior tree → tick loop → snapshot → client entity positions → tween → visible walking) end-to-end. It also exposes the tick-interval mismatch (30s backend vs 60Hz visible animation) which must be solved for any of A1..A9 to feel right. Solve A3 and the others become easier to scope.

## 4. Authoring rules for child PRDs

All child PRDs MUST:

1. **Follow `PRD_STANDARD.md`** — sections 1 through 10 in the stated order. Title is `PRD: Frontend <Feature Name> — <one line subtitle>`.
2. **Open with a "Reference" subsection inside §1 Purpose** that lists:
   - The exact GemRB source file path(s) under `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\`
   - The exact Godot target file path(s) under `godot-client/`
   - Any `core/GUI/*.cpp` widget the GemRB Python script calls that is relevant to behavior.
3. **Treat GemRB as a behavior spec, not as code.** Quote at most ~15 consecutive words of GemRB source per rule in the PRD (copyright / fair use boundary). Describe behavior in English + pseudocode instead.
4. **Consume the existing backend API only.** No new endpoints may be added by a frontend PRD. If a frontend feature needs backend data that isn't in the current `/game/campaigns/*` responses, the PRD must call that out in §9 Integration Points as a **dependency** and block on a sibling backend PRD being added first.
5. **Write AC against the existing automation bridge** (`runtime_automation_bridge.gd` — see `PRD_PLAYABILITY_RESCUE.md` §6 for the reference pattern). At least one AC per PRD must be verifiable without manual input.
6. **List forbidden files explicitly** — every frontend PRD must have a "Forbidden" subsection in §9 stating: "No edits to `frp-backend/engine/kernel/**`, no edits to any other PRD file, no new autoloads." Override only with explicit justification.
7. **Not exceed ~300 lines.** If a feature is too big for one PRD (e.g. character creation), split it into sub-PRDs with a parent-child naming: `PRD_frontend_character_creation_v1.md`, `PRD_frontend_character_creation_abilities_v1.md`, etc.

## 5. Priority and dependency order

Child PRDs should be written, implemented, and verified in this order. Later items assume earlier items are green.

1. **PRD_PLAYABILITY_RESCUE.md** (already written; gates the entire family)
2. **Core play loop**: exploration view → action bar → message window → party portraits → inventory → character record (rows 1..6)
3. **Spellcasting**: mage spellbook → priest spellbook (rows 7..8)
4. **Maps**: area map UI → world map (rows 9..10)
5. **Quests / trade**: journal → container → store (rows 11..13)
6. **Character growth**: level up → dual-class → character creation (rows 14..16) — creation is last because it's the most complex and already has a v1 placeholder
7. **System menus**: title → quit → options → save → load (rows 17..21)
8. **Presentation**: loading → death → tooltip → clock (rows 22..25)
9. **Deferred**: console, movie player (rows 26..27)

## 6. Kill criterion tie-in

None of the PRDs in this family start landing until **PRD_PLAYABILITY_RESCUE.md is green**. That PRD is the gate: if AC-03 / AC-04 fail three bounded implementation attempts, the project pivots to a browser client (React + Pixi.js) and this index is re-applied to the browser client instead of Godot. The index itself is engine-agnostic — only the "Godot target" column changes on pivot.

## 7. Execution via Copilot CLI / codex-cli

Each child PRD can be handed to a single Copilot CLI or codex-cli session via PowerShell. Recommended invocation:

    powershell.exe -NoProfile -Command "codex exec --model gpt-5 'Read docs/prd/active/PRD_frontend_<screen>_v1.md. Read the referenced GemRB source file(s) to understand behavior. Implement AC-01 through AC-N exactly. Only touch files listed under Integration Points. Do not copy GemRB code; reimplement. Run the Verification block and stop when it is green.'"

For the master index itself (this file), no implementation is needed — it is a planning document.

## 8. Status tracking

When a child PRD moves from `placeholder` to `draft`, update its row in §3. When it moves from `draft` to `implemented`, update the row AND add a short changelog entry below this section. When a child PRD becomes obsolete (e.g. because the feature is redesigned), mark it `skipped` with a reason.

### Changelog

- 2026-04-10: Index created. `PRD_frontend_inventory_v1.md` and `PRD_frontend_character_record_v1.md` drafted as exemplars to anchor the authoring convention.

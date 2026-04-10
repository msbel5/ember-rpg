# PRD: Frontend Area Map UI — BG1 Local Automap with Notes
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the area (local) map panel — BG1's automap for the currently-loaded area. Shows the explored portions of the area with fog-of-war masking unexplored regions, marks player position, marks notes placed by the player, shows important landmarks. Clicking the map scrolls the main game view to that tile (for quick navigation). Right-clicking adds a player note. The existing Godot scaffold `minimap_panel.gd` is a placeholder; this PRD extends it.

### Reference sources
- **GemRB behavior:** `gemrb/GUIScripts/GUIMA.py` (318 LOC — full file read). Key functions: `InitMapWindow(Window)`, `ShowMap()` (farsight effect), `RevealMap()`, `HasMapNotes()`, `AddNoteWindow()`, `SetMapNote` (callback), `ChangeTooltip()`, plus `MapN/NE/E/SE/S/SW/W/NW/C` scroll methods for arrow-button navigation. Uses `IE_GUI_MAP` widget internally.
- **GemRB companion:** `gemrb/GUIScripts/GUIMACommon.py` (71 LOC) — shared map helpers
- **Godot target:** Extend `godot-client/scripts/ui/minimap_panel.gd`

## 2. Scope

**In scope:**
- Render the current area at a fixed scale with fog-of-war overlay
- Player marker (pulsing dot) at current tile
- Click-to-scroll the main world view to that tile
- Right-click → add map note modal (text + color)
- Map note icons rendered at their coordinates with tooltip on hover
- Existing notes editable/removable via the same modal
- Toggle map-notes visibility via checkbox (BG2-feature, optional in BG1 but supported)
- Show landmarks (doors, containers, fixed locations) from backend data
- Zoom in/out (2x steps) — optional nice-to-have

**Out of scope:**
- World map (overland travel) — separate PRD `PRD_frontend_world_map_v1.md`
- Fog-of-war computation (backend responsibility)
- Farsight spell UI (integrates with this but the spell itself is combat scope)
- Exporting map to image

## 3. Functional Requirements (FR)

**FR-01:** The map panel MUST render the current area as a 2D image with fog-of-war: explored tiles visible, unexplored tiles dark. Data comes from `GameState.area_state.fog_mask`.

**FR-02:** The player marker MUST appear at `GameState.player_map_pos` and pulse (simple alpha tween) so it's easy to find.

**FR-03:** Left-clicking any explored tile MUST emit `scroll_world_view_to_tile(tile: Vector2i)` which the exploration view handles via `move_viewport_to(tile, center=true)`.

**FR-04:** Right-clicking any explored tile MUST open the note modal at that tile, allowing the player to enter text and choose a color (8 preset colors).

**FR-05:** Existing map notes MUST render as colored icons at their stored coordinates. Hovering MUST show the note text as tooltip.

**FR-06:** Clicking an existing note icon (left-click) MUST reopen the note modal in edit mode. A "Remove" button in the modal deletes the note.

**FR-07:** A toggle checkbox "Show Notes" MUST be present. Unchecked hides all note icons.

**FR-08:** The panel MUST refresh on `GameState.state_updated` (for player position) and `GameState.area_map_notes_changed` (add if missing).

**FR-09:** The panel MUST support directional scrolling for large maps via 8 direction buttons + Home key (center on player). This mirrors the BG2 extended navigation.

**FR-10:** Landmarks (doors, stores, important NPCs' home buildings) MUST render as distinct icons based on `area_state.landmarks` from the backend.

## 4. Data Structures

`GameState.area_state` expected shape:

    {
        "area_id": "ar1000",
        "area_name": "Candlekeep Exterior",
        "width": 120,
        "height": 80,
        "fog_mask": <packed byte array or 2D array>,   # 1 = explored, 0 = unexplored
        "tile_data": <map tile colors / biome mask>,   # for rendering
        "landmarks": [
            {"type": "door", "position": [45, 12], "tooltip": "Candlekeep Inner Gate"},
            {"type": "store", "position": [30, 18], "tooltip": "Winthrop's Inn"}
        ],
        "map_notes": [
            {"note_id": "note_1", "position": [22, 15], "color": 2, "text": "Hidden stash here"}
        ]
    }

Widget state:

    class_name AreaMapPanel extends PanelContainer
    
    const NOTE_COLORS := [
        Color.WHITE, Color.RED, Color.YELLOW, Color.GREEN,
        Color.BLUE, Color.PURPLE, Color.ORANGE, Color.CYAN
    ]
    
    var _show_notes: bool = true
    var _zoom: float = 1.0
    var _view_offset: Vector2 = Vector2.ZERO
    var _note_edit_modal: PanelContainer

## 5. Public API — methods that MUST exist

    # ---- construction ----
    func _ready() -> void
    func _input(event: InputEvent) -> void
    
    # ---- init / refresh ----
    func init_map_window() -> void                                               # GemRB: InitMapWindow
    func update_map_window() -> void
    func refresh_player_marker() -> void
    func refresh_fog_of_war() -> void
    func refresh_notes() -> void
    func refresh_landmarks() -> void
    
    # ---- click handling ----
    func handle_tile_click(tile: Vector2i, button: int) -> void                  # routes left/right
    func scroll_world_view_to(tile: Vector2i) -> void                            # emits signal
    
    # ---- note management ----
    func open_add_note_modal(tile: Vector2i) -> void                             # GemRB: AddNoteWindow
    func open_edit_note_modal(note_id: String) -> void
    func set_map_note(tile: Vector2i, color_index: int, text: String) -> void    # GemRB: SetMapNote
    func delete_map_note(note_id: String) -> void
    func has_map_notes() -> bool                                                 # GemRB: HasMapNotes
    
    # ---- notes visibility ----
    func toggle_notes_visible() -> void
    func set_notes_visible(visible: bool) -> void
    
    # ---- scroll / navigation ----
    func scroll_map(dx: int, dy: int) -> void                                    # GemRB: MapN/E/... helpers
    func map_north() -> void                                                     # shortcut for scroll_map(0, -10)
    func map_south() -> void
    func map_east() -> void
    func map_west() -> void
    func map_north_east() -> void
    func map_north_west() -> void
    func map_south_east() -> void
    func map_south_west() -> void
    func center_on_player() -> void                                              # GemRB: MapC
    
    # ---- zoom ----
    func zoom_in() -> void
    func zoom_out() -> void
    func set_zoom(level: float) -> void
    
    # ---- tooltip ----
    func build_landmark_tooltip(landmark: Dictionary) -> String
    func build_note_tooltip(note: Dictionary) -> String
    func change_tooltip_for_position(tile: Vector2i) -> void                     # GemRB: ChangeTooltip
    
    # ---- conversion ----
    func tile_to_screen(tile: Vector2i) -> Vector2
    func screen_to_tile(screen_point: Vector2) -> Vector2i
    
    # ---- farsight effect (spell integration) ----
    func show_map_farsight(tile: Vector2i) -> void                               # GemRB: ShowMap
    func reveal_map_area(center: Vector2i, radius: int) -> void                  # GemRB: RevealMap
    
    # ---- signals ----
    signal scroll_world_view_to_tile(tile: Vector2i)
    signal map_note_added(note_id: String, tile: Vector2i)
    signal map_note_updated(note_id: String)
    signal map_note_deleted(note_id: String)

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** Given an area with a fog mask where tile (10, 10) is explored, the rendered pixel at the corresponding screen position MUST be non-dark. Given tile (100, 100) is unexplored, the corresponding pixel MUST be dark.

**AC-02 [FR-02]:** With `GameState.player_map_pos = (25, 30)`, the player marker node MUST be positioned at `tile_to_screen((25, 30))` (within 1 pixel).

**AC-03 [FR-03]:** Simulated left-click on tile (45, 15) MUST emit `scroll_world_view_to_tile((45, 15))`.

**AC-04 [FR-04]:** Simulated right-click on tile (20, 20) MUST open the note edit modal with that tile stored as the target.

**AC-05 [FR-05]:** Given 2 notes at (10,10) red and (20,20) blue, both icons MUST be visible on the map. Hovering the (10,10) icon MUST set its tooltip.

**AC-06 [FR-06]:** Clicking an existing note icon MUST open the modal with the note's existing text and color pre-populated.

**AC-07 [FR-07]:** Calling `set_notes_visible(false)` MUST hide all note icons (not remove them from the data).

**AC-08 [FR-09]:** Calling `map_north()` MUST call `scroll_map(0, -10)` which adjusts `_view_offset.y` by -10.

**AC-09 [FR-10]:** Given 3 landmarks in `area_state.landmarks`, the map MUST render 3 landmark icons with correct tooltips.

**AC-10 [reflection]:** Every method in §5 MUST exist on the script.

## 7. Performance Requirements

- Full map render with 10000 tiles: **< 50ms**
- Fog of war update: **< 20ms** on position change
- Note icon rendering: **< 5ms** per note
- Scroll by one unit: **< 16ms**

## 8. Error Handling

- Missing `area_state.fog_mask`: render entire map dark, log once
- Invalid tile in click: clamp to area bounds
- Note modal submit with empty text: treat as delete
- Backend area_state desync (area_id mismatch): force refresh on next tick

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/minimap_panel.gd` — rewrite / extend per §5
- `godot-client/scripts/ui/area_map_note_modal.gd` — NEW sub-modal
- `godot-client/scenes/minimap_panel.tscn` — NEW / updated scene
- `godot-client/autoloads/game_state.gd` — add `area_state` projection + `area_map_notes_changed` signal
- `godot-client/tests/automation/godot/test_frontend_area_map_ui.gd` — NEW

**Backend (consumed, NOT modified):**
- `/state` includes `area_state` per §4 shape
- Commands: `add_map_note <x> <y> <color> "<text>"`, `update_map_note <note_id> ...`, `delete_map_note <note_id>`

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No GemRB code port
- No client-side fog-of-war computation

## 10. Test Coverage Target

- `test_frontend_area_map_ui.gd` MUST cover AC-01..AC-10
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_area_map_ui.gd

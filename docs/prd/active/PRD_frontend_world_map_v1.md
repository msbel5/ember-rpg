# PRD: Frontend World Map — BG1 Overland Travel Interface
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the World Map panel — BG1's overland travel interface. Shows a hand-drawn world map of the Sword Coast (or ember's equivalent region atlas) with nodes for visited and discoverable areas, distance labels between nodes, click-to-travel interaction, and travel time previews. This is one of BG1's most iconic UI screens and must be captured in ember-rpg.

### Reference sources
- **GemRB behavior:** `gemrb/GUIScripts/GUIMA.py` (both area map and world map — see `InitWorldMapWindow(Window)` and helpers, plus the 8 directional scroll methods `MapN/NE/E/SE/S/SW/W/NW/C`). `GUIMACommon.py` provides `MoveToNewArea`.
- **GemRB widget:** `gemrb/core/GUI/WorldMapControl.{h,cpp}` — the `IE_GUI_WORLDMAP` widget. ember does not port the C++ widget; implements its own.
- **Color scheme for BG1 (from the source):** normal node `(0,0,0,0xff)`, selected `(0xff,0,0,0xff)`, not-visited `(0x80,0x80,0xf0,0xa0)`.
- **Godot target:** NEW `godot-client/scripts/ui/world_map_panel.gd` + NEW `godot-client/scenes/world_map_panel.tscn`

## 2. Scope

**In scope:**
- Display world map background image with area nodes overlaid
- 3 node states: visited (black), selected (red), not-visited (light-blue with transparency)
- Click a reachable node to initiate travel (opens confirmation modal with travel time + random encounter risk)
- Hover a node shows tooltip with area name + distance from current location
- Pan/scroll map with 8 direction buttons OR mouse drag
- Center-on-current-area button (Home key)
- Travel confirmation modal with encounter odds + party rest status check
- Visual path indicator from current location to selected target
- Lock the map from travel during cutscenes / dialog / combat

**Out of scope:**
- Travel encounter resolution (backend combat kernel)
- World time progression during travel (backend tick)
- Mounts / travel speed modifiers (backend)
- Weather effects on the world map

## 3. Functional Requirements (FR)

**FR-01:** The world map panel MUST load and display the world map background image (asset path: `res://assets/world/world_map_bg.png` or similar).

**FR-02:** Area nodes MUST render as colored icons at their world coordinates. Each node's state MUST match `GameState.world_map_state.nodes[node_id].state` (visited | selected | not_visited | current).

**FR-03:** The current area MUST be highlighted distinctly (e.g. a pulsing yellow ring).

**FR-04:** Left-clicking a node MUST call `handle_node_click(node_id)`. If the node is the current area, no-op. If not-visited, check `discoverable == true` flag and show tooltip "Discovered via [rumor/map purchase]". If visited, open travel confirmation modal.

**FR-05:** Hovering a node MUST show tooltip with: node name, area type (town/wilderness/dungeon), distance in days from current, "Unvisited" tag if applicable.

**FR-06:** The travel confirmation modal MUST display: destination name, travel time (days, hours), encounter risk label (low/medium/high), party rest status, and Confirm / Cancel buttons.

**FR-07:** Confirming travel MUST emit `travel_to_requested(target_node_id: String)` which routes to backend command `travel <target_node_id>`.

**FR-08:** The map MUST support panning via 8 directional buttons AND mouse drag. The current viewport offset MUST be clamped to the map image bounds.

**FR-09:** Pressing Home key MUST center the viewport on the current area.

**FR-10:** The map MUST draw a path line from the current area to the currently hovered or selected node (implementation: a Line2D or ImmediateMesh). Path may be a straight line in Phase 2; curved/waypointed is nice-to-have.

**FR-11:** The panel MUST refuse to open travel modals during combat, dialog, or cutscene states (`GameState.is_in_combat()`, `has_active_dialog()`).

**FR-12:** The panel MUST refresh on `GameState.world_map_state_changed` signal + `GameState.state_updated`.

## 4. Data Structures

`GameState.world_map_state` expected shape:

    {
        "current_area_id": "candlekeep",
        "nodes": {
            "candlekeep": {
                "area_id": "candlekeep",
                "name": "Candlekeep",
                "type": "town",
                "position": [45, 30],        # world map pixel coords
                "state": "current",           # visited | selected | not_visited | current
                "discoverable": true,
                "distance_days": 0
            },
            "friendly_arm_inn": {
                "area_id": "friendly_arm_inn",
                "name": "Friendly Arm Inn",
                "type": "town",
                "position": [70, 22],
                "state": "not_visited",
                "discoverable": true,
                "distance_days": 3
            },
            ...
        },
        "paths": [
            {"from": "candlekeep", "to": "friendly_arm_inn", "risk": "low"}
        ]
    }

Widget state:

    class_name WorldMapPanel extends PanelContainer
    
    const NODE_COLOR_NORMAL := Color(0, 0, 0, 1)
    const NODE_COLOR_SELECTED := Color(1, 0, 0, 1)
    const NODE_COLOR_NOT_VISITED := Color(0.5, 0.5, 0.94, 0.63)  # 0x80/255, 0x80/255, 0xf0/255, 0xa0/255
    const NODE_COLOR_CURRENT := Color(1, 1, 0, 1)
    
    var _view_offset: Vector2 = Vector2.ZERO
    var _hovered_node_id: String = ""
    var _selected_node_id: String = ""
    var _travel_confirm_modal: PanelContainer

## 5. Public API — methods that MUST exist

    # ---- construction ----
    func _ready() -> void
    func _input(event: InputEvent) -> void                                       # Home key + hotkeys
    
    # ---- init / refresh ----
    func init_world_map_window() -> void                                         # GemRB: InitWorldMapWindow
    func update_world_map_window() -> void
    func refresh_nodes() -> void
    func refresh_current_highlight() -> void
    func refresh_path_line() -> void
    
    # ---- nodes ----
    func render_node(node_id: String, node_data: Dictionary) -> void
    func get_node_screen_position(node_id: String) -> Vector2
    func handle_node_click(node_id: String) -> void
    func handle_node_hover_enter(node_id: String) -> void
    func handle_node_hover_exit(node_id: String) -> void
    func color_for_node_state(state: String) -> Color
    
    # ---- travel ----
    func open_travel_confirm_modal(target_node_id: String) -> void
    func close_travel_confirm_modal() -> void
    func confirm_travel() -> void
    func cancel_travel() -> void
    func build_travel_confirm_text(target_node_data: Dictionary) -> String       # multi-line description
    func can_travel_to(target_node_id: String) -> Dictionary                     # {allowed: bool, reason: String}
    
    # ---- panning / scroll ----
    func scroll_map(dx: int, dy: int) -> void
    func map_north() -> void
    func map_south() -> void
    func map_east() -> void
    func map_west() -> void
    func map_north_east() -> void
    func map_north_west() -> void
    func map_south_east() -> void
    func map_south_west() -> void
    func center_on_current_area() -> void                                        # GemRB: MapC equivalent
    func clamp_view_offset() -> void
    
    # ---- path rendering ----
    func draw_path_line(from_node_id: String, to_node_id: String) -> void
    func clear_path_line() -> void
    
    # ---- tooltip ----
    func build_node_tooltip(node_data: Dictionary) -> String
    func change_tooltip_for_node(node_id: String) -> void                        # GemRB: ChangeTooltip
    
    # ---- state gates ----
    func can_open_travel() -> bool                                               # checks combat/dialog/cutscene
    func handle_blocked_travel_attempt(reason: String) -> void                   # shows a toast
    
    # ---- conversion ----
    func world_to_screen(world_pos: Vector2) -> Vector2
    func screen_to_world(screen_point: Vector2) -> Vector2
    
    # ---- signals ----
    signal travel_to_requested(target_node_id: String)
    signal node_hovered(node_id: String)
    signal node_selected(node_id: String)
    signal travel_confirm_opened(target_node_id: String)
    signal travel_confirm_closed()

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** On `_ready()`, the world map background image MUST be loaded and visible. Verified by asserting `_background_sprite.texture != null`.

**AC-02 [FR-02, FR-03]:** Given `world_map_state.nodes` with 5 entries and one marked `state = "current"`, the map MUST render 5 node icons and the current one MUST use `NODE_COLOR_CURRENT`.

**AC-03 [FR-04]:** Clicking a visited node (via automation bridge) MUST call `open_travel_confirm_modal(node_id)`. Clicking the current node MUST NOT open the modal.

**AC-04 [FR-05]:** Hovering a node MUST emit `node_hovered(node_id)` and set a tooltip containing the node name.

**AC-05 [FR-07]:** Clicking Confirm in the travel modal MUST emit `travel_to_requested(target_node_id)`. The modal MUST close.

**AC-06 [FR-08]:** Calling `scroll_map(0, -10)` MUST decrement `_view_offset.y` by 10, clamped to bounds.

**AC-07 [FR-09]:** Pressing Home key (via automation bridge) MUST call `center_on_current_area()` which sets the view offset so the current node is visible.

**AC-08 [FR-11]:** With `GameState.is_in_combat() == true`, calling `open_travel_confirm_modal("target")` MUST call `handle_blocked_travel_attempt("Cannot travel during combat")` instead of opening the modal.

**AC-09 [FR-10]:** Hovering a node MUST call `draw_path_line(current_area_id, hovered_node_id)` which makes at least one Line2D child visible.

**AC-10 [reflection]:** Every method in §5 MUST exist on the script.

## 7. Performance Requirements

- World map render with 40 nodes: **< 30ms**
- Node hover highlight: **< 16ms**
- Pan scroll by one unit: **< 16ms**
- Travel confirm modal open: **< 100ms**

## 8. Error Handling

- Missing background image: render a fallback colored rect with "World map unavailable"
- Missing `world_map_state`: render empty map, log once
- Invalid node_id in click: no-op, log at DEBUG
- Confirm travel while target is unreachable: show toast, keep modal open
- View offset clamping: always clamp to `(0, 0)` to `(map_w - view_w, map_h - view_h)`

## 9. Integration Points

**Godot (editable):**
- `godot-client/scripts/ui/world_map_panel.gd` — NEW
- `godot-client/scripts/ui/travel_confirm_modal.gd` — NEW sub-modal
- `godot-client/scenes/world_map_panel.tscn` — NEW
- `godot-client/autoloads/game_state.gd` — add `world_map_state` projection + `world_map_state_changed` signal
- `godot-client/tests/automation/godot/test_frontend_world_map.gd` — NEW

**Backend (consumed, NOT modified):**
- `/state` includes `world_map_state` per §4 shape
- Command: `travel <node_id>`
- Existing `travel_encounter` resolution (per 2026-04-02 commit 264eda9)

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**`
- No GemRB code port
- No client-side encounter resolution
- No client-side time advancement

## 10. Test Coverage Target

- `test_frontend_world_map.gd` MUST cover AC-01..AC-10
- ≥80% branch coverage

## 11. Verification

    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
    godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/automation/godot/test_frontend_world_map.gd

## Core world viewport — renders map, entities, handles input, camera, walk.
## Delegates command generation to WorldInteraction, focus to WorldFocus,
## and walk animation to WorldWalk.  Each helper is under 150 lines.
extends SubViewportContainer

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const PovRendererConfig = preload("res://scripts/pov_renderer_config.gd")
const WorldOverlay = preload("res://scripts/world/world_overlay.gd")

signal command_requested(command_text: String)
signal focus_changed(summary: String)
signal focus_actions_changed(actions: Array)

@onready var world_viewport: SubViewport = $WorldViewport
@onready var terrain_layer: TileMapLayer = $WorldViewport/WorldRoot/TerrainLayer
@onready var entity_layer: Node2D = $WorldViewport/WorldRoot/EntityLayer
@onready var selection_layer = $WorldViewport/WorldRoot/SelectionLayer
@onready var world_camera: Camera2D = $WorldViewport/WorldRoot/WorldCamera

var _world_overlay: Control
var _placeholder_banner: Label
var _atmosphere_motes: Array = []
var _background_key: String = ""
var _focus_summary_text: String = ""
var _focus_actions: Array = []

# Camera state
var _is_camera_dragging: bool = false
const EDGE_SCROLL_MARGIN := 20.0
const EDGE_SCROLL_SPEED := 200.0

# Context menu state
var _context_menu: PopupMenu
var _context_target_entity: Dictionary = {}
var _context_target_tile: Vector2i = Vector2i.ZERO

# Walk animation state
var _walker := WorldWalk.new()
var _walk_tween: Tween
var _walk_pending_interact: Dictionary = {}


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_exited.connect(_on_mouse_exited)
	_world_overlay = WorldOverlay.new()
	_world_overlay.name = "WorldOverlay"
	add_child(_world_overlay)
	_placeholder_banner = Label.new()
	_placeholder_banner.name = "PlaceholderBanner"
	_placeholder_banner.visible = false
	_placeholder_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_placeholder_banner.position = Vector2(12, 12)
	_placeholder_banner.z_index = 100
	_placeholder_banner.text = "Placeholder map: waiting for campaign data"
	_placeholder_banner.add_theme_color_override("font_color", Color(1.0, 0.88, 0.42))
	_placeholder_banner.add_theme_font_size_override("font_size", 16)
	add_child(_placeholder_banner)
	if get_node_or_null("/root/GameState") != null:
		GameState.map_loaded.connect(_refresh_from_state)
		GameState.entities_loaded.connect(_refresh_from_state)
		GameState.state_updated.connect(_refresh_from_state)
	_refresh_from_state()


# --- public ----------------------------------------------------------------

func refresh_from_state() -> void:
	_refresh_from_state()

func get_atmosphere_state() -> Dictionary:
	return {"mote_count": _atmosphere_motes.size(), "placeholder": _is_placeholder(), "background_key": _background_key}

func get_focus_summary() -> String:
	return _focus_summary_text

func get_focus_actions() -> Array:
	return _focus_actions.duplicate(true)

func capture_world_image() -> Image:
	return world_viewport.get_texture().get_image()

func capture_world_screenshot(folder: String, prefix: String) -> String:
	var image := capture_world_image()
	var screenshot_capture = preload("res://scripts/ui/screenshot_capture.gd")
	return screenshot_capture.capture_image(image, folder, prefix)

# Legacy public API preserved for game_session.gd compatibility
func command_for_entity(entity: Dictionary) -> String:
	return WorldInteraction.command_for_entity(entity)

func command_for_tile(tile_position: Vector2i) -> String:
	return WorldInteraction.command_for_tile(tile_position, _tile_name_at(tile_position))


# --- per-frame -------------------------------------------------------------

func _process(delta: float) -> void:
	_handle_edge_scroll(delta)
	_handle_home_key()


func _handle_edge_scroll(delta: float) -> void:
	if not is_visible_in_tree():
		return
	var mouse_pos := get_local_mouse_position()
	var vp_size := size
	var scroll_dir := Vector2.ZERO
	if mouse_pos.x < EDGE_SCROLL_MARGIN and mouse_pos.x >= 0:
		scroll_dir.x = -1.0
	elif mouse_pos.x > vp_size.x - EDGE_SCROLL_MARGIN and mouse_pos.x <= vp_size.x:
		scroll_dir.x = 1.0
	if mouse_pos.y < EDGE_SCROLL_MARGIN and mouse_pos.y >= 0:
		scroll_dir.y = -1.0
	elif mouse_pos.y > vp_size.y - EDGE_SCROLL_MARGIN and mouse_pos.y <= vp_size.y:
		scroll_dir.y = 1.0
	if scroll_dir != Vector2.ZERO:
		world_camera.position += scroll_dir * EDGE_SCROLL_SPEED * delta / world_camera.zoom.x


func _handle_home_key() -> void:
	if Input.is_key_pressed(KEY_HOME):
		var player_tile := GameState.player_map_pos
		if player_tile != Vector2i.ZERO:
			world_camera.position = Vector2(player_tile) * TileCatalog.TILE_SIZE + Vector2(TileCatalog.TILE_SIZE / 2.0, TileCatalog.TILE_SIZE / 2.0)


# --- input -----------------------------------------------------------------

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		if _is_camera_dragging:
			world_camera.position -= event.relative / world_camera.zoom
			accept_event()
			return
		_update_hover(event.position)
		return

	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_MIDDLE:
			_is_camera_dragging = event.pressed
			accept_event()
			return
		if event.pressed:
			match event.button_index:
				MOUSE_BUTTON_LEFT:
					_on_left_click(event.position)
					accept_event()
				MOUSE_BUTTON_RIGHT:
					_on_right_click(event.position)
					accept_event()
				MOUSE_BUTTON_WHEEL_UP:
					world_camera.zoom_in()
					accept_event()
				MOUSE_BUTTON_WHEEL_DOWN:
					world_camera.zoom_out()
					accept_event()


func _on_left_click(screen_pos: Vector2) -> void:
	var tile := _screen_to_tile(screen_pos)
	if not _tile_in_bounds(tile):
		return
	if selection_layer.has_method("set_selected_tile"):
		selection_layer.set_selected_tile(tile)
	if selection_layer.has_method("flash_tile"):
		selection_layer.flash_tile(tile)
	var entity := entity_layer.get_entity_at_tile(tile)
	_emit_focus(tile, entity)
	_handle_walk_or_interact(tile, entity)


func _on_right_click(screen_pos: Vector2) -> void:
	var tile := _screen_to_tile(screen_pos)
	if not _tile_in_bounds(tile):
		return
	var entity := entity_layer.get_entity_at_tile(tile)
	_show_context_menu(screen_pos, tile, entity)


# --- click-to-walk ---------------------------------------------------------

func _handle_walk_or_interact(tile: Vector2i, entity: Dictionary) -> void:
	_walker.cancel()
	var player_tile := GameState.player_map_pos
	if player_tile == Vector2i.ZERO:
		_emit_command(tile, entity)
		return

	if not entity.is_empty():
		var dist := abs(tile.x - player_tile.x) + abs(tile.y - player_tile.y)
		if dist <= 1:
			command_requested.emit(WorldInteraction.command_for_entity(entity))
			return
		var adjacent := _find_adjacent(tile, player_tile)
		var path := _walker.compute_path(player_tile, adjacent, GameState.map_data)
		if path.is_empty():
			command_requested.emit(WorldInteraction.command_for_entity(entity))
			return
		_walk_pending_interact = entity
		_walker.start_walk(path)
		_animate_walk(path)
	else:
		var tile_name := _tile_name_at(tile)
		if tile_name in WorldInteraction.INTERACTIVE_TILE_NAMES:
			command_requested.emit(WorldInteraction.command_for_tile(tile, tile_name))
			return
		var path := _walker.compute_path(player_tile, tile, GameState.map_data)
		if path.is_empty():
			command_requested.emit(WorldInteraction.command_for_tile(tile, tile_name))
			return
		_walk_pending_interact = {}
		_walker.start_walk(path)
		_animate_walk(path)
		command_requested.emit("move to %d,%d" % [tile.x, tile.y])


func _animate_walk(path: Array[Vector2i]) -> void:
	if path.is_empty():
		return
	if _walk_tween != null and _walk_tween.is_valid():
		_walk_tween.kill()
	var player_actor := entity_layer.get_node_or_null("player")
	if player_actor == null:
		return
	_walk_tween = create_tween().set_ease(Tween.EASE_IN_OUT).set_trans(Tween.TRANS_SINE)
	for tile in path:
		var target := Vector2(tile.x * TileCatalog.TILE_SIZE + TileCatalog.TILE_SIZE / 2.0,
							  tile.y * TileCatalog.TILE_SIZE + TileCatalog.TILE_SIZE / 2.0)
		_walk_tween.tween_property(player_actor, "position", target, WorldWalk.STEP_DURATION)
	_walk_tween.finished.connect(_on_walk_finished)


func _on_walk_finished() -> void:
	_walker.is_walking = false
	if not _walk_pending_interact.is_empty():
		command_requested.emit(WorldInteraction.command_for_entity(_walk_pending_interact))
		_walk_pending_interact = {}


func _find_adjacent(target: Vector2i, from: Vector2i) -> Vector2i:
	var best := target
	var best_dist := 99999
	for dir in [Vector2i(0, -1), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(1, 0)]:
		var c := target + dir
		if not _tile_in_bounds(c):
			continue
		var n := _tile_name_at(c)
		if n in ["wall", "water", "void"]:
			continue
		var d := abs(c.x - from.x) + abs(c.y - from.y)
		if d < best_dist:
			best = c
			best_dist = d
	return best


# --- context menu ----------------------------------------------------------

func _show_context_menu(screen_pos: Vector2, tile: Vector2i, entity: Dictionary) -> void:
	if _context_menu != null:
		_context_menu.queue_free()
	_context_menu = PopupMenu.new()
	_context_menu.name = "ContextMenu"
	add_child(_context_menu)
	_context_target_entity = entity
	_context_target_tile = tile
	var items: Array[Dictionary]
	if not entity.is_empty():
		items = WorldInteraction.build_entity_menu_items(entity)
	else:
		items = WorldInteraction.build_ground_menu_items(_tile_name_at(tile))
	for item in items:
		_context_menu.add_item(str(item.get("label", "")), int(item.get("id", 0)))
	_context_menu.id_pressed.connect(_on_context_menu_selected)
	_context_menu.position = Vector2i(int(screen_pos.x + global_position.x), int(screen_pos.y + global_position.y))
	_context_menu.popup()


func _on_context_menu_selected(id: int) -> void:
	var cmd := WorldInteraction.resolve_context_command(id, _context_target_entity, _context_target_tile, _tile_name_at(_context_target_tile))
	if not cmd.is_empty():
		command_requested.emit(cmd)


# --- state refresh ---------------------------------------------------------

func _refresh_from_state(_payload = null) -> void:
	var has_real_map := not GameState.map_data.is_empty()
	var map_payload: Dictionary = GameState.map_data if has_real_map else TileCatalog.build_placeholder_map()
	if map_payload.is_empty():
		map_payload = TileCatalog.build_placeholder_map()
	_update_placeholder_banner(not has_real_map or bool(map_payload.get("placeholder", false)))
	terrain_layer.render_map(map_payload)
	_update_attention_layers(map_payload)
	_rebuild_atmosphere(map_payload)
	_background_key = _resolve_background_key()
	if _world_overlay != null and _world_overlay.has_method("configure"):
		_world_overlay.configure(_current_adapter_id(), _background_key, _atmosphere_motes, _is_placeholder())
	var player_tile := GameState.player_map_pos
	if player_tile == Vector2i.ZERO and map_payload.has("spawn_point"):
		var sp = map_payload.get("spawn_point", [])
		if sp is Array and sp.size() >= 2:
			player_tile = Vector2i(int(sp[0]), int(sp[1]))
	entity_layer.render_entities(player_tile, GameState.entities, _resolve_player_template())
	world_camera.focus_on_tiles(_camera_focus_tiles(player_tile), TileCatalog.TILE_SIZE)
	if selection_layer.has_method("set_selected_tile") and player_tile != Vector2i.ZERO:
		selection_layer.set_selected_tile(player_tile)
	_set_focus_summary(WorldFocus.default_summary(GameState.get_display_location(), GameState.entities))
	_set_focus_actions(WorldFocus.default_actions(GameState.entities))


# --- hover -----------------------------------------------------------------

func _update_hover(screen_pos: Vector2) -> void:
	var tile := _screen_to_tile(screen_pos)
	if not _tile_in_bounds(tile):
		tooltip_text = ""
		if selection_layer.has_method("clear_hover"):
			selection_layer.clear_hover()
		return
	if selection_layer.has_method("set_hover_tile"):
		selection_layer.set_hover_tile(tile)
	var entity := entity_layer.get_entity_at_tile(tile)
	var tile_name := _tile_name_at(tile)
	tooltip_text = WorldInteraction.describe_hover(entity, tile_name, tile) if not _is_placeholder() else _placeholder_banner.text
	_emit_focus(tile, entity)


func _on_mouse_exited() -> void:
	tooltip_text = ""
	if selection_layer.has_method("clear_hover"):
		selection_layer.clear_hover()
	_set_focus_summary(WorldFocus.default_summary(GameState.get_display_location(), GameState.entities))
	_set_focus_actions(WorldFocus.default_actions(GameState.entities))


# --- internal helpers ------------------------------------------------------

func _emit_focus(tile: Vector2i, entity: Dictionary) -> void:
	var tile_name := _tile_name_at(tile)
	var summary := WorldFocus.tile_summary(tile_name, tile, entity)
	if summary.is_empty():
		summary = WorldFocus.default_summary(GameState.get_display_location(), GameState.entities)
	_set_focus_summary(summary)
	var actions := WorldFocus.actions_for_tile(tile, tile_name, entity)
	if actions.is_empty():
		actions = WorldFocus.default_actions(GameState.entities)
	_set_focus_actions(actions)


func _emit_command(tile: Vector2i, entity: Dictionary) -> void:
	if not entity.is_empty():
		command_requested.emit(WorldInteraction.command_for_entity(entity))
	else:
		command_requested.emit(WorldInteraction.command_for_tile(tile, _tile_name_at(tile)))


func _set_focus_summary(text: String) -> void:
	var next := text.strip_edges()
	if next.is_empty():
		next = "Focus: click a prop, person, or threat for the clearest next action."
	if _focus_summary_text != next:
		_focus_summary_text = next
		focus_changed.emit(next)


func _set_focus_actions(actions: Array) -> void:
	var next := actions.duplicate(true)
	if next.is_empty():
		next = WorldFocus.default_actions(GameState.entities)
	_focus_actions = next
	focus_actions_changed.emit(next)


func _screen_to_tile(screen_pos: Vector2) -> Vector2i:
	var wp := world_camera.position + (screen_pos - Vector2(size) / 2.0) / world_camera.zoom
	return Vector2i(floori(wp.x / TileCatalog.TILE_SIZE), floori(wp.y / TileCatalog.TILE_SIZE))


func _tile_in_bounds(t: Vector2i) -> bool:
	var w := int(GameState.map_data.get("width", 0))
	var h := int(GameState.map_data.get("height", 0))
	if w <= 0 or h <= 0:
		return t.x >= 0 and t.y >= 0
	return t.x >= 0 and t.y >= 0 and t.x < w and t.y < h


func _tile_name_at(t: Vector2i) -> String:
	var tiles = GameState.map_data.get("tiles", [])
	if not (tiles is Array) or t.y < 0 or t.y >= tiles.size():
		return ""
	var row = tiles[t.y]
	if not (row is Array) or t.x < 0 or t.x >= row.size():
		return ""
	return TileCatalog.resolve_tile_name(row[t.x])


func _is_placeholder() -> bool:
	return _placeholder_banner != null and _placeholder_banner.visible


func _update_placeholder_banner(is_ph: bool) -> void:
	if _placeholder_banner != null:
		_placeholder_banner.visible = is_ph
		if is_ph:
			_placeholder_banner.text = "Placeholder map: awaiting live campaign terrain"


func _resolve_player_template() -> String:
	if GameState.player.has("classes") and GameState.player["classes"] is Dictionary and not GameState.player["classes"].is_empty():
		return str(GameState.player["classes"].keys()[0]).to_lower()
	if GameState.player.has("player_class"):
		return str(GameState.player["player_class"]).to_lower()
	return "warrior"


func _current_adapter_id() -> String:
	return str(GameState.adapter_id).strip_edges().to_lower()


func _update_attention_layers(map_payload: Dictionary) -> void:
	if selection_layer == null:
		return
	if selection_layer.has_method("set_interest_tiles"):
		selection_layer.set_interest_tiles(_interactive_positions(map_payload))
	if selection_layer.has_method("set_hostile_tiles"):
		selection_layer.set_hostile_tiles(_hostile_positions())
	if selection_layer.has_method("set_ambient_tiles"):
		selection_layer.set_ambient_tiles(_ambient_positions(map_payload))


func _interactive_positions(mp: Dictionary) -> Array:
	var result: Array = []
	var rows = mp.get("tiles", [])
	for y in range(rows.size()):
		var row = rows[y]
		if not (row is Array):
			continue
		for x in range(row.size()):
			if TileCatalog.resolve_tile_name(row[x]) in WorldInteraction.INTERACTIVE_TILE_NAMES:
				result.append(Vector2i(x, y))
	for e in GameState.entities.get("furniture", []):
		if e is Dictionary:
			result.append(_entity_tile(e))
	return result


func _ambient_positions(mp: Dictionary) -> Array:
	var result: Array = []
	var rows = mp.get("tiles", [])
	for y in range(rows.size()):
		var row = rows[y]
		if not (row is Array):
			continue
		for x in range(row.size()):
			if TileCatalog.resolve_tile_name(row[x]) in ["well", "fountain"]:
				result.append(Vector2i(x, y))
	return result


func _hostile_positions() -> Array:
	var result: Array = []
	for e in GameState.entities.get("enemies", []):
		if e is Dictionary:
			result.append(_entity_tile(e))
	return result


func _entity_tile(entry: Dictionary) -> Vector2i:
	var p = entry.get("position", [0, 0])
	if p is Array and p.size() >= 2:
		return Vector2i(int(p[0]), int(p[1]))
	return Vector2i.ZERO


func _camera_focus_tiles(player_tile: Vector2i) -> Array:
	var tiles: Array = [player_tile]
	for bucket in ["npcs", "enemies", "items", "furniture"]:
		for e in GameState.entities.get(bucket, []):
			if not (e is Dictionary):
				continue
			var t := _entity_tile(e)
			if t == Vector2i.ZERO or abs(t.x - player_tile.x) + abs(t.y - player_tile.y) > 12:
				continue
			tiles.append(t)
			if tiles.size() >= 10:
				return tiles
	return tiles


func _rebuild_atmosphere(mp: Dictionary) -> void:
	_atmosphere_motes.clear()
	var mw := maxf(float(mp.get("width", 16)), 16.0)
	var mh := maxf(float(mp.get("height", 12)), 12.0)
	var density := clampi(int((mw * mh) / 96.0), 10, 28)
	for i in range(density):
		var s := float(i + 1)
		_atmosphere_motes.append({
			"x": fposmod(mw * 13.0 + s * 57.0, maxf(size.x, 320.0)),
			"y": fposmod(mh * 11.0 + s * 31.0, maxf(size.y, 220.0)),
			"speed": 0.35 + fposmod(s * 0.17, 0.85),
			"drift": 4.0 + fposmod(s * 1.3, 14.0),
			"radius": 1.2 + fposmod(s * 0.41, 1.8),
			"phase": s * 0.63,
			"alpha": 0.08 + fposmod(s * 0.019, 0.08),
		})


func _resolve_background_key() -> String:
	var hint := GameState.get_display_location().to_lower()
	var path := PovRendererConfig.resolve_background(hint)
	if path.contains("dungeon") or GameState.scene == "combat":
		return "dungeon"
	return "harbor"

extends SubViewportContainer
class_name WorldViewWidget

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const PovRendererConfig = preload("res://scripts/pov_renderer_config.gd")
const WorldOverlay = preload("res://scripts/world/world_overlay.gd")
const WorldIntentRouter = preload("res://scripts/world/world_intent_router.gd")
const WorldViewPlanner = preload("res://scripts/world/world_view_planner.gd")
const ENABLE_WORLD_OVERLAY := false

signal command_requested(command_text: String)
signal command_sequence_requested(commands: Array[String])
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
var _is_camera_dragging: bool = false
const EDGE_SCROLL_MARGIN := 20.0
const EDGE_SCROLL_SPEED := 200.0

var _context_menu: PopupMenu
var _context_menu_commands: Dictionary = {}

var _walker := WorldWalk.new()
func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_exited.connect(_on_mouse_exited)
	resized.connect(_sync_viewport_size)
	if ENABLE_WORLD_OVERLAY:
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
	call_deferred("_sync_viewport_size")
	_refresh_from_state()
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


func automation_click_tile(tile: Vector2i, button_name: String = "left") -> bool:
	if not _tile_in_bounds(tile):
		return false
	_select_tile(tile)
	var entity: Dictionary = entity_layer.get_entity_at_tile(tile)
	_emit_focus(tile, entity)
	match button_name.strip_edges().to_lower():
		"left":
			if _left_click_should_interact(entity):
				_handle_walk_or_interact(tile, entity)
			return true
		"right":
			if entity.is_empty():
				_handle_walk_or_interact(tile, {})
				return true
			var popup_pos := _tile_to_screen(tile)
			_show_context_menu(popup_pos, tile, entity)
			return true
	return false


func _sync_viewport_size() -> void:
	if world_viewport == null:
		return
	if stretch:
		return
	var next_size := Vector2i(maxi(int(size.x), 1), maxi(int(size.y), 1))
	if world_viewport.size != next_size:
		world_viewport.size = next_size

# Legacy public API preserved for game_session.gd compatibility
func command_for_entity(entity: Dictionary) -> String:
	return WorldInteraction.command_for_entity(entity)

func command_for_tile(tile_position: Vector2i) -> String:
	return WorldInteraction.command_for_tile(tile_position, _tile_name_at(tile_position))


func _describe_hover(tile_position: Vector2i, entity: Dictionary) -> String:
	var tile_name := _tile_name_at(tile_position)
	return WorldInteraction.describe_hover(entity, tile_name, tile_position)

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

func _gui_input(event: InputEvent) -> void:
	if _world_input_locked():
		if event is InputEventMouseMotion:
			tooltip_text = ""
			if selection_layer.has_method("clear_hover"):
				selection_layer.clear_hover()
		return
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
	_select_tile(tile)
	var entity: Dictionary = entity_layer.get_entity_at_tile(tile)
	_emit_focus(tile, entity)
	if _left_click_should_interact(entity):
		_handle_walk_or_interact(tile, entity)


func _on_right_click(screen_pos: Vector2) -> void:
	var tile := _screen_to_tile(screen_pos)
	if not _tile_in_bounds(tile):
		return
	_select_tile(tile)
	var entity: Dictionary = entity_layer.get_entity_at_tile(tile)
	_emit_focus(tile, entity)
	if entity.is_empty():
		_handle_walk_or_interact(tile, {})
		return
	_show_context_menu(screen_pos, tile, entity)

func _handle_walk_or_interact(tile: Vector2i, entity: Dictionary) -> void:
	var route := WorldIntentRouter.route_walk_or_interact(
		_walker,
		GameState.player_map_pos,
		tile,
		entity,
		GameState.map_data,
		Callable(self, "_tile_name_at"),
		Callable(self, "_tile_in_bounds"),
	)
	if route.has("commands"):
		command_sequence_requested.emit(route["commands"])
		return
	if route.has("command"):
		command_requested.emit(str(route["command"]))


func _left_click_should_interact(entity: Dictionary) -> bool:
	if entity.is_empty():
		return false
	var bucket := str(entity.get("bucket", "")).strip_edges().to_lower()
	match bucket:
		"npc":
			return true
		"enemy":
			return GameState.is_in_combat()
	return false


func _find_adjacent(target: Vector2i, from: Vector2i) -> Vector2i:
	return WorldIntentRouter._find_adjacent(target, from, Callable(self, "_tile_name_at"), Callable(self, "_tile_in_bounds"))


func _commands_for_path(from_tile: Vector2i, path: Array[Vector2i]) -> Array[String]:
	return WorldIntentRouter._commands_for_path(from_tile, path)

func _show_context_menu(screen_pos: Vector2, tile: Vector2i, entity: Dictionary) -> void:
	if _context_menu != null:
		_context_menu.queue_free()
	_context_menu = PopupMenu.new()
	_context_menu.name = "ContextMenu"
	add_child(_context_menu)
	_context_menu_commands.clear()
	var items: Array[Dictionary]
	if not entity.is_empty():
		items = WorldInteraction.build_entity_menu_items(entity)
	else:
		items = WorldInteraction.build_ground_menu_items(_tile_name_at(tile), tile)
	var item_id := 0
	for item in items:
		var label := str(item.get("label", "")).strip_edges()
		var command := str(item.get("command", "")).strip_edges()
		if label.is_empty() or command.is_empty():
			continue
		_context_menu.add_item(label, item_id)
		_context_menu_commands[item_id] = command
		item_id += 1
	if item_id == 0:
		_context_menu.queue_free()
		_context_menu = null
		return
	_context_menu.id_pressed.connect(_on_context_menu_selected)
	_context_menu.position = Vector2i(int(screen_pos.x + global_position.x), int(screen_pos.y + global_position.y))
	_context_menu.popup()


func _on_context_menu_selected(id: int) -> void:
	var cmd := str(_context_menu_commands.get(id, "")).strip_edges()
	if not cmd.is_empty():
		command_requested.emit(cmd)

func _refresh_from_state(_payload = null) -> void:
	var has_real_map := not GameState.map_data.is_empty()
	var map_payload: Dictionary = GameState.map_data if has_real_map else TileCatalog.build_placeholder_map()
	if map_payload.is_empty():
		map_payload = TileCatalog.build_placeholder_map()
	_update_placeholder_banner(not has_real_map or bool(map_payload.get("placeholder", false)))
	terrain_layer.render_map(map_payload)
	WorldViewPlanner.update_attention_layers(selection_layer, map_payload, GameState.entities)
	_atmosphere_motes = WorldViewPlanner.rebuild_atmosphere(map_payload, size)
	_background_key = WorldViewPlanner.resolve_background_key(GameState.get_display_location(), GameState.scene)
	if ENABLE_WORLD_OVERLAY and _world_overlay != null and _world_overlay.has_method("configure"):
		_world_overlay.configure(_current_adapter_id(), _background_key, _atmosphere_motes, _is_placeholder())
	var player_tile := GameState.player_map_pos
	if player_tile == Vector2i.ZERO and map_payload.has("spawn_point"):
		var sp = map_payload.get("spawn_point", [])
		if sp is Array and sp.size() >= 2:
			player_tile = Vector2i(int(sp[0]), int(sp[1]))
	entity_layer.render_entities(player_tile, GameState.entities, _resolve_player_template())
	world_camera.focus_on_tiles(WorldViewPlanner.camera_focus_tiles(player_tile, GameState.entities), TileCatalog.TILE_SIZE)
	if selection_layer.has_method("set_selected_tile") and player_tile != Vector2i.ZERO:
		selection_layer.set_selected_tile(player_tile)
	_set_focus_summary(WorldFocus.default_summary(GameState.get_display_location(), GameState.entities))
	_set_focus_actions(WorldFocus.default_actions(GameState.entities))

func _update_hover(screen_pos: Vector2) -> void:
	if _world_input_locked():
		tooltip_text = ""
		if selection_layer.has_method("clear_hover"):
			selection_layer.clear_hover()
		return
	var tile := _screen_to_tile(screen_pos)
	if not _tile_in_bounds(tile):
		tooltip_text = ""
		if selection_layer.has_method("clear_hover"):
			selection_layer.clear_hover()
		return
	if selection_layer.has_method("set_hover_tile"):
		selection_layer.set_hover_tile(tile)
	var entity: Dictionary = entity_layer.get_entity_at_tile(tile)
	var tile_name := _tile_name_at(tile)
	tooltip_text = WorldInteraction.describe_hover(entity, tile_name, tile) if not _is_placeholder() else _placeholder_banner.text
	_emit_focus(tile, entity)


func _on_mouse_exited() -> void:
	tooltip_text = ""
	if selection_layer.has_method("clear_hover"):
		selection_layer.clear_hover()
	_set_focus_summary(WorldFocus.default_summary(GameState.get_display_location(), GameState.entities))
	_set_focus_actions(WorldFocus.default_actions(GameState.entities))

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


func _select_tile(tile: Vector2i) -> void:
	if selection_layer.has_method("set_selected_tile"):
		selection_layer.set_selected_tile(tile)
	if selection_layer.has_method("flash_tile"):
		selection_layer.flash_tile(tile)


func _screen_to_tile(screen_pos: Vector2) -> Vector2i:
	var wp := world_camera.position + (screen_pos - Vector2(size) / 2.0) / world_camera.zoom
	return Vector2i(floori(wp.x / TileCatalog.TILE_SIZE), floori(wp.y / TileCatalog.TILE_SIZE))


func _tile_to_screen(tile: Vector2i) -> Vector2:
	var tile_center := Vector2(tile) * TileCatalog.TILE_SIZE + Vector2(TileCatalog.TILE_SIZE / 2.0, TileCatalog.TILE_SIZE / 2.0)
	var viewport_center := Vector2(size) / 2.0
	var delta := (tile_center - world_camera.position) * world_camera.zoom
	return viewport_center + delta


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


func _world_input_locked() -> bool:
	if GameState.has_active_dialog():
		return true
	var current_scene = get_tree().current_scene
	if current_scene == null:
		return false
	var modal = current_scene.get_node_or_null("MainMargin/MainVBox/ContentSplit/ModalHost")
	if modal is Control and modal.visible:
		return true
	var save_panel = current_scene.get_node_or_null("OverlayCanvas/SaveLoadPanel")
	if save_panel is Control and save_panel.visible:
		return true
	return false


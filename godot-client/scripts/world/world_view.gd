extends SubViewportContainer

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

signal command_requested(command_text: String)

@onready var world_viewport: SubViewport = $WorldViewport
@onready var terrain_layer: TileMapLayer = $WorldViewport/WorldRoot/TerrainLayer
@onready var entity_layer: Node2D = $WorldViewport/WorldRoot/EntityLayer
@onready var selection_layer = $WorldViewport/WorldRoot/SelectionLayer
@onready var world_camera: Camera2D = $WorldViewport/WorldRoot/WorldCamera
var _placeholder_banner: Label


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_exited.connect(_on_mouse_exited)
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


func refresh_from_state() -> void:
	_refresh_from_state()


func _refresh_from_state(_payload = null) -> void:
	var has_real_map := not GameState.map_data.is_empty()
	var map_payload: Dictionary = GameState.map_data if has_real_map else TileCatalog.build_placeholder_map()
	if map_payload.is_empty():
		map_payload = TileCatalog.build_placeholder_map()
	_update_placeholder_banner(not has_real_map or bool(map_payload.get("placeholder", false)))
	terrain_layer.render_map(map_payload)

	var player_tile = GameState.player_map_pos
	if player_tile == Vector2i.ZERO and map_payload.has("spawn_point"):
		var spawn_point = map_payload.get("spawn_point", [])
		if spawn_point is Array and spawn_point.size() >= 2:
			player_tile = Vector2i(int(spawn_point[0]), int(spawn_point[1]))

	entity_layer.render_entities(player_tile, GameState.entities, _resolve_player_template())
	world_camera.focus_on_tile(player_tile, TileCatalog.TILE_SIZE)
	if selection_layer.has_method("set_selected_tile") and player_tile != Vector2i.ZERO:
		selection_layer.set_selected_tile(player_tile)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_update_hover(event.position)
		return

	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT:
			var tile_position = _screen_to_tile(event.position)
			if not _tile_in_bounds(tile_position):
				return
			if selection_layer.has_method("set_selected_tile"):
				selection_layer.set_selected_tile(tile_position)
			var entity = entity_layer.get_entity_at_tile(tile_position)
			if not entity.is_empty():
				command_requested.emit(command_for_entity(entity))
			else:
				command_requested.emit(command_for_tile(tile_position))
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			world_camera.zoom_in()
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			world_camera.zoom_out()
			accept_event()


func command_for_entity(entity: Dictionary) -> String:
	var entity_name = str(entity.get("name", "")).strip_edges().to_lower()
	if entity_name.is_empty():
		entity_name = "target"
	var actions = entity.get("context_actions", [])
	if actions is Array and not actions.is_empty():
		var primary_action = str(actions[0]).strip_edges().to_lower()
		match primary_action:
			"pick up":
				return "pick up %s" % entity_name
			"attack":
				return "attack %s" % entity_name
			"trade":
				return "trade %s" % entity_name
			"talk":
				return "talk %s" % entity_name
			"examine":
				return "examine %s" % entity_name
	var bucket = str(entity.get("bucket", "npc"))
	match bucket:
		"enemy":
			return "attack %s" % entity_name
		"item":
			return "pick up %s" % entity_name
		_:
			return "talk %s" % entity_name


func command_for_tile(tile_position: Vector2i) -> String:
	var tile_name = _tile_name_at(tile_position)
	match tile_name:
		"door":
			return "open door"
		"well", "fountain", "tree":
			return "examine %s" % tile_name
	return "move to %d,%d" % [tile_position.x, tile_position.y]


func _resolve_player_template() -> String:
	if GameState.player.has("classes") and GameState.player["classes"] is Dictionary and not GameState.player["classes"].is_empty():
		var class_keys = GameState.player["classes"].keys()
		return str(class_keys[0]).to_lower()
	if GameState.player.has("player_class"):
		return str(GameState.player["player_class"]).to_lower()
	return "warrior"


func _screen_to_tile(screen_position: Vector2) -> Vector2i:
	var world_position = _screen_to_world(screen_position)
	return Vector2i(
		floori(world_position.x / TileCatalog.TILE_SIZE),
		floori(world_position.y / TileCatalog.TILE_SIZE)
	)


func _screen_to_world(screen_position: Vector2) -> Vector2:
	var viewport_size = Vector2(size)
	return world_camera.position + (screen_position - viewport_size / 2.0) / world_camera.zoom


func _update_hover(screen_position: Vector2) -> void:
	var tile_position = _screen_to_tile(screen_position)
	if not _tile_in_bounds(tile_position):
		tooltip_text = ""
		if selection_layer.has_method("clear_hover"):
			selection_layer.clear_hover()
		return
	if selection_layer.has_method("set_hover_tile"):
		selection_layer.set_hover_tile(tile_position)
	var entity = entity_layer.get_entity_at_tile(tile_position)
	tooltip_text = _describe_hover(tile_position, entity)


func _describe_hover(tile_position: Vector2i, entity: Dictionary) -> String:
	if _placeholder_banner != null and _placeholder_banner.visible:
		return _placeholder_banner.text
	if not entity.is_empty():
		var actions = entity.get("context_actions", [])
		if actions is Array and not actions.is_empty():
			return "%s (%s)" % [str(entity.get("name", "Unknown")), ", ".join(actions)]
		return str(entity.get("name", "Unknown"))
	var tile_name = _tile_name_at(tile_position)
	if tile_name in ["door", "well", "fountain", "tree"]:
		return "%s (%s)" % [tile_name.capitalize(), command_for_tile(tile_position)]
	return "Tile %d, %d" % [tile_position.x, tile_position.y]


func _tile_in_bounds(tile_position: Vector2i) -> bool:
	var width = int(GameState.map_data.get("width", 0))
	var height = int(GameState.map_data.get("height", 0))
	if width <= 0 or height <= 0:
		return tile_position.x >= 0 and tile_position.y >= 0
	return tile_position.x >= 0 and tile_position.y >= 0 and tile_position.x < width and tile_position.y < height


func _tile_name_at(tile_position: Vector2i) -> String:
	var tiles = GameState.map_data.get("tiles", [])
	if not (tiles is Array) or tile_position.y < 0 or tile_position.y >= tiles.size():
		return ""
	var row = tiles[tile_position.y]
	if not (row is Array) or tile_position.x < 0 or tile_position.x >= row.size():
		return ""
	return TileCatalog.resolve_tile_name(row[tile_position.x])


func capture_world_image() -> Image:
	return world_viewport.get_texture().get_image()


func capture_world_screenshot(folder: String, prefix: String) -> String:
	var image = capture_world_image()
	var screenshot_capture = preload("res://scripts/ui/screenshot_capture.gd")
	return screenshot_capture.capture_image(image, folder, prefix)


func _update_placeholder_banner(is_placeholder: bool) -> void:
	if _placeholder_banner == null:
		return
	_placeholder_banner.visible = is_placeholder
	if is_placeholder:
		_placeholder_banner.text = "Placeholder map: waiting for campaign data"


func _on_mouse_exited() -> void:
	tooltip_text = ""
	if selection_layer.has_method("clear_hover"):
		selection_layer.clear_hover()

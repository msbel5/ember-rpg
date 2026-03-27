extends SubViewportContainer

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

signal command_requested(command_text: String)

@onready var world_viewport: SubViewport = $WorldViewport
@onready var terrain_layer: TileMapLayer = $WorldViewport/WorldRoot/TerrainLayer
@onready var entity_layer: Node2D = $WorldViewport/WorldRoot/EntityLayer
@onready var selection_layer = $WorldViewport/WorldRoot/SelectionLayer
@onready var world_camera: Camera2D = $WorldViewport/WorldRoot/WorldCamera


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_exited.connect(_on_mouse_exited)

	if get_node_or_null("/root/GameState") != null:
		GameState.map_loaded.connect(_refresh_from_state)
		GameState.entities_loaded.connect(_refresh_from_state)
		GameState.state_updated.connect(_refresh_from_state)

	_refresh_from_state()


func refresh_from_state() -> void:
	_refresh_from_state()


func _refresh_from_state(_payload = null) -> void:
	var map_payload: Dictionary = GameState.map_data if not GameState.map_data.is_empty() else TileCatalog.build_placeholder_map()
	if map_payload.is_empty():
		map_payload = TileCatalog.build_placeholder_map()
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
				command_requested.emit("move to %d,%d" % [tile_position.x, tile_position.y])
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			world_camera.zoom_in()
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			world_camera.zoom_out()
			accept_event()


func command_for_entity(entity: Dictionary) -> String:
	var bucket = str(entity.get("bucket", "npc"))
	var entity_name = str(entity.get("name", "")).strip_edges().to_lower()
	if entity_name.is_empty():
		entity_name = "target"
	match bucket:
		"enemy":
			return "attack %s" % entity_name
		"item":
			return "examine %s" % entity_name
		_:
			return "talk %s" % entity_name


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
	if not entity.is_empty():
		var actions = entity.get("context_actions", [])
		if actions is Array and not actions.is_empty():
			return "%s (%s)" % [str(entity.get("name", "Unknown")), ", ".join(actions)]
		return str(entity.get("name", "Unknown"))
	return "Tile %d, %d" % [tile_position.x, tile_position.y]


func _tile_in_bounds(tile_position: Vector2i) -> bool:
	var width = int(GameState.map_data.get("width", 0))
	var height = int(GameState.map_data.get("height", 0))
	if width <= 0 or height <= 0:
		return tile_position.x >= 0 and tile_position.y >= 0
	return tile_position.x >= 0 and tile_position.y >= 0 and tile_position.x < width and tile_position.y < height


func _on_mouse_exited() -> void:
	tooltip_text = ""
	if selection_layer.has_method("clear_hover"):
		selection_layer.clear_hover()

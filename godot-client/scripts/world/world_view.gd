extends SubViewportContainer

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

@onready var world_viewport: SubViewport = $WorldViewport
@onready var terrain_layer: TileMapLayer = $WorldViewport/WorldRoot/TerrainLayer
@onready var entity_layer: Node2D = $WorldViewport/WorldRoot/EntityLayer
@onready var world_camera: Camera2D = $WorldViewport/WorldRoot/WorldCamera


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP

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

	entity_layer.render_entities(player_tile, GameState.entities)
	world_camera.focus_on_tile(player_tile, TileCatalog.TILE_SIZE)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			world_camera.zoom_in()
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			world_camera.zoom_out()
			accept_event()

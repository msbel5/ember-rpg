extends Camera2D

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const ZOOM_STEPS := [1.0, 2.0, 3.0, 4.0]

var _zoom_index: int = 3


func _ready() -> void:
	make_current()
	position_smoothing_enabled = true
	position_smoothing_speed = 8.0
	set_zoom_index(_zoom_index)


func focus_on_tile(tile_position: Vector2i, tile_size: int = TileCatalog.TILE_SIZE) -> void:
	position = Vector2(
		(tile_position.x + 0.5) * tile_size,
		(tile_position.y + 0.5) * tile_size
	)


func focus_on_tiles(tile_positions: Array, tile_size: int = TileCatalog.TILE_SIZE) -> void:
	if tile_positions.is_empty():
		return
	var min_x = 1_000_000
	var min_y = 1_000_000
	var max_x = -1_000_000
	var max_y = -1_000_000
	for tile_position in tile_positions:
		if not (tile_position is Vector2i):
			continue
		min_x = mini(min_x, tile_position.x)
		min_y = mini(min_y, tile_position.y)
		max_x = maxi(max_x, tile_position.x)
		max_y = maxi(max_y, tile_position.y)
	if min_x > max_x or min_y > max_y:
		return
	var center_tile = Vector2(
		(float(min_x + max_x) / 2.0) + 0.5,
		(float(min_y + max_y) / 2.0) + 0.5
	)
	position = center_tile * tile_size
	var span_x = max_x - min_x + 1
	var span_y = max_y - min_y + 1
	var widest_span = maxi(span_x, span_y)
	var desired_zoom_index := 3
	if widest_span >= 12 or tile_positions.size() >= 7:
		desired_zoom_index = 1
	elif widest_span >= 7 or tile_positions.size() >= 4:
		desired_zoom_index = 2
	set_zoom_index(desired_zoom_index)


func zoom_in() -> void:
	set_zoom_index(_zoom_index + 1)


func zoom_out() -> void:
	set_zoom_index(_zoom_index - 1)


func set_zoom_index(next_index: int) -> void:
	_zoom_index = clampi(next_index, 0, ZOOM_STEPS.size() - 1)
	var zoom_value = ZOOM_STEPS[_zoom_index]
	zoom = Vector2(zoom_value, zoom_value)


func get_zoom_index() -> int:
	return _zoom_index

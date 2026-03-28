extends Camera2D

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const ZOOM_STEPS := [1.0, 2.0, 3.0, 4.0]

var _zoom_index: int = 2


func _ready() -> void:
	make_current()
	set_zoom_index(_zoom_index)


func focus_on_tile(tile_position: Vector2i, tile_size: int = TileCatalog.TILE_SIZE) -> void:
	position = Vector2(
		(tile_position.x + 0.5) * tile_size,
		(tile_position.y + 0.5) * tile_size
	)


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

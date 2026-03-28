extends Node2D
class_name SelectionOverlay

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const FLASH_DURATION := 0.35
const INTEREST_FILL := Color(0.94, 0.78, 0.30, 0.14)
const INTEREST_OUTLINE := Color(0.96, 0.82, 0.44, 0.62)
const HOSTILE_FILL := Color(0.86, 0.18, 0.18, 0.12)
const HOSTILE_OUTLINE := Color(0.96, 0.28, 0.24, 0.60)
const AMBIENT_FILL := Color(0.34, 0.76, 0.94, 0.14)
const AMBIENT_SPARK := Color(0.78, 0.94, 1.00, 0.52)

var hover_tile: Vector2i = Vector2i(-1, -1)
var selected_tile: Vector2i = Vector2i(-1, -1)
var flash_tile_position: Vector2i = Vector2i(-1, -1)
var flash_strength: float = 0.0
var _pulse_time: float = 0.0
var _interest_tiles: Dictionary = {}
var _hostile_tiles: Dictionary = {}
var _ambient_tiles: Dictionary = {}


func _process(delta: float) -> void:
	_pulse_time += delta
	if flash_strength > 0.0:
		flash_strength = maxf(flash_strength - delta / FLASH_DURATION, 0.0)
		if flash_strength <= 0.0:
			flash_tile_position = Vector2i(-1, -1)
	queue_redraw()


func set_hover_tile(tile_position: Vector2i) -> void:
	if hover_tile == tile_position:
		return
	hover_tile = tile_position
	queue_redraw()


func set_selected_tile(tile_position: Vector2i) -> void:
	if selected_tile == tile_position:
		return
	selected_tile = tile_position
	queue_redraw()


func clear_hover() -> void:
	set_hover_tile(Vector2i(-1, -1))


func clear_selection() -> void:
	set_selected_tile(Vector2i(-1, -1))


func flash_tile(tile_position: Vector2i) -> void:
	flash_tile_position = tile_position
	flash_strength = 1.0
	_update_processing_state()
	queue_redraw()


func set_interest_tiles(tile_positions: Array) -> void:
	_interest_tiles = _tile_dictionary(tile_positions)
	_update_processing_state()
	queue_redraw()


func set_hostile_tiles(tile_positions: Array) -> void:
	_hostile_tiles = _tile_dictionary(tile_positions)
	_update_processing_state()
	queue_redraw()


func set_ambient_tiles(tile_positions: Array) -> void:
	_ambient_tiles = _tile_dictionary(tile_positions)
	_update_processing_state()
	queue_redraw()


func get_interest_tile_count() -> int:
	return _interest_tiles.size()


func get_hostile_tile_count() -> int:
	return _hostile_tiles.size()


func get_ambient_tile_count() -> int:
	return _ambient_tiles.size()


func _draw() -> void:
	var interest_alpha = 0.05 + (sin(_pulse_time * 1.8) * 0.5 + 0.5) * 0.05
	var hostile_alpha = 0.05 + (sin(_pulse_time * 2.4 + 0.8) * 0.5 + 0.5) * 0.05
	var ambient_alpha = 0.05 + (sin(_pulse_time * 2.6 + 0.2) * 0.5 + 0.5) * 0.07
	for tile_position in _ambient_tiles.values():
		_draw_tile_fill(tile_position, Color(AMBIENT_FILL.r, AMBIENT_FILL.g, AMBIENT_FILL.b, ambient_alpha))
		_draw_ambient_spray(tile_position, ambient_alpha)
	for tile_position in _interest_tiles.values():
		_draw_tile_fill(tile_position, Color(INTEREST_FILL.r, INTEREST_FILL.g, INTEREST_FILL.b, interest_alpha))
		_draw_tile_outline(tile_position, Color(INTEREST_OUTLINE.r, INTEREST_OUTLINE.g, INTEREST_OUTLINE.b, INTEREST_OUTLINE.a + interest_alpha), 1.2)
		_draw_tile_ping(tile_position, Color(1.0, 0.90, 0.56, 0.28 + interest_alpha), 2.6 + sin(_pulse_time * 2.2) * 0.5)
		_draw_tile_corner_marks(tile_position, Color(1.0, 0.92, 0.62, 0.44 + interest_alpha), 3.0)
	for tile_position in _hostile_tiles.values():
		_draw_tile_fill(tile_position, Color(HOSTILE_FILL.r, HOSTILE_FILL.g, HOSTILE_FILL.b, hostile_alpha))
		_draw_tile_outline(tile_position, Color(HOSTILE_OUTLINE.r, HOSTILE_OUTLINE.g, HOSTILE_OUTLINE.b, HOSTILE_OUTLINE.a + hostile_alpha), 1.5)
		_draw_tile_ping(tile_position, Color(1.0, 0.42, 0.32, 0.24 + hostile_alpha), 2.8 + sin(_pulse_time * 2.8 + 0.6) * 0.6)
		_draw_tile_corner_marks(tile_position, Color(1.0, 0.48, 0.36, 0.42 + hostile_alpha), 3.0)
	_draw_tile_fill(flash_tile_position, Color(0.20, 0.92, 1.0, 0.16 + flash_strength * 0.28))
	_draw_tile_outline(hover_tile, Color(1.0, 1.0, 1.0, 0.88), 1.5)
	_draw_tile_outline(selected_tile, Color(0.16, 0.92, 1.0, 0.96), 2.2)
	_draw_tile_outline(flash_tile_position, Color(0.40, 0.96, 1.0, 0.40 + flash_strength * 0.45), 2.8)


func _draw_tile_fill(tile_position: Vector2i, color: Color) -> void:
	if tile_position.x < 0 or tile_position.y < 0 or color.a <= 0.0:
		return
	var rect = Rect2(
		Vector2(tile_position.x * TileCatalog.TILE_SIZE, tile_position.y * TileCatalog.TILE_SIZE),
		Vector2(TileCatalog.TILE_SIZE, TileCatalog.TILE_SIZE)
	)
	draw_rect(rect, color, true)


func _draw_tile_outline(tile_position: Vector2i, color: Color, width: float) -> void:
	if tile_position.x < 0 or tile_position.y < 0:
		return
	var rect = Rect2(
		Vector2(tile_position.x * TileCatalog.TILE_SIZE, tile_position.y * TileCatalog.TILE_SIZE),
		Vector2(TileCatalog.TILE_SIZE, TileCatalog.TILE_SIZE)
	)
	draw_rect(rect, color, false, width)


func _draw_tile_ping(tile_position: Vector2i, color: Color, radius: float) -> void:
	if tile_position.x < 0 or tile_position.y < 0 or color.a <= 0.0:
		return
	var center = Vector2(
		tile_position.x * TileCatalog.TILE_SIZE + TileCatalog.TILE_SIZE * 0.5,
		tile_position.y * TileCatalog.TILE_SIZE + TileCatalog.TILE_SIZE * 0.5
	)
	draw_circle(center, radius, color)


func _draw_tile_corner_marks(tile_position: Vector2i, color: Color, corner_length: float) -> void:
	if tile_position.x < 0 or tile_position.y < 0 or color.a <= 0.0:
		return
	var left = float(tile_position.x * TileCatalog.TILE_SIZE)
	var top = float(tile_position.y * TileCatalog.TILE_SIZE)
	var right = left + TileCatalog.TILE_SIZE
	var bottom = top + TileCatalog.TILE_SIZE
	draw_line(Vector2(left, top), Vector2(left + corner_length, top), color, 1.2)
	draw_line(Vector2(left, top), Vector2(left, top + corner_length), color, 1.2)
	draw_line(Vector2(right, top), Vector2(right - corner_length, top), color, 1.2)
	draw_line(Vector2(right, top), Vector2(right, top + corner_length), color, 1.2)
	draw_line(Vector2(left, bottom), Vector2(left + corner_length, bottom), color, 1.2)
	draw_line(Vector2(left, bottom), Vector2(left, bottom - corner_length), color, 1.2)
	draw_line(Vector2(right, bottom), Vector2(right - corner_length, bottom), color, 1.2)
	draw_line(Vector2(right, bottom), Vector2(right, bottom - corner_length), color, 1.2)


func _draw_ambient_spray(tile_position: Vector2i, alpha: float) -> void:
	if tile_position.x < 0 or tile_position.y < 0 or alpha <= 0.0:
		return
	var center = Vector2(
		tile_position.x * TileCatalog.TILE_SIZE + TileCatalog.TILE_SIZE * 0.5,
		tile_position.y * TileCatalog.TILE_SIZE + TileCatalog.TILE_SIZE * 0.5
	)
	draw_circle(center, 4.2 + sin(_pulse_time * 2.2) * 0.5, Color(0.30, 0.70, 0.90, alpha * 0.75))
	for index in range(3):
		var phase = _pulse_time * (2.4 + index * 0.28) + index * 1.2
		var droplet = center + Vector2((index - 1) * 2.1, -3.0 - sin(phase) * 3.0)
		draw_circle(droplet, 1.1 + index * 0.15, Color(AMBIENT_SPARK.r, AMBIENT_SPARK.g, AMBIENT_SPARK.b, alpha * (0.55 + index * 0.10)))
	draw_line(center + Vector2(0, -1.0), center + Vector2(0, -4.5 - sin(_pulse_time * 2.8) * 1.8), Color(0.70, 0.94, 1.0, alpha * 0.6), 1.0)


func _tile_dictionary(tile_positions: Array) -> Dictionary:
	var result: Dictionary = {}
	for tile_position in tile_positions:
		if tile_position is Vector2i and tile_position.x >= 0 and tile_position.y >= 0:
			result["%d,%d" % [tile_position.x, tile_position.y]] = tile_position
	return result


func _update_processing_state() -> void:
	set_process(
		flash_strength > 0.0
		or not _interest_tiles.is_empty()
		or not _hostile_tiles.is_empty()
		or not _ambient_tiles.is_empty()
	)

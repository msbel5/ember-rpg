extends Node2D
class_name SelectionOverlay

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const FLASH_DURATION := 0.35

var hover_tile: Vector2i = Vector2i(-1, -1)
var selected_tile: Vector2i = Vector2i(-1, -1)
var flash_tile_position: Vector2i = Vector2i(-1, -1)
var flash_strength: float = 0.0


func _process(delta: float) -> void:
	if flash_strength <= 0.0:
		return
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
	set_process(true)
	queue_redraw()


func _draw() -> void:
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

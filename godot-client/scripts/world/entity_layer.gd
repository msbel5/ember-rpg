extends Node2D

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

var _marker_textures: Dictionary = {}


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_ensure_marker_textures()


func render_entities(player_tile: Vector2i, grouped_entities: Dictionary) -> void:
	_ensure_marker_textures()
	_clear_runtime_children()

	_create_marker("player", player_tile)
	for npc in grouped_entities.get("npcs", []):
		_create_marker("npc", _extract_position(npc))
	for enemy in grouped_entities.get("enemies", []):
		_create_marker("enemy", _extract_position(enemy))
	for item in grouped_entities.get("items", []):
		_create_marker("item", _extract_position(item))


func _extract_position(entry: Dictionary) -> Vector2i:
	var position_data = entry.get("position", [0, 0])
	if position_data is Array and position_data.size() >= 2:
		return Vector2i(int(position_data[0]), int(position_data[1]))
	return Vector2i.ZERO


func _create_marker(kind: String, tile_position: Vector2i) -> void:
	var sprite = Sprite2D.new()
	sprite.texture = _marker_textures.get(kind, _marker_textures["player"])
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.centered = true
	sprite.position = Vector2(
		(tile_position.x + 0.5) * TileCatalog.TILE_SIZE,
		(tile_position.y + 0.5) * TileCatalog.TILE_SIZE
	)
	add_child(sprite)


func _ensure_marker_textures() -> void:
	if not _marker_textures.is_empty():
		return
	_marker_textures = {
		"player": _build_circle_texture(Color(0.18, 0.78, 0.92)),
		"npc": _build_circle_texture(Color(0.92, 0.78, 0.30)),
		"enemy": _build_diamond_texture(Color(0.84, 0.24, 0.24)),
		"item": _build_square_texture(Color(0.38, 0.82, 0.46)),
	}


func _build_circle_texture(color: Color) -> Texture2D:
	var image = Image.create(TileCatalog.TILE_SIZE, TileCatalog.TILE_SIZE, false, Image.FORMAT_RGBA8)
	for y in range(TileCatalog.TILE_SIZE):
		for x in range(TileCatalog.TILE_SIZE):
			var dx = x - (TileCatalog.TILE_SIZE / 2.0) + 0.5
			var dy = y - (TileCatalog.TILE_SIZE / 2.0) + 0.5
			if sqrt(dx * dx + dy * dy) <= 5.5:
				image.set_pixel(x, y, color)
	return ImageTexture.create_from_image(image)


func _build_diamond_texture(color: Color) -> Texture2D:
	var image = Image.create(TileCatalog.TILE_SIZE, TileCatalog.TILE_SIZE, false, Image.FORMAT_RGBA8)
	var mid = int(TileCatalog.TILE_SIZE / 2)
	for y in range(TileCatalog.TILE_SIZE):
		for x in range(TileCatalog.TILE_SIZE):
			if abs(x - mid) + abs(y - mid) <= 5:
				image.set_pixel(x, y, color)
	return ImageTexture.create_from_image(image)


func _build_square_texture(color: Color) -> Texture2D:
	var image = Image.create(TileCatalog.TILE_SIZE, TileCatalog.TILE_SIZE, false, Image.FORMAT_RGBA8)
	image.fill_rect(Rect2i(3, 3, TileCatalog.TILE_SIZE - 6, TileCatalog.TILE_SIZE - 6), color)
	return ImageTexture.create_from_image(image)


func _clear_runtime_children() -> void:
	for child in get_children():
		child.queue_free()

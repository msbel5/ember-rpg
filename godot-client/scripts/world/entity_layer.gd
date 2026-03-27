extends Node2D

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const EntitySpriteCatalog = preload("res://scripts/world/entity_sprite_catalog.gd")
const ADAPTER_BUCKET_TINTS := {
	"fantasy_ember": {
		"player": Color(1.00, 0.95, 0.86),
		"npc": Color(1.00, 0.90, 0.72),
		"enemy": Color(0.96, 0.54, 0.42),
		"item": Color(0.88, 1.00, 0.84),
	},
	"scifi_frontier": {
		"player": Color(0.76, 0.95, 1.00),
		"npc": Color(0.76, 1.00, 0.92),
		"enemy": Color(1.00, 0.58, 0.76),
		"item": Color(0.94, 1.00, 0.72),
	},
}

var _marker_textures: Dictionary = {}
var _entities_by_tile: Dictionary = {}


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_ensure_marker_textures()


func render_entities(player_tile: Vector2i, grouped_entities: Dictionary, player_template: String = "warrior") -> void:
	_ensure_marker_textures()
	_clear_runtime_children()
	_entities_by_tile.clear()

	_create_sprite_entity({
		"id": "player",
		"name": "Player",
		"template": player_template,
		"position": [player_tile.x, player_tile.y],
		"bucket": "player",
	})
	for npc in grouped_entities.get("npcs", []):
		_create_sprite_entity(_with_bucket(npc, "npc"))
	for enemy in grouped_entities.get("enemies", []):
		_create_sprite_entity(_with_bucket(enemy, "enemy"))
	for item in grouped_entities.get("items", []):
		_create_sprite_entity(_with_bucket(item, "item"))


func get_entity_at_tile(tile_position: Vector2i) -> Dictionary:
	var tile_key = _tile_key(tile_position)
	if not _entities_by_tile.has(tile_key):
		return {}
	var entries: Array = _entities_by_tile[tile_key]
	if entries.is_empty():
		return {}
	return entries[0]


func _with_bucket(entry: Dictionary, bucket: String) -> Dictionary:
	var normalized = entry.duplicate(true)
	normalized["bucket"] = bucket
	return normalized


func _extract_position(entry: Dictionary) -> Vector2i:
	var position_data = entry.get("position", [0, 0])
	if position_data is Array and position_data.size() >= 2:
		return Vector2i(int(position_data[0]), int(position_data[1]))
	return Vector2i.ZERO


func _create_sprite_entity(entry: Dictionary) -> void:
	var tile_position = _extract_position(entry)
	var sprite = Sprite2D.new()
	var texture = EntitySpriteCatalog.resolve_texture(str(entry.get("template", "warrior")))
	if texture != null:
		sprite.texture = texture
		var width = texture.get_width()
		if width > TileCatalog.TILE_SIZE and width > 0:
			var scale_factor = float(TileCatalog.TILE_SIZE) / float(width)
			sprite.scale = Vector2(scale_factor, scale_factor)
	else:
		var bucket = str(entry.get("bucket", "npc"))
		sprite.texture = _marker_textures.get(bucket, _marker_textures["player"])
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.centered = true
	sprite.modulate = adapter_bucket_tint(str(entry.get("bucket", "npc")), _current_adapter_id())
	sprite.position = _tile_to_world(tile_position)
	add_child(sprite)
	_register_entity(tile_position, entry)


func _create_marker(kind: String, tile_position: Vector2i) -> void:
	var sprite = Sprite2D.new()
	sprite.texture = _marker_textures.get(kind, _marker_textures["player"])
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.centered = true
	sprite.position = _tile_to_world(tile_position)
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


func _register_entity(tile_position: Vector2i, entry: Dictionary) -> void:
	var tile_key = _tile_key(tile_position)
	if not _entities_by_tile.has(tile_key):
		_entities_by_tile[tile_key] = []
	var entries: Array = _entities_by_tile[tile_key]
	entries.append(entry)
	_entities_by_tile[tile_key] = entries


func _tile_key(tile_position: Vector2i) -> String:
	return "%d,%d" % [tile_position.x, tile_position.y]


func _tile_to_world(tile_position: Vector2i) -> Vector2:
	return Vector2(
		(tile_position.x + 0.5) * TileCatalog.TILE_SIZE,
		(tile_position.y + 0.5) * TileCatalog.TILE_SIZE
	)


static func adapter_bucket_tint(bucket: String, adapter_id: String) -> Color:
	var normalized_adapter = adapter_id.strip_edges().to_lower()
	var normalized_bucket = bucket.strip_edges().to_lower()
	var palette = ADAPTER_BUCKET_TINTS.get(normalized_adapter, ADAPTER_BUCKET_TINTS["fantasy_ember"])
	return palette.get(normalized_bucket, Color.WHITE)


func _current_adapter_id() -> String:
	var loop = Engine.get_main_loop()
	if loop is SceneTree:
		var game_state = loop.root.get_node_or_null("GameState")
		if game_state != null:
			return str(game_state.adapter_id)
	return "fantasy_ember"

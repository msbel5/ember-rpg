extends Node2D

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const EntitySpriteCatalog = preload("res://scripts/world/entity_sprite_catalog.gd")
const ADAPTER_BUCKET_TINTS := {
	"fantasy_ember": {
		"player": Color(1.00, 0.95, 0.86),
		"npc": Color(1.00, 0.90, 0.72),
		"enemy": Color(0.96, 0.54, 0.42),
		"item": Color(0.88, 1.00, 0.84),
		"furniture": Color(0.78, 0.72, 0.62),
	},
	"scifi_frontier": {
		"player": Color(0.76, 0.95, 1.00),
		"npc": Color(0.76, 1.00, 0.92),
		"enemy": Color(1.00, 0.58, 0.76),
		"item": Color(0.94, 1.00, 0.72),
		"furniture": Color(0.68, 0.74, 0.82),
	},
}

var _marker_textures: Dictionary = {}
var _shadow_texture: Texture2D
var _entities_by_tile: Dictionary = {}


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_ensure_marker_textures()
	_ensure_shadow_texture()


func render_entities(player_tile: Vector2i, grouped_entities: Dictionary, player_template: String = "warrior") -> void:
	_ensure_marker_textures()
	_ensure_shadow_texture()
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
	for furniture in grouped_entities.get("furniture", []):
		_create_sprite_entity(_with_bucket(furniture, "furniture"))


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
	var bucket = str(entry.get("bucket", "npc"))
	var actor = Node2D.new()
	actor.name = str(entry.get("id", "%s_%d_%d" % [bucket, tile_position.x, tile_position.y]))
	actor.position = _tile_to_world(tile_position)
	actor.z_index = tile_position.y

	var shadow = Sprite2D.new()
	shadow.name = "Shadow"
	shadow.texture = _shadow_texture
	shadow.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	shadow.centered = true
	shadow.modulate = Color(0.0, 0.0, 0.0, _shadow_alpha_for_bucket(bucket))
	shadow.position = Vector2(0, 4)
	var shadow_scale = _shadow_scale_for_bucket(bucket)
	shadow.scale = Vector2(shadow_scale, shadow_scale)
	actor.add_child(shadow)

	var sprite = Sprite2D.new()
	sprite.name = "Body"
	var texture = EntitySpriteCatalog.resolve_texture(str(entry.get("template", "warrior")))
	var using_fallback := false
	if texture != null:
		sprite.texture = texture
		var max_dimension = maxi(texture.get_width(), texture.get_height())
		if max_dimension > 0:
			var scale_factor = float(display_size_for_bucket(bucket)) / float(max_dimension)
			sprite.scale = Vector2(scale_factor, scale_factor)
	else:
		using_fallback = true
		sprite.texture = _marker_textures.get(bucket, _marker_textures["player"])
		var fallback_dimension = maxi(sprite.texture.get_width(), sprite.texture.get_height())
		if fallback_dimension > 0:
			var fallback_scale = float(display_size_for_bucket(bucket)) / float(fallback_dimension)
			sprite.scale = Vector2(fallback_scale, fallback_scale)
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.centered = true
	sprite.modulate = _body_modulate(bucket, _current_adapter_id(), using_fallback)
	sprite.position = Vector2(0, -_body_lift_for_bucket(bucket))
	actor.add_child(sprite)

	add_child(actor)
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
		"furniture": _build_square_texture(Color(0.62, 0.54, 0.42)),
	}


func _ensure_shadow_texture() -> void:
	if _shadow_texture != null:
		return
	var image = Image.create(TileCatalog.TILE_SIZE, int(TileCatalog.TILE_SIZE / 2), false, Image.FORMAT_RGBA8)
	var center = Vector2(float(image.get_width()) / 2.0, float(image.get_height()) / 2.0)
	for y in range(image.get_height()):
		for x in range(image.get_width()):
			var normalized_x = (float(x) - center.x) / maxf(center.x - 1.0, 1.0)
			var normalized_y = (float(y) - center.y) / maxf(center.y - 1.0, 1.0)
			var distance = normalized_x * normalized_x + normalized_y * normalized_y
			if distance <= 1.0:
				var alpha = clampf(1.0 - distance, 0.0, 1.0) * 0.7
				image.set_pixel(x, y, Color(0.0, 0.0, 0.0, alpha))
	_shadow_texture = ImageTexture.create_from_image(image)


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


static func display_size_for_bucket(bucket: String) -> int:
	match bucket.strip_edges().to_lower():
		"player":
			return 30
		"enemy":
			return 24
		"furniture":
			return 22
		"item":
			return 18
		_:
			return 22


static func _body_modulate(bucket: String, adapter_id: String, using_fallback: bool) -> Color:
	if using_fallback:
		return adapter_bucket_tint(bucket, adapter_id)
	var tint = adapter_bucket_tint(bucket, adapter_id)
	var blend = 0.08 if bucket == "player" else 0.16
	return Color.WHITE.lerp(tint, blend)


static func _body_lift_for_bucket(bucket: String) -> float:
	var extra_height = maxf(float(display_size_for_bucket(bucket) - TileCatalog.TILE_SIZE), 0.0)
	return 4.0 + extra_height * 0.42


static func _shadow_alpha_for_bucket(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"item":
			return 0.18
		"furniture":
			return 0.26
		"player":
			return 0.34
		_:
			return 0.28


static func _shadow_scale_for_bucket(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"player":
			return 1.25
		"enemy", "npc":
			return 1.05
		"furniture":
			return 1.15
		"item":
			return 0.70
		_:
			return 0.95


func _current_adapter_id() -> String:
	var loop = Engine.get_main_loop()
	if loop is SceneTree:
		var game_state = loop.root.get_node_or_null("GameState")
		if game_state != null:
			return str(game_state.adapter_id)
	return "fantasy_ember"

extends Node2D

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const EntitySpriteCatalog = preload("res://scripts/world/entity_sprite_catalog.gd")
const MOVE_TWEEN_DURATION := 0.24
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
var _actors_by_id: Dictionary = {}
var _motion_time: float = 0.0


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	y_sort_enabled = true
	set_process(true)
	_ensure_marker_textures()
	_ensure_shadow_texture()


func render_entities(player_tile: Vector2i, grouped_entities: Dictionary, player_template: String = "warrior") -> void:
	_ensure_marker_textures()
	_ensure_shadow_texture()
	var desired_ids: Dictionary = {}
	var next_entities_by_tile: Dictionary = {}
	var render_entries: Array = [{
		"id": "player",
		"name": "Player",
		"template": player_template,
		"position": [player_tile.x, player_tile.y],
		"bucket": "player",
	}]
	for npc in grouped_entities.get("npcs", []):
		render_entries.append(_with_bucket(npc, "npc"))
	for enemy in grouped_entities.get("enemies", []):
		render_entries.append(_with_bucket(enemy, "enemy"))
	for item in grouped_entities.get("items", []):
		render_entries.append(_with_bucket(item, "item"))
	for furniture in grouped_entities.get("furniture", []):
		render_entries.append(_with_bucket(furniture, "furniture"))

	for index in range(render_entries.size()):
		var entry = render_entries[index]
		if not (entry is Dictionary):
			continue
		var normalized: Dictionary = entry.duplicate(true)
		var actor_id = _actor_id_for_entry(normalized, index)
		var tile_position = _extract_position(normalized)
		desired_ids[actor_id] = true
		_upsert_actor(actor_id, normalized, tile_position)
		_register_entity(next_entities_by_tile, tile_position, normalized)

	_remove_stale_actors(desired_ids)
	_entities_by_tile = next_entities_by_tile


func get_entity_at_tile(tile_position: Vector2i) -> Dictionary:
	var tile_key = _tile_key(tile_position)
	if not _entities_by_tile.has(tile_key):
		return {}
	var entries: Array = _entities_by_tile[tile_key]
	if entries.is_empty():
		return {}
	return entries[0]


func get_actor_for_entity(entity_id: String) -> Node2D:
	return _actors_by_id.get(entity_id, null)


func _with_bucket(entry: Dictionary, bucket: String) -> Dictionary:
	var normalized = entry.duplicate(true)
	normalized["bucket"] = bucket
	return normalized


func _extract_position(entry: Dictionary) -> Vector2i:
	var position_data = entry.get("position", [0, 0])
	if position_data is Array and position_data.size() >= 2:
		return Vector2i(int(position_data[0]), int(position_data[1]))
	return Vector2i.ZERO


func _process(delta: float) -> void:
	_motion_time += delta
	for actor in _actors_by_id.values():
		if not is_instance_valid(actor):
			continue
		_update_idle_motion(actor)


func _actor_id_for_entry(entry: Dictionary, render_index: int) -> String:
	var explicit_id = str(entry.get("id", "")).strip_edges()
	if not explicit_id.is_empty():
		return explicit_id
	var bucket = str(entry.get("bucket", "npc")).strip_edges().to_lower()
	var tile_position = _extract_position(entry)
	return "%s_%d_%d_%d" % [bucket, render_index, tile_position.x, tile_position.y]


func _upsert_actor(actor_id: String, entry: Dictionary, tile_position: Vector2i) -> void:
	var actor = _actors_by_id.get(actor_id, null)
	if actor == null or not is_instance_valid(actor):
		actor = _create_sprite_entity(actor_id, entry, tile_position)
		_actors_by_id[actor_id] = actor
	else:
		_update_actor(actor, entry, tile_position)


func _create_sprite_entity(actor_id: String, entry: Dictionary, tile_position: Vector2i) -> Node2D:
	var bucket = str(entry.get("bucket", "npc"))
	var actor = Node2D.new()
	actor.name = actor_id
	actor.position = _tile_to_world(tile_position)
	actor.z_index = tile_position.y * 10 + _z_bias_for_bucket(bucket)
	actor.set_meta("bucket", bucket)
	actor.set_meta("idle_seed", float(abs(actor_id.hash() % 628)) / 100.0)
	actor.set_meta("body_lift", _body_lift_for_bucket(bucket))
	actor.set_meta("shadow_scale", _shadow_scale_for_bucket(bucket))
	actor.set_meta("last_world_position", actor.position)
	actor.set_meta("tile_position", tile_position)

	var aura = Sprite2D.new()
	aura.name = "Aura"
	aura.texture = _shadow_texture
	aura.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	aura.centered = true
	aura.position = Vector2(0, 3)
	actor.add_child(aura)

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
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.centered = true
	actor.add_child(sprite)
	_apply_actor_visual(actor, entry, Vector2.ZERO)

	add_child(actor)
	return actor


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


func _update_actor(actor: Node2D, entry: Dictionary, tile_position: Vector2i) -> void:
	var previous_world_position: Vector2 = actor.position
	var target_world_position = _tile_to_world(tile_position)
	var movement_delta = target_world_position - previous_world_position
	actor.set_meta("bucket", str(entry.get("bucket", "npc")))
	actor.set_meta("tile_position", tile_position)
	actor.z_index = tile_position.y * 10 + _z_bias_for_bucket(str(entry.get("bucket", "npc")))
	_apply_actor_visual(actor, entry, movement_delta)
	_move_actor_to(actor, target_world_position)


func _apply_actor_visual(actor: Node2D, entry: Dictionary, movement_delta: Vector2) -> void:
	var bucket = str(entry.get("bucket", "npc"))
	var aura: Sprite2D = actor.get_node_or_null("Aura")
	var sprite: Sprite2D = actor.get_node_or_null("Body")
	var shadow: Sprite2D = actor.get_node_or_null("Shadow")
	if sprite == null or shadow == null or aura == null:
		return
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
	sprite.modulate = _body_modulate(bucket, _current_adapter_id(), using_fallback)
	if absf(movement_delta.x) > 0.05:
		sprite.flip_h = movement_delta.x < 0.0
	actor.set_meta("body_lift", _body_lift_for_bucket(bucket))
	actor.set_meta("shadow_scale", _shadow_scale_for_bucket(bucket))
	aura.modulate = _aura_modulate(bucket, _current_adapter_id())
	shadow.modulate = Color(0.0, 0.0, 0.0, _shadow_alpha_for_bucket(bucket))
	_update_idle_motion(actor)


func _move_actor_to(actor: Node2D, target_world_position: Vector2) -> void:
	var previous_tween = actor.get_meta("move_tween") if actor.has_meta("move_tween") else null
	if previous_tween is Tween and is_instance_valid(previous_tween):
		previous_tween.kill()
	var distance = actor.position.distance_to(target_world_position)
	if distance <= 0.05:
		actor.position = target_world_position
		actor.set_meta("last_world_position", target_world_position)
		return
	var tween = create_tween()
	tween.tween_property(actor, "position", target_world_position, MOVE_TWEEN_DURATION).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	actor.set_meta("move_tween", tween)
	actor.set_meta("last_world_position", target_world_position)


func _update_idle_motion(actor: Node2D) -> void:
	var bucket = str(actor.get_meta("bucket", "npc"))
	var aura: Sprite2D = actor.get_node_or_null("Aura")
	var body: Sprite2D = actor.get_node_or_null("Body")
	var shadow: Sprite2D = actor.get_node_or_null("Shadow")
	if body == null or shadow == null or aura == null:
		return
	var idle_seed = float(actor.get_meta("idle_seed", 0.0))
	var amplitude = _idle_amplitude_for_bucket(bucket)
	var speed = _idle_speed_for_bucket(bucket)
	var bob = sin(_motion_time * speed + idle_seed) * amplitude
	var body_lift = float(actor.get_meta("body_lift", _body_lift_for_bucket(bucket)))
	body.position = Vector2(0.0, -body_lift + bob)
	aura.position = Vector2(0.0, 3.0 + bob * 0.08)
	shadow.position = Vector2(0.0, 4.0 + bob * 0.16)
	var aura_scale = _aura_scale_for_bucket(bucket)
	var aura_pulse = 1.0 + sin(_motion_time * speed * 0.7 + idle_seed) * 0.05
	aura.scale = Vector2(aura_scale * aura_pulse, aura_scale * aura_pulse)
	var shadow_scale = float(actor.get_meta("shadow_scale", _shadow_scale_for_bucket(bucket)))
	var pulse = 1.0 + sin(_motion_time * speed * 0.5 + idle_seed) * 0.03
	shadow.scale = Vector2(shadow_scale * pulse, shadow_scale * pulse)


func _remove_stale_actors(desired_ids: Dictionary) -> void:
	for actor_id in _actors_by_id.keys():
		if desired_ids.has(actor_id):
			continue
		var actor = _actors_by_id.get(actor_id, null)
		if actor != null and is_instance_valid(actor):
			var tween = actor.get_meta("move_tween") if actor.has_meta("move_tween") else null
			if tween is Tween and is_instance_valid(tween):
				tween.kill()
			actor.queue_free()
	var retained: Dictionary = {}
	for actor_id in _actors_by_id.keys():
		if desired_ids.has(actor_id):
			retained[actor_id] = _actors_by_id[actor_id]
	_actors_by_id = retained


func _register_entity(target_index: Dictionary, tile_position: Vector2i, entry: Dictionary) -> void:
	var tile_key = _tile_key(tile_position)
	if not target_index.has(tile_key):
		target_index[tile_key] = []
	var entries: Array = target_index[tile_key]
	entries.append(entry)
	target_index[tile_key] = entries


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
			return 36
		"enemy":
			return 28
		"npc":
			return 26
		"furniture":
			return 24
		"item":
			return 20
		_:
			return 24


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
			return 1.42
		"enemy", "npc":
			return 1.16
		"furniture":
			return 1.15
		"item":
			return 0.70
		_:
			return 0.95


static func _aura_scale_for_bucket(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"player":
			return 1.34
		"enemy":
			return 1.18
		"npc":
			return 1.08
		"furniture":
			return 0.92
		_:
			return 0.0


static func _aura_modulate(bucket: String, adapter_id: String) -> Color:
	var alpha := 0.0
	match bucket.strip_edges().to_lower():
		"player":
			alpha = 0.22
		"enemy":
			alpha = 0.18
		"npc":
			alpha = 0.14
		"furniture":
			alpha = 0.08
		_:
			alpha = 0.0
	if alpha <= 0.0:
		return Color(1.0, 1.0, 1.0, 0.0)
	var tint = adapter_bucket_tint(bucket, adapter_id).lightened(0.28)
	return Color(tint.r, tint.g, tint.b, alpha)


static func _idle_amplitude_for_bucket(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"player":
			return 1.00
		"enemy":
			return 0.82
		"npc":
			return 0.68
		"furniture":
			return 0.18
		"item":
			return 0.28
		_:
			return 0.52


static func _idle_speed_for_bucket(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"player":
			return 2.3
		"enemy":
			return 2.0
		"item":
			return 1.6
		_:
			return 1.8


static func _z_bias_for_bucket(bucket: String) -> int:
	match bucket.strip_edges().to_lower():
		"item":
			return 1
		"furniture":
			return 2
		"npc":
			return 3
		"enemy":
			return 4
		"player":
			return 5
		_:
			return 0


func _current_adapter_id() -> String:
	var loop = Engine.get_main_loop()
	if loop is SceneTree:
		var game_state = loop.root.get_node_or_null("GameState")
		if game_state != null:
			return str(game_state.adapter_id)
	return "fantasy_ember"

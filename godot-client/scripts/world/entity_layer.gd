## Renders entity sprites on the world map — player, NPCs, enemies, items, furniture.
## Delegates visual properties (tints, sizes, textures) to EntityVisuals.
extends Node2D

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const EntitySpriteCatalog = preload("res://scripts/world/entity_sprite_catalog.gd")
const EntityVisuals = preload("res://scripts/world/entity_visuals.gd")
const MOVE_TWEEN_DURATION := 0.24

var _marker_textures: Dictionary = {}
var _shadow_texture: Texture2D
var _entities_by_tile: Dictionary = {}
var _actors_by_id: Dictionary = {}
var _motion_time: float = 0.0


static func adapter_bucket_tint(bucket: String, adapter_id: String) -> Color:
	return EntityVisuals.adapter_bucket_tint(bucket, adapter_id)


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	y_sort_enabled = true
	set_process(true)
	_ensure_textures()


func _process(delta: float) -> void:
	_motion_time += delta
	for actor_id in _actors_by_id:
		var actor = _actors_by_id[actor_id]
		if actor != null and is_instance_valid(actor):
			_update_idle_motion(actor)


func render_entities(player_tile: Vector2i, grouped_entities: Dictionary, player_template: String = "warrior") -> void:
	_ensure_textures()
	var desired_ids: Dictionary = {}
	var next_entities_by_tile: Dictionary = {}
	var render_entries: Array = [{"id": "player", "name": "Player", "template": player_template, "position": [player_tile.x, player_tile.y], "bucket": "player"}]
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
		var actor_id := _actor_id_for(normalized, index)
		var tile_pos := _extract_position(normalized)
		desired_ids[actor_id] = true
		_upsert_actor(actor_id, normalized, tile_pos)
		_register_entity(next_entities_by_tile, tile_pos, normalized)
	_remove_stale(desired_ids)
	_entities_by_tile = next_entities_by_tile


func get_entity_at_tile(tile_position: Vector2i) -> Dictionary:
	var key := "%d,%d" % [tile_position.x, tile_position.y]
	if not _entities_by_tile.has(key):
		return {}
	var entries: Array = _entities_by_tile[key]
	if entries.is_empty():
		return {}
	for entry in entries:
		if entry is Dictionary and str(entry.get("bucket", "")) != "player":
			return entry
	return entries[0] if entries[0] is Dictionary else {}


func get_actor_for_entity(entry) -> Node2D:
	var payload: Dictionary = entry if entry is Dictionary else {"id": str(entry)}
	var actor_id = _actor_id_for(payload, -1)
	return _actors_by_id.get(actor_id, null)


# --- actor lifecycle -------------------------------------------------------

func _upsert_actor(actor_id: String, entry: Dictionary, tile_pos: Vector2i) -> void:
	if _actors_by_id.has(actor_id):
		var existing = _actors_by_id[actor_id]
		if existing != null and is_instance_valid(existing):
			_update_actor(existing, entry, tile_pos)
			return
	var actor := _create_actor(actor_id, entry, tile_pos)
	_actors_by_id[actor_id] = actor


func _create_actor(actor_id: String, entry: Dictionary, tile_pos: Vector2i) -> Node2D:
	var bucket := str(entry.get("bucket", "npc"))
	var actor := Node2D.new()
	actor.name = actor_id
	actor.position = _tile_to_world(tile_pos)
	actor.z_index = tile_pos.y * 10 + EntityVisuals.z_bias(bucket)
	actor.set_meta("bucket", bucket)
	actor.set_meta("idle_seed", float(abs(actor_id.hash() % 628)) / 100.0)
	actor.set_meta("body_lift", EntityVisuals.body_lift(bucket))
	actor.set_meta("shadow_scale", EntityVisuals.shadow_scale(bucket))
	actor.set_meta("last_world_position", actor.position)
	actor.set_meta("tile_position", tile_pos)

	var aura := Sprite2D.new()
	aura.name = "Aura"
	aura.texture = _shadow_texture
	aura.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	aura.centered = true
	aura.position = Vector2(0, 3)
	actor.add_child(aura)

	var shadow := Sprite2D.new()
	shadow.name = "Shadow"
	shadow.texture = _shadow_texture
	shadow.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	shadow.centered = true
	shadow.modulate = Color(0.0, 0.0, 0.0, EntityVisuals.shadow_alpha(bucket))
	shadow.position = Vector2(0, 4)
	shadow.scale = Vector2.ONE * EntityVisuals.shadow_scale(bucket)
	actor.add_child(shadow)

	var sprite := Sprite2D.new()
	sprite.name = "Body"
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.centered = true
	actor.add_child(sprite)
	_apply_visual(actor, entry, Vector2.ZERO)

	# Name label
	var entity_name := str(entry.get("name", "")).strip_edges()
	if not entity_name.is_empty() and bucket != "furniture":
		var lbl := Label.new()
		lbl.name = "NameLabel"
		lbl.text = entity_name
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lbl.position = Vector2(-40, -14)
		lbl.size = Vector2(80, 16)
		lbl.add_theme_font_size_override("font_size", 10)
		lbl.add_theme_color_override("font_color", EntityVisuals.name_label_color(bucket))
		lbl.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
		lbl.add_theme_constant_override("outline_size", 2)
		lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
		actor.add_child(lbl)

	add_child(actor)
	return actor


func _update_actor(actor: Node2D, entry: Dictionary, tile_pos: Vector2i) -> void:
	var target := _tile_to_world(tile_pos)
	var delta := target - actor.position
	var bucket := str(entry.get("bucket", "npc"))
	actor.set_meta("bucket", bucket)
	actor.set_meta("tile_position", tile_pos)
	actor.z_index = tile_pos.y * 10 + EntityVisuals.z_bias(bucket)
	_apply_visual(actor, entry, delta)
	_move_to(actor, target)


func _apply_visual(actor: Node2D, entry: Dictionary, movement: Vector2) -> void:
	var bucket := str(entry.get("bucket", "npc"))
	var aura: Sprite2D = actor.get_node_or_null("Aura")
	var body: Sprite2D = actor.get_node_or_null("Body")
	var shadow: Sprite2D = actor.get_node_or_null("Shadow")
	if body == null or shadow == null or aura == null:
		return
	var texture = EntitySpriteCatalog.resolve_texture(str(entry.get("template", "warrior")))
	var using_fallback := texture == null
	if texture != null:
		body.texture = texture
		var max_dim := maxi(texture.get_width(), texture.get_height())
		if max_dim > 0:
			var s := float(EntityVisuals.display_size(bucket)) / float(max_dim)
			body.scale = Vector2(s, s)
	else:
		body.texture = _marker_textures.get(bucket, _marker_textures["player"])
		var fb_dim := maxi(body.texture.get_width(), body.texture.get_height())
		if fb_dim > 0:
			var s := float(EntityVisuals.display_size(bucket)) / float(fb_dim)
			body.scale = Vector2(s, s)
	body.modulate = EntityVisuals.body_modulate(bucket, _adapter_id(), using_fallback)
	if absf(movement.x) > 0.05:
		body.flip_h = movement.x < 0.0
	actor.set_meta("body_lift", EntityVisuals.body_lift(bucket))
	actor.set_meta("shadow_scale", EntityVisuals.shadow_scale(bucket))
	aura.modulate = EntityVisuals.aura_modulate(bucket, _adapter_id())
	shadow.modulate = Color(0.0, 0.0, 0.0, EntityVisuals.shadow_alpha(bucket))


func _move_to(actor: Node2D, target: Vector2) -> void:
	var prev = actor.get_meta("move_tween") if actor.has_meta("move_tween") else null
	if prev is Tween and is_instance_valid(prev):
		prev.kill()
	if actor.position.distance_to(target) <= 0.05:
		actor.position = target
		actor.set_meta("last_world_position", target)
		return
	var tween := create_tween()
	tween.tween_property(actor, "position", target, MOVE_TWEEN_DURATION).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	actor.set_meta("move_tween", tween)
	actor.set_meta("last_world_position", target)


func _update_idle_motion(actor: Node2D) -> void:
	var bucket := str(actor.get_meta("bucket", "npc"))
	var body: Sprite2D = actor.get_node_or_null("Body")
	var shadow: Sprite2D = actor.get_node_or_null("Shadow")
	var aura: Sprite2D = actor.get_node_or_null("Aura")
	if body == null or shadow == null or aura == null:
		return
	var seed_val := float(actor.get_meta("idle_seed", 0.0))
	var amp := EntityVisuals.idle_amplitude(bucket)
	var spd := EntityVisuals.idle_speed(bucket)
	var bob := sin(_motion_time * spd + seed_val) * amp
	var lift := float(actor.get_meta("body_lift", EntityVisuals.body_lift(bucket)))
	body.position = Vector2(0.0, -lift + bob)
	aura.position = Vector2(0.0, 3.0 + bob * 0.08)
	shadow.position = Vector2(0.0, 4.0 + bob * 0.16)
	var a_scale := EntityVisuals.aura_scale(bucket)
	aura.scale = Vector2.ONE * a_scale * (1.0 + sin(_motion_time * spd * 0.7 + seed_val) * 0.05)
	var s_scale := float(actor.get_meta("shadow_scale", EntityVisuals.shadow_scale(bucket)))
	shadow.scale = Vector2.ONE * s_scale * (1.0 + sin(_motion_time * spd * 0.5 + seed_val) * 0.03)


func _remove_stale(desired_ids: Dictionary) -> void:
	var retained: Dictionary = {}
	for actor_id in _actors_by_id.keys():
		if desired_ids.has(actor_id):
			retained[actor_id] = _actors_by_id[actor_id]
		else:
			var actor = _actors_by_id[actor_id]
			if actor != null and is_instance_valid(actor):
				var tw = actor.get_meta("move_tween") if actor.has_meta("move_tween") else null
				if tw is Tween and is_instance_valid(tw):
					tw.kill()
				actor.queue_free()
	_actors_by_id = retained


# --- helpers ---------------------------------------------------------------

func _with_bucket(entry, bucket: String) -> Dictionary:
	if entry is Dictionary:
		var d: Dictionary = entry.duplicate(true)
		d["bucket"] = bucket
		return d
	return {"bucket": bucket}


func _actor_id_for(entry: Dictionary, fallback_index: int) -> String:
	var raw := str(entry.get("id", entry.get("entity_id", "")))
	if not raw.is_empty():
		return raw
	var name_key := str(entry.get("name", ""))
	if not name_key.is_empty():
		return "%s_%s" % [str(entry.get("bucket", "npc")), name_key.to_lower().replace(" ", "_")]
	return "entity_%d" % fallback_index


func _extract_position(entry: Dictionary) -> Vector2i:
	var pos = entry.get("position", [0, 0])
	if pos is Array and pos.size() >= 2:
		return Vector2i(int(pos[0]), int(pos[1]))
	return Vector2i.ZERO


func _tile_to_world(t: Vector2i) -> Vector2:
	return Vector2((t.x + 0.5) * TileCatalog.TILE_SIZE, (t.y + 0.5) * TileCatalog.TILE_SIZE)


func _register_entity(index: Dictionary, tile_pos: Vector2i, entry: Dictionary) -> void:
	var key := "%d,%d" % [tile_pos.x, tile_pos.y]
	if not index.has(key):
		index[key] = []
	index[key].append(entry)


func _ensure_textures() -> void:
	if _marker_textures.is_empty():
		_marker_textures = EntityVisuals.build_marker_textures()
	if _shadow_texture == null:
		_shadow_texture = EntityVisuals.build_shadow_texture()


func _adapter_id() -> String:
	var loop = Engine.get_main_loop()
	if loop is SceneTree:
		var gs = loop.root.get_node_or_null("GameState")
		if gs != null:
			return str(gs.adapter_id)
	return "fantasy_ember"

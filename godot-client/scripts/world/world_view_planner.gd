extends RefCounted
class_name WorldViewPlanner

const PovRendererConfig = preload("res://scripts/pov_renderer_config.gd")


static func update_attention_layers(selection_layer, map_payload: Dictionary, grouped_entities: Dictionary) -> void:
	if selection_layer == null:
		return
	if selection_layer.has_method("set_interest_tiles"):
		selection_layer.set_interest_tiles([])
	if selection_layer.has_method("set_hostile_tiles"):
		selection_layer.set_hostile_tiles(hostile_positions(grouped_entities))
	if selection_layer.has_method("set_ambient_tiles"):
		selection_layer.set_ambient_tiles(ambient_positions(map_payload))


static func camera_focus_tiles(player_tile: Vector2i, grouped_entities: Dictionary) -> Array:
	var tiles: Array = [player_tile]
	var nearest: Array[Dictionary] = []
	for bucket in ["npcs", "enemies", "items", "furniture"]:
		for e in grouped_entities.get(bucket, []):
			if not (e is Dictionary):
				continue
			var t: Vector2i = entity_tile(e)
			var distance: int = abs(t.x - player_tile.x) + abs(t.y - player_tile.y)
			if t == Vector2i.ZERO:
				continue
			nearest.append({
				"tile": t,
				"distance": distance,
				"bucket": bucket,
				"priority": camera_focus_priority(e, bucket, distance),
			})
	nearest.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
		var left_priority := int(left.get("priority", 0))
		var right_priority := int(right.get("priority", 0))
		if left_priority == right_priority:
			var left_distance := int(left.get("distance", 99))
			var right_distance := int(right.get("distance", 99))
			if left_distance == right_distance:
				return str(left.get("bucket", "")) < str(right.get("bucket", ""))
			return left_distance < right_distance
		return left_priority > right_priority
	)
	for entry in nearest:
		var next_tile: Vector2i = entry.get("tile", Vector2i.ZERO)
		if tiles.has(next_tile):
			continue
		tiles.append(next_tile)
		if tiles.size() >= 5:
			break
	return tiles


static func rebuild_atmosphere(map_payload: Dictionary, view_size: Vector2) -> Array:
	var atmosphere: Array = []
	var mw := maxf(float(map_payload.get("width", 16)), 16.0)
	var mh := maxf(float(map_payload.get("height", 12)), 12.0)
	var density := clampi(int((mw * mh) / 96.0), 10, 28)
	for i in range(density):
		var s := float(i + 1)
		atmosphere.append({
			"x": fposmod(mw * 13.0 + s * 57.0, maxf(view_size.x, 320.0)),
			"y": fposmod(mh * 11.0 + s * 31.0, maxf(view_size.y, 220.0)),
			"speed": 0.35 + fposmod(s * 0.17, 0.85),
			"drift": 4.0 + fposmod(s * 1.3, 14.0),
			"radius": 1.2 + fposmod(s * 0.41, 1.8),
			"phase": s * 0.63,
			"alpha": 0.08 + fposmod(s * 0.019, 0.08),
		})
	return atmosphere


static func resolve_background_key(display_location: String, scene: String) -> String:
	var hint := display_location.to_lower()
	var path := PovRendererConfig.resolve_background(hint)
	if path.contains("dungeon") or scene == "combat":
		return "dungeon"
	return "harbor"


static func ambient_positions(map_payload: Dictionary) -> Array:
	var result: Array = []
	var rows = map_payload.get("tiles", [])
	for y in range(rows.size()):
		var row = rows[y]
		if not (row is Array):
			continue
		for x in range(row.size()):
			if TileCatalog.resolve_tile_name(row[x]) in ["well", "fountain"]:
				result.append(Vector2i(x, y))
	return result


static func hostile_positions(grouped_entities: Dictionary) -> Array:
	var result: Array = []
	for e in grouped_entities.get("enemies", []):
		if e is Dictionary:
			result.append(entity_tile(e))
	return result


static func entity_tile(entry: Dictionary) -> Vector2i:
	var p = entry.get("position", [0, 0])
	if p is Array and p.size() >= 2:
		return Vector2i(int(p[0]), int(p[1]))
	return Vector2i.ZERO


static func camera_focus_priority(entry: Dictionary, bucket: String, distance: int) -> int:
	var priority := int(entry.get("placement_priority", 0))
	var actions: Array = entry.get("context_actions", [])
	var action_ids: Array[String] = []
	for action in actions:
		action_ids.append(str(action).strip_edges().to_lower())
	match bucket:
		"npcs":
			priority += 110 if action_ids.has("talk") else 60
			if str(entry.get("anchor_kind", "")) == "service":
				priority += 25
		"furniture":
			if is_service_landmark(entry):
				priority += 80
			else:
				priority += 20
		"enemies":
			priority += 95
		"items":
			priority += 18
	priority -= mini(distance, 32) * 2
	return priority


static func is_service_landmark(entry: Dictionary) -> bool:
	var anchor_kind := str(entry.get("anchor_kind", "")).strip_edges().to_lower()
	if anchor_kind in ["service", "landmark"]:
		return true
	var template := str(entry.get("template", entry.get("site_role", ""))).strip_edges().to_lower()
	return template in ["altar", "anvil", "bar_counter", "bookshelf", "campfire", "door", "fountain", "well", "workbench"]

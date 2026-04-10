extends RefCounted
class_name RuntimeAutomationProbe


static func runtime_state_payload(scene_name: String, game_state, active_panel_id: String, current_scene = null) -> Dictionary:
	if game_state == null:
		return {
			"status": "ok",
			"scene_name": scene_name,
			"spawn_frame_verified": false,
			"spawn_frame_missing": [],
			"tick_index": -1,
		}
	var spawn_frame_state := _spawn_frame_state(game_state, current_scene)
	var payload := {
		"status": "ok",
		"scene_name": scene_name,
		"shell_mode": str(game_state.current_shell_mode()),
		"location": str(game_state.get_display_location()),
		"player_tile": [game_state.player_map_pos.x, game_state.player_map_pos.y],
		"dialog_active": bool(game_state.has_active_dialog()),
		"combat_active": bool(game_state.is_in_combat()),
		"travel_active": bool(game_state.has_active_travel()),
		"active_panel_id": active_panel_id,
		"map_size": [
			int(game_state.map_data.get("width", 0)),
			int(game_state.map_data.get("height", 0)),
		],
		"neighbor_tiles": _neighbor_tile_snapshot(game_state.player_map_pos, game_state.map_data, game_state.entities),
		"entities": _flatten_entities(game_state.entities),
		"ask_about_topic_count": _ask_about_topic_count(game_state.conversation_state),
		"spawn_frame_verified": bool(spawn_frame_state.get("verified", false)),
		"spawn_frame_missing": spawn_frame_state.get("missing", []),
		"tick_index": int(spawn_frame_state.get("tick_index", game_state.tick_state.get("tick_index", -1))),
	}
	if game_state.has_active_dialog():
		payload["dialog_npc"] = str(game_state.dialog_npc)
		payload["dialog_text"] = str(game_state.dialog_text)
		payload["dialog_options"] = game_state.dialog_options
	return payload


static func _spawn_frame_state(game_state, current_scene) -> Dictionary:
	if current_scene != null and current_scene.has_method("automation_spawn_frame_payload"):
		var payload = current_scene.call("automation_spawn_frame_payload")
		if payload is Dictionary:
			return payload
	var missing: Array[String] = []
	if not _has_nearby_named_npc(game_state.player_map_pos, game_state.entities):
		missing.append("npc")
	if not _has_nearby_service_or_furniture(game_state.player_map_pos, game_state.entities):
		missing.append("service_or_furniture")
	return {
		"verified": missing.is_empty(),
		"missing": missing,
		"tick_index": int(game_state.tick_state.get("tick_index", -1)),
	}


static func _neighbor_tile_snapshot(player_tile: Vector2i, map_data: Dictionary, grouped_entities: Dictionary) -> Array:
	var snapshot: Array = []
	for dir in [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]:
		var tile: Vector2i = player_tile + dir
		snapshot.append({
			"tile": [tile.x, tile.y],
			"tile_name": _tile_name_at(map_data, tile),
			"occupied": _tile_has_entity(grouped_entities, tile),
		})
	return snapshot


static func _flatten_entities(grouped_entities: Dictionary) -> Array:
	var flattened: Array = []
	for bucket in ["npcs", "enemies", "items", "furniture"]:
		for entry in grouped_entities.get(bucket, []):
			if not (entry is Dictionary):
				continue
			var pos = entry.get("position", [0, 0])
			var x: int = 0
			var y: int = 0
			if pos is Array and pos.size() >= 2:
				x = int(pos[0])
				y = int(pos[1])
			flattened.append({
				"id": str(entry.get("id", entry.get("entity_id", ""))),
				"name": str(entry.get("name", "")),
				"bucket": bucket,
				"role": str(entry.get("role", "")),
				"position": [x, y],
			})
	return flattened


static func _has_nearby_named_npc(player_tile: Vector2i, grouped_entities: Dictionary) -> bool:
	for entry in grouped_entities.get("npcs", []):
		if not (entry is Dictionary):
			continue
		if str(entry.get("name", "")).strip_edges().is_empty():
			continue
		if _within_spawn_radius(player_tile, _entry_position(entry)):
			return true
	return false


static func _has_nearby_service_or_furniture(player_tile: Vector2i, grouped_entities: Dictionary) -> bool:
	for entry in grouped_entities.get("furniture", []):
		if entry is Dictionary and _within_spawn_radius(player_tile, _entry_position(entry)):
			return true
	for entry in grouped_entities.get("npcs", []):
		if not (entry is Dictionary):
			continue
		if not _within_spawn_radius(player_tile, _entry_position(entry)):
			continue
		var combined := ("%s %s" % [str(entry.get("name", "")), str(entry.get("role", ""))]).to_lower()
		for token in ["merchant", "shop", "inn", "smith", "trader", "vendor", "barkeep", "keeper"]:
			if combined.contains(token):
				return true
	return false


static func _entry_position(entry: Dictionary) -> Vector2i:
	var pos = entry.get("position", [])
	if pos is Array and pos.size() >= 2:
		return Vector2i(int(pos[0]), int(pos[1]))
	if pos is Vector2i:
		return pos
	return Vector2i.ZERO


static func _within_spawn_radius(player_tile: Vector2i, target_tile: Vector2i) -> bool:
	if player_tile == Vector2i.ZERO and target_tile == Vector2i.ZERO:
		return false
	return maxi(absi(target_tile.x - player_tile.x), absi(target_tile.y - player_tile.y)) <= 8


static func _tile_name_at(map_data: Dictionary, tile: Vector2i) -> String:
	var rows = map_data.get("tiles", [])
	if not (rows is Array) or tile.y < 0 or tile.y >= rows.size():
		return ""
	var row = rows[tile.y]
	if not (row is Array) or tile.x < 0 or tile.x >= row.size():
		return ""
	var value = row[tile.x]
	if value == null:
		return ""
	return str(value)


static func _tile_has_entity(grouped_entities: Dictionary, tile: Vector2i) -> bool:
	for bucket in ["npcs", "enemies", "items", "furniture"]:
		for entry in grouped_entities.get(bucket, []):
			if not (entry is Dictionary):
				continue
			var pos = entry.get("position", [])
			if pos is Array and pos.size() >= 2 and int(pos[0]) == tile.x and int(pos[1]) == tile.y:
				return true
	return false


static func _ask_about_topic_count(conversation_state: Dictionary) -> int:
	var topic_ids = conversation_state.get("ask_about_topic_ids", [])
	return topic_ids.size() if topic_ids is Array else 0

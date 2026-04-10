extends RefCounted
class_name SessionWorldSync

const SERVICE_ROLE_TOKENS := ["merchant", "shop", "inn", "smith", "trader", "vendor", "barkeep", "keeper"]
const FIRST_FRAME_RADIUS := 8

var _owner
var _first_frame_baseline := {
	"verified": false,
	"missing": ["npc", "service_or_furniture"],
	"tick_index": -1,
}
var _extra_snapshot_requested := false
var _runtime_poll_timer: Timer


func _init(owner) -> void:
	_owner = owner


func initialize_runtime() -> void:
	_extra_snapshot_requested = false
	_first_frame_baseline = _evaluate_first_frame_baseline()
	_ensure_runtime_poll_timer()
	if GameState.campaign_id.is_empty():
		return
	if GameState.runtime_transport == "ws" and bool(GameState.transport.get("websocket_ready", false)):
		Backend.ensure_runtime_socket(GameState.campaign_id, GameState.ws_url, GameState.ws_path)
	# Always pull one bootstrap snapshot when the session scene mounts.
	# Continue/load can otherwise show the settlement before the first live tick lands,
	# which makes the world look empty even though the runtime is populated.
	resync_campaign()
	_runtime_poll_timer.start()


func on_map_resynced(data) -> void:
	if data != null:
		GameState.update_from_response(data)
		_first_frame_baseline = _evaluate_first_frame_baseline()
	complete_followup_sync()


func on_inventory_resynced(data) -> void:
	if data != null:
		GameState.update_from_response(data)
		_first_frame_baseline = _evaluate_first_frame_baseline()
	complete_followup_sync()


func complete_followup_sync() -> void:
	_owner._pending_sync_callbacks = maxi(_owner._pending_sync_callbacks - 1, 0)
	if _owner._pending_sync_callbacks == 0:
		_owner._finish_turn_sync()


func resync_campaign() -> void:
	if GameState.campaign_id.is_empty():
		return
	_owner._set_waiting(true)
	_owner._pending_sync_callbacks = 1
	Backend.get_campaign(GameState.campaign_id, on_campaign_snapshot_loaded)


func _ensure_runtime_poll_timer() -> void:
	if _runtime_poll_timer != null and is_instance_valid(_runtime_poll_timer):
		return
	_runtime_poll_timer = Timer.new()
	_runtime_poll_timer.name = "RuntimeFallbackPollTimer"
	_runtime_poll_timer.wait_time = 2.0
	_runtime_poll_timer.one_shot = false
	_runtime_poll_timer.autostart = false
	_runtime_poll_timer.timeout.connect(_on_runtime_poll_timeout)
	_owner.add_child(_runtime_poll_timer)


func shutdown() -> void:
	if _runtime_poll_timer != null and is_instance_valid(_runtime_poll_timer):
		_runtime_poll_timer.stop()
		_runtime_poll_timer.queue_free()
	_runtime_poll_timer = null


func _on_runtime_poll_timeout() -> void:
	if not GameState.has_active_campaign() or _owner.is_waiting:
		return
	if Backend.runtime_connected_for(GameState.campaign_id):
		return
	Backend.get_campaign(GameState.campaign_id, _on_runtime_poll_snapshot_loaded)


func _on_runtime_poll_snapshot_loaded(data) -> void:
	if data != null:
		GameState.update_from_response(data)
		_first_frame_baseline = _evaluate_first_frame_baseline()


func on_campaign_snapshot_loaded(data) -> void:
	if data != null:
		GameState.update_from_response(data)
		_first_frame_baseline = _evaluate_first_frame_baseline()
	complete_followup_sync()


func map_has_tiles() -> bool:
	return (
		GameState.map_data.has("tiles")
		and GameState.map_data.get("tiles", []) is Array
		and not GameState.map_data.get("tiles", []).is_empty()
	)


func ensure_first_frame_baseline() -> Dictionary:
	_first_frame_baseline = _evaluate_first_frame_baseline()
	if _needs_extra_snapshot() and not _extra_snapshot_requested and not GameState.campaign_id.is_empty():
		_extra_snapshot_requested = true
		Backend.get_campaign(GameState.campaign_id, _on_first_frame_snapshot_loaded)
	return _first_frame_baseline.duplicate(true)


func first_frame_baseline_state() -> Dictionary:
	_first_frame_baseline = _evaluate_first_frame_baseline()
	return _first_frame_baseline.duplicate(true)


func _on_first_frame_snapshot_loaded(data) -> void:
	if data != null:
		GameState.update_from_response(data)
	_first_frame_baseline = _evaluate_first_frame_baseline()


func _needs_extra_snapshot() -> bool:
	return _flattened_entity_count() == 0


func _flattened_entity_count() -> int:
	var total := 0
	for bucket in ["npcs", "enemies", "items", "furniture"]:
		var entries = GameState.entities.get(bucket, [])
		if entries is Array:
			total += entries.size()
	return total


func _evaluate_first_frame_baseline() -> Dictionary:
	var player_tile: Vector2i = GameState.player_map_pos
	var missing: Array[String] = []
	if not _has_nearby_named_npc(player_tile):
		missing.append("npc")
	if not _has_nearby_service_or_furniture(player_tile):
		missing.append("service_or_furniture")
	return {
		"verified": missing.is_empty(),
		"missing": missing,
		"tick_index": int(GameState.tick_state.get("tick_index", -1)),
	}


func _has_nearby_named_npc(player_tile: Vector2i) -> bool:
	for entry in GameState.entities.get("npcs", []):
		if not (entry is Dictionary):
			continue
		if str(entry.get("name", "")).strip_edges().is_empty():
			continue
		if _is_within_radius(_entry_position(entry), player_tile):
			return true
	return false


func _has_nearby_service_or_furniture(player_tile: Vector2i) -> bool:
	for entry in GameState.entities.get("furniture", []):
		if not (entry is Dictionary):
			continue
		if _is_within_radius(_entry_position(entry), player_tile):
			return true
	for entry in GameState.entities.get("npcs", []):
		if not (entry is Dictionary):
			continue
		if not _is_within_radius(_entry_position(entry), player_tile):
			continue
		var combined := "%s %s" % [str(entry.get("name", "")), str(entry.get("role", ""))]
		var normalized := combined.to_lower()
		for token in SERVICE_ROLE_TOKENS:
			if normalized.contains(token):
				return true
	return false


func _entry_position(entry: Dictionary) -> Vector2i:
	var pos = entry.get("position", [])
	if pos is Array and pos.size() >= 2:
		return Vector2i(int(pos[0]), int(pos[1]))
	if pos is Vector2i:
		return pos
	return Vector2i.ZERO


func _is_within_radius(position: Vector2i, player_tile: Vector2i) -> bool:
	if player_tile == Vector2i.ZERO and position == Vector2i.ZERO:
		return false
	return maxi(absi(position.x - player_tile.x), absi(position.y - player_tile.y)) <= FIRST_FRAME_RADIUS

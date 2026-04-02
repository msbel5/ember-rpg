extends RefCounted
class_name SessionWorldSync


var _owner


func _init(owner) -> void:
	_owner = owner


func initialize_runtime() -> void:
	if GameState.has_active_campaign():
		if GameState.map_data.is_empty() or not map_has_tiles():
			resync_campaign()
	elif GameState.session_id != "":
		if GameState.map_data.is_empty():
			enter_scene(GameState.location if not GameState.location.is_empty() else "Harbor Town")
		elif not map_has_tiles():
			resync_existing_session()


func enter_scene(location_name: String) -> void:
	var display_name := location_name.replace("_", " ").capitalize()
	_owner.narrative_panel.append_system_text("[color=gray]Entering %s...[/color]" % display_name)
	Backend.enter_scene(GameState.session_id, location_name, on_scene_entered)


func on_scene_entered(data) -> void:
	if data == null:
		_owner.narrative_panel.append_system_text("[color=red]Failed to enter scene.[/color]")
		return
	GameState.update_from_response(data)
	if (not data.has("player") or not data["player"].has("position")) and GameState.map_data.has("spawn_point"):
		var spawn_point = GameState.map_data.get("spawn_point", [])
		if spawn_point is Array and spawn_point.size() >= 2:
			GameState.player_map_pos = Vector2i(int(spawn_point[0]), int(spawn_point[1]))
	Backend.get_session(GameState.session_id, on_scene_session_loaded)
	Backend.get_map(GameState.session_id, on_map_loaded)
	Backend.get_inventory(GameState.session_id, on_inventory_loaded)


func on_scene_session_loaded(data) -> void:
	if data != null:
		GameState.update_from_response(data)


func on_map_loaded(data) -> void:
	if data != null:
		GameState.update_from_response(data)


func on_inventory_loaded(data) -> void:
	if data != null:
		GameState.update_from_response(data)


func on_map_resynced(data) -> void:
	if data != null:
		GameState.update_from_response(data)
	complete_followup_sync()


func on_inventory_resynced(data) -> void:
	if data != null:
		GameState.update_from_response(data)
	complete_followup_sync()


func complete_followup_sync() -> void:
	_owner._pending_sync_callbacks = maxi(_owner._pending_sync_callbacks - 1, 0)
	if _owner._pending_sync_callbacks == 0:
		_owner._finish_turn_sync()


func resync_existing_session() -> void:
	if GameState.session_id.is_empty():
		return
	Backend.get_session(GameState.session_id, on_scene_session_loaded)
	Backend.get_map(GameState.session_id, on_map_loaded)
	Backend.get_inventory(GameState.session_id, on_inventory_loaded)


func resync_campaign() -> void:
	if GameState.campaign_id.is_empty():
		return
	_owner._set_waiting(true)
	_owner._pending_sync_callbacks = 2
	Backend.get_campaign(GameState.campaign_id, on_campaign_snapshot_loaded)
	Backend.get_campaign_settlement(GameState.campaign_id, on_campaign_settlement_loaded)


func on_campaign_snapshot_loaded(data) -> void:
	if data != null:
		GameState.update_from_response(data)
	complete_followup_sync()


func on_campaign_settlement_loaded(data) -> void:
	if data != null and data is Dictionary:
		GameState.update_from_response({"settlement_state": data})
	complete_followup_sync()


func map_has_tiles() -> bool:
	return (
		GameState.map_data.has("tiles")
		and GameState.map_data.get("tiles", []) is Array
		and not GameState.map_data.get("tiles", []).is_empty()
	)

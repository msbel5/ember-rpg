extends RefCounted
class_name SessionWorldSync


var _owner


func _init(owner) -> void:
	_owner = owner


func initialize_runtime() -> void:
	if GameState.campaign_id.is_empty():
		return
	if GameState.runtime_transport == "ws" and bool(GameState.transport.get("websocket_ready", false)):
		Backend.ensure_runtime_socket(GameState.campaign_id, GameState.ws_url, GameState.ws_path)
	# Always pull one bootstrap snapshot when the session scene mounts.
	# Continue/load can otherwise show the settlement before the first live tick lands,
	# which makes the world look empty even though the runtime is populated.
	resync_campaign()


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


func resync_campaign() -> void:
	if GameState.campaign_id.is_empty():
		return
	_owner._set_waiting(true)
	_owner._pending_sync_callbacks = 1
	Backend.get_campaign(GameState.campaign_id, on_campaign_snapshot_loaded)


func on_campaign_snapshot_loaded(data) -> void:
	if data != null:
		GameState.update_from_response(data)
	complete_followup_sync()


func map_has_tiles() -> bool:
	return (
		GameState.map_data.has("tiles")
		and GameState.map_data.get("tiles", []) is Array
		and not GameState.map_data.get("tiles", []).is_empty()
	)
